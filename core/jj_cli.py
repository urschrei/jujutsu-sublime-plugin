"""CLI wrapper for jj with async execution and output parsing."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import sublime

from .diff_selection import HUNK_HEADER_RE


def _get_startupinfo():
    """Return a STARTUPINFO that hides the console window on Windows."""
    if hasattr(subprocess, "STARTUPINFO"):
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return si
    return None


@dataclass
class JJResult:
    """Result of a jj command execution."""

    success: bool
    stdout: str
    stderr: str
    returncode: int


@dataclass
class ChangeInfo:
    """Information about a jj change."""

    change_id: str
    commit_id: str
    description: str
    author: str
    timestamp: str
    is_empty: bool
    is_immutable: bool
    is_working_copy: bool
    bookmarks: list = field(default_factory=list)
    # Unique prefix highlighting
    change_id_prefix: str = ""  # The unique prefix part
    change_id_rest: str = ""  # The rest after the prefix
    has_conflict: bool = False


@dataclass
class DiffHunk:
    """Represents a diff hunk for gutter markers."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    hunk_type: str  # 'added', 'modified', 'deleted'
    lines: list = field(default_factory=list)


@dataclass
class OperationInfo:
    """Information about a jj operation (from jj op log)."""

    op_id: str
    description: str
    timestamp: str
    user: str
    is_snapshot: bool
    is_current: bool


@dataclass
class EvologEntry:
    """One entry in a change's evolution log (a past commit version)."""

    commit_id: str
    description: str
    timestamp: str


@dataclass
class ConflictedFile:
    """A conflicted file as reported by jj resolve --list."""

    path: str
    description: str


@dataclass
class BookmarkInfo:
    """Information about a jj bookmark."""

    name: str
    change_id: str
    description: str


_executor: ThreadPoolExecutor | None = None
_generation: int = 0


def _make_success_callback(callback):
    """Create a standard callback handler for success/error results.

    Returns a function that calls callback(success, error) where error is
    empty string on success, or stderr on failure.
    """

    def on_result(result):
        callback(result.success, result.stderr if not result.success else "")

    return on_result


def _get_executor() -> ThreadPoolExecutor:
    """Get or create the thread pool executor."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="sublime-jujutsu-worker"
        )
    return _executor


def init_executor():
    """Initialise the executor. Called from plugin_loaded()."""
    global _generation
    _generation += 1
    _get_executor()


class JJCli:
    """Wrapper for jj CLI commands."""

    # Templates for machine-readable output
    # Use ||| as separator to avoid tab/space conversion issues
    FIELD_SEP = "|||"

    STATUS_TEMPLATE = (
        'change_id.short(8) ++ "|||" ++ '
        'commit_id.short(8) ++ "|||" ++ '
        'if(description, description.first_line(), "(no description)") ++ "|||" ++ '
        'author.email() ++ "|||" ++ '
        'committer.timestamp().format("%Y-%m-%d %H:%M") ++ "|||" ++ '
        'if(empty, "true", "false") ++ "|||" ++ '
        'if(immutable, "true", "false") ++ "|||" ++ '
        'if(self.contained_in("@"), "true", "false") ++ "|||" ++ '
        'bookmarks.join(",") ++ "|||" ++ '
        'change_id.shortest(8).prefix() ++ "|||" ++ '
        'change_id.shortest(8).rest() ++ "|||" ++ '
        'if(conflict, "true", "false")'
    )

    LOG_TEMPLATE = (
        'change_id.short(8) ++ "|||" ++ '
        'commit_id.short(8) ++ "|||" ++ '
        'if(description, description.first_line(), "(no description)") ++ "|||" ++ '
        'author.email() ++ "|||" ++ '
        'committer.timestamp().format("%Y-%m-%d %H:%M") ++ "|||" ++ '
        'if(empty, "true", "false") ++ "|||" ++ '
        'if(immutable, "true", "false") ++ "|||" ++ '
        'if(self.contained_in("@"), "true", "false") ++ "|||" ++ '
        'bookmarks.join(",") ++ "|||" ++ '
        'change_id.shortest(8).prefix() ++ "|||" ++ '
        'change_id.shortest(8).rest() ++ "|||" ++ '
        'if(conflict, "true", "false") ++ "\\n"'
    )

    def __init__(self, repo_root, jj_path=None):
        self.repo_root = repo_root
        self.jj_path = jj_path or "jj"

    def _run_sync(self, args, cwd=None, input_text=None):
        """Run a jj command synchronously."""
        cmd = [self.jj_path] + args
        working_dir = cwd or self.repo_root

        try:
            env = os.environ.copy()
            # Ensure consistent output format
            env["NO_COLOR"] = "1"

            process = subprocess.Popen(
                cmd,
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE if input_text else None,
                env=env,
                startupinfo=_get_startupinfo(),
            )
            stdout, stderr = process.communicate(
                input=input_text.encode() if input_text else None, timeout=30
            )
            return JJResult(
                success=process.returncode == 0,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                returncode=process.returncode,
            )
        except subprocess.TimeoutExpired:
            process.kill()
            return JJResult(
                success=False,
                stdout="",
                stderr="Command timed out",
                returncode=-1,
            )
        except OSError:
            return JJResult(
                success=False,
                stdout="",
                stderr=f"jj executable not found: {self.jj_path}",
                returncode=-1,
            )
        except Exception as e:
            return JJResult(
                success=False,
                stdout="",
                stderr=str(e),
                returncode=-1,
            )

    def run_async(self, args, callback, cwd=None, input_text=None):
        """Run a jj command asynchronously and call callback on main thread."""
        task_generation = _generation

        def execute():
            result = self._run_sync(args, cwd, input_text)
            if task_generation == _generation:
                sublime.set_timeout(lambda: callback(result), 0)

        _get_executor().submit(execute)

    def run(self, args, cwd=None, input_text=None):
        """Run a jj command synchronously (use sparingly)."""
        return self._run_sync(args, cwd, input_text)

    def get_current_change(self, callback):
        """Get information about the current working copy change."""

        def on_result(result):
            if not result.success:
                callback(None)
                return

            info = self._parse_change_info(result.stdout.strip())
            callback(info)

        self.run_async(
            ["log", "-r", "@", "-T", self.STATUS_TEMPLATE, "--no-graph"], on_result
        )

    # Evolog entries expose the commit via the `commit` keyword rather
    # than top-level commit keywords
    EVOLOG_TEMPLATE = (
        'commit.commit_id().short(8) ++ "|||" ++ '
        "if(commit.description(), commit.description().first_line(), "
        '"(no description)") ++ "|||" ++ '
        'commit.committer().timestamp().format("%Y-%m-%d %H:%M") ++ "\\n"'
    )

    def get_evolog(self, callback, revision="@", limit=50):
        """Get the evolution log of a change (its past commit versions).

        Callback receives a list of EvologEntry, newest first.
        """

        def on_result(result):
            if not result.success:
                callback([])
                return

            entries = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split(self.FIELD_SEP)
                if len(parts) < 3:
                    continue
                entries.append(
                    EvologEntry(
                        commit_id=parts[0],
                        description=parts[1],
                        timestamp=parts[2],
                    )
                )
            callback(entries)

        args = [
            "evolog",
            "-r",
            revision,
            "--no-graph",
            "-n",
            str(limit),
            "-T",
            self.EVOLOG_TEMPLATE,
        ]
        self.run_async(args, on_result)

    # Per-line annotate template. Passed explicitly rather than relying on
    # templates.file_annotate so that broken or outdated user template
    # aliases cannot break the command.
    ANNOTATE_TEMPLATE = (
        'commit.change_id().shortest(8) ++ "  " ++ '
        'pad_end(20, truncate_end(20, commit.author().email())) ++ "  " ++ '
        'commit.committer().timestamp().format("%Y-%m-%d") ++ "  " ++ '
        'pad_start(4, line_number) ++ ": " ++ content'
    )

    def annotate_file(self, path, callback):
        """Annotate a file with the change that last modified each line.

        Callback receives (success, text_or_error).
        """

        def on_result(result):
            callback(result.success, result.stdout if result.success else result.stderr)

        self.run_async(
            ["file", "annotate", path, "-T", self.ANNOTATE_TEMPLATE], on_result
        )

    OP_LOG_TEMPLATE = (
        'id.short(12) ++ "|||" ++ '
        'description.first_line() ++ "|||" ++ '
        'time.start().format("%Y-%m-%d %H:%M:%S") ++ "|||" ++ '
        'user ++ "|||" ++ '
        'if(snapshot, "true", "false") ++ "|||" ++ '
        'if(current_operation, "true", "false") ++ "\\n"'
    )

    def op_log(self, callback, limit=100):
        """Get the operation log.

        Callback receives a list of OperationInfo, newest first.
        """

        def on_result(result):
            if not result.success:
                callback([])
                return

            operations = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                info = self._parse_operation_info(line)
                if info:
                    operations.append(info)
            callback(operations)

        args = [
            "op",
            "log",
            "--no-graph",
            "-n",
            str(limit),
            "-T",
            self.OP_LOG_TEMPLATE,
        ]
        self.run_async(args, on_result)

    def _parse_operation_info(self, line):
        """Parse a line of op log template output into OperationInfo."""
        parts = line.split(self.FIELD_SEP)
        if len(parts) < 6:
            return None

        return OperationInfo(
            op_id=parts[0],
            description=parts[1] or "(no description)",
            timestamp=parts[2],
            user=parts[3],
            is_snapshot=parts[4] == "true",
            is_current=parts[5] == "true",
        )

    def op_restore(self, op_id, callback):
        """Restore the repository to the state at the given operation."""
        self.run_async(["op", "restore", op_id], _make_success_callback(callback))

    def get_status_info(self, callback):
        """Get working copy change info plus conflicted mutable changes.

        Callback receives (current_change, conflicted_changes) where
        current_change is a ChangeInfo (or None on error) and
        conflicted_changes is a list of ChangeInfo for mutable changes
        that contain conflicted files (possibly including the working copy).
        """

        def on_result(result):
            if not result.success:
                callback(None, [])
                return

            current = None
            conflicted = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                info = self._parse_change_info(line)
                if info is None:
                    continue
                if info.is_working_copy:
                    current = info
                if info.has_conflict:
                    conflicted.append(info)
            callback(current, conflicted)

        self.run_async(
            [
                "log",
                "-r",
                "@ | (mutable() & conflicts())",
                "-T",
                self.LOG_TEMPLATE,
                "--no-graph",
            ],
            on_result,
        )

    def resolve_list(self, callback, revision=None):
        """List conflicted files for a revision (default: @).

        Callback receives (success, files_or_error): a list of
        ConflictedFile on success, or an error message string on failure.
        A revision without conflicts yields (True, []).
        """

        def on_result(result):
            if not result.success:
                if "No conflicts found" in result.stderr:
                    callback(True, [])
                else:
                    callback(False, result.stderr)
                return
            callback(True, self._parse_resolve_list(result.stdout))

        args = ["resolve", "--list"]
        if revision:
            args.extend(["-r", revision])
        self.run_async(args, on_result)

    # Columns are separated by runs of whitespace, e.g.
    # "path/to/file.txt    2-sided conflict"
    RESOLVE_LIST_RE = re.compile(r"^(?P<path>.+?)(?:\t+|\s{2,})(?P<desc>\S.*)$")

    def _parse_resolve_list(self, output):
        """Parse jj resolve --list output into ConflictedFile objects."""
        files = []
        for line in output.splitlines():
            if not line.strip():
                continue
            match = self.RESOLVE_LIST_RE.match(line)
            if match:
                files.append(
                    ConflictedFile(
                        path=match.group("path"),
                        description=match.group("desc").strip(),
                    )
                )
            else:
                files.append(ConflictedFile(path=line.strip(), description=""))
        return files

    # Two-line-per-entry template for the graph log view
    GRAPH_LOG_TEMPLATE = (
        'change_id.shortest(8) ++ "  " ++ '
        'if(description, description.first_line(), "(no description set)") ++ '
        'if(empty, " (empty)", "") ++ '
        'if(conflict, " (conflict)", "") ++ '
        'if(bookmarks, "  [" ++ bookmarks.join(", ") ++ "]", "") ++ "\\n" ++ '
        'author.email() ++ "  " ++ '
        'committer.timestamp().format("%Y-%m-%d %H:%M") ++ "\\n"'
    )

    def get_log_graph(self, callback, revset=None, limit=200):
        """Get the log rendered as a graph, plus the change ids it contains.

        Callback receives (success, text_or_error, change_ids) where
        change_ids is a set of the change id strings present in the graph.
        Without a revset, jj's configured default revset is used.
        """

        graph_args = ["log", "-T", self.GRAPH_LOG_TEMPLATE, "-n", str(limit)]
        id_args = [
            "log",
            "--no-graph",
            "-T",
            'change_id.shortest(8) ++ "\\n"',
            "-n",
            str(limit),
        ]
        if revset:
            graph_args.extend(["-r", revset])
            id_args.extend(["-r", revset])

        def on_graph(result):
            if not result.success:
                callback(False, result.stderr, set())
                return
            graph_text = result.stdout

            def on_ids(id_result):
                if not id_result.success:
                    callback(False, id_result.stderr, set())
                    return
                ids = {
                    line.strip()
                    for line in id_result.stdout.splitlines()
                    if line.strip()
                }
                callback(True, graph_text, ids)

            self.run_async(id_args, on_ids)

        self.run_async(graph_args, on_graph)

    def get_log(self, callback, revset="::", limit=50, paths=None):
        """Get commit log, optionally restricted to the given paths."""

        def on_result(result):
            if not result.success:
                callback([])
                return

            changes = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    info = self._parse_change_info(line)
                    if info:
                        changes.append(info)
            callback(changes)

        args = [
            "log",
            "-r",
            revset,
            "-T",
            self.LOG_TEMPLATE,
            "--no-graph",
            "-n",
            str(limit),
        ]
        if paths:
            args.extend(["--"] + list(paths))
        self.run_async(args, on_result)

    def get_diff(self, callback, file_path=None):
        """Get diff for the working copy, optionally for a specific file."""

        def on_result(result):
            if not result.success:
                callback([])
                return

            hunks = self._parse_git_diff(result.stdout, file_path)
            callback(hunks)

        args = ["diff", "--git"]
        if file_path:
            args.extend(["--", file_path])
        self.run_async(args, on_result)

    def get_file_diff(self, file_path, callback):
        """Get diff for a specific file."""
        self.get_diff(callback, file_path)

    def new(self, callback, message=None, revision=None):
        """Create a new change, optionally on top of a specific revision."""
        args = ["new"]
        if revision:
            args.append(revision)
        if message:
            args.extend(["-m", message])
        self.run_async(args, _make_success_callback(callback))

    def describe(self, message, callback, revision=None):
        """Set description for a change.

        If revision is None, describes the current change (@).
        """
        args = ["describe", "-m", message]
        if revision:
            args.extend(["-r", revision])
        self.run_async(args, _make_success_callback(callback))

    def commit(self, message, callback):
        """Commit current change (describe + new)."""
        self.run_async(["commit", "-m", message], _make_success_callback(callback))

    def squash(self, callback):
        """Squash current change into parent."""
        self.run_async(["squash"], _make_success_callback(callback))

    def absorb(self, callback, from_rev=None):
        """Absorb changes into ancestor commits.

        Moves changes from the source revision into the stack of mutable
        revisions where the corresponding lines were last modified.
        """
        args = ["absorb"]
        if from_rev:
            args.extend(["--from", from_rev])
        self.run_async(args, _make_success_callback(callback))

    def squash_flexible(self, sources, destination, use_dest_message, callback):
        """Flexible squash with multiple sources and destination.

        sources: list of revision IDs to squash from
        destination: revision ID to squash into
        use_dest_message: if True, discard source messages and use destination's
        """
        args = ["squash"]

        # Add source revisions
        for source in sources:
            args.extend(["--from", source])

        # Add destination
        args.extend(["--into", destination])

        # Optionally discard source messages
        if use_dest_message:
            args.append("--use-destination-message")

        self.run_async(args, _make_success_callback(callback))

    def abandon(self, callback, revision=None):
        """Abandon a change (default: the current change)."""
        args = ["abandon"]
        if revision:
            args.append(revision)
        self.run_async(args, _make_success_callback(callback))

    def undo(self, callback):
        """Undo last operation."""
        self.run_async(["undo"], _make_success_callback(callback))

    def edit(self, revision, callback):
        """Edit (checkout) a specific revision."""
        self.run_async(["edit", revision], _make_success_callback(callback))

    def rebase(self, revision, destination, callback):
        """Rebase a revision onto a destination."""
        self.run_async(
            ["rebase", "-r", revision, "-d", destination],
            _make_success_callback(callback),
        )

    def rebase_source(self, source, destination, callback):
        """Rebase a revision and its descendants onto a destination."""
        self.run_async(
            ["rebase", "-s", source, "-d", destination],
            _make_success_callback(callback),
        )

    def rebase_insert_before(self, revision, target, callback):
        """Insert revision before target (make revision a parent of target)."""
        self.run_async(
            ["rebase", "-r", revision, "--insert-before", target],
            _make_success_callback(callback),
        )

    def rebase_insert_after(self, revision, target, callback):
        """Insert revision after target (make revision a child of target)."""
        self.run_async(
            ["rebase", "-r", revision, "--insert-after", target],
            _make_success_callback(callback),
        )

    def rebase_flexible(self, source_mode, source_rev, dest_mode, dest_rev, callback):
        """Flexible rebase with full mode control.

        source_mode: 'revision' (-r), 'source' (-s), or 'branch' (-b)
        dest_mode: 'onto' (-d), 'after' (-A), or 'before' (-B)
        """
        args = ["rebase"]

        # Source mode
        if source_mode == "revision":
            args.extend(["-r", source_rev])
        elif source_mode == "source":
            args.extend(["-s", source_rev])
        elif source_mode == "branch":
            args.extend(["-b", source_rev])

        # Destination mode
        if dest_mode == "onto":
            args.extend(["-d", dest_rev])
        elif dest_mode == "after":
            args.extend(["-A", dest_rev])
        elif dest_mode == "before":
            args.extend(["-B", dest_rev])

        self.run_async(args, _make_success_callback(callback))

    def get_diff_raw(self, callback, revision="@", context=3, paths=None):
        """Get raw diff output for a revision.

        Args:
            callback: Called with (success, diff_text_or_error)
            revision: Revision to diff (default: @)
            context: Number of context lines around changes (default: 3)
            paths: Optional list of paths to restrict the diff to
        """

        def on_result(result):
            callback(result.success, result.stdout if result.success else result.stderr)

        args = ["diff", "-r", revision, "--git", "--context", str(context)]
        if paths:
            args.extend(["--"] + list(paths))
        self.run_async(args, on_result)

    # Bookmark template for machine-readable output
    BOOKMARK_TEMPLATE = (
        'name ++ "|||" ++ '
        'if(normal_target, normal_target.change_id().short(8), "(deleted)") ++ "|||" ++ '
        'if(normal_target, normal_target.description().first_line(), "") ++ "\\n"'
    )

    def _parse_ref_list(self, output):
        """Parse bookmark/tag list template output into BookmarkInfo objects."""
        refs = []
        for line in output.strip().split("\n"):
            if line:
                parts = line.split(self.FIELD_SEP)
                if len(parts) >= 3:
                    refs.append(
                        BookmarkInfo(
                            name=parts[0],
                            change_id=parts[1],
                            description=parts[2] or "(no description)",
                        )
                    )
        return refs

    def bookmark_list(self, callback):
        """Get list of bookmarks with their targets."""

        def on_result(result):
            callback(self._parse_ref_list(result.stdout) if result.success else [])

        self.run_async(["bookmark", "list", "-T", self.BOOKMARK_TEMPLATE], on_result)

    def tag_list(self, callback):
        """Get list of tags with their targets.

        Tags share the bookmark template keywords, so entries are returned
        as BookmarkInfo objects.
        """

        def on_result(result):
            callback(self._parse_ref_list(result.stdout) if result.success else [])

        self.run_async(["tag", "list", "-T", self.BOOKMARK_TEMPLATE], on_result)

    def tag_set(self, name, revision, callback):
        """Create or update a tag (with --allow-move)."""
        args = ["tag", "set", name, "-r", revision, "--allow-move"]
        self.run_async(args, _make_success_callback(callback))

    def tag_delete(self, names, callback):
        """Delete one or more tags."""
        args = ["tag", "delete"] + list(names)
        self.run_async(args, _make_success_callback(callback))

    def bookmark_set(self, name, revision, callback):
        """Create or update a bookmark (with --allow-backwards)."""
        args = ["bookmark", "set", name, "-r", revision, "-B"]
        self.run_async(args, _make_success_callback(callback))

    def bookmark_move(self, name, revision, callback):
        """Move an existing bookmark to a new revision."""
        args = ["bookmark", "move", name, "--to", revision, "-B"]
        self.run_async(args, _make_success_callback(callback))

    def bookmark_delete(self, names, callback):
        """Delete one or more bookmarks."""
        args = ["bookmark", "delete"] + list(names)
        self.run_async(args, _make_success_callback(callback))

    def bookmark_rename(self, old_name, new_name, callback):
        """Rename a bookmark."""
        args = ["bookmark", "rename", old_name, new_name]
        self.run_async(args, _make_success_callback(callback))

    def git_push_change(self, revision, callback):
        """Push a change by creating a bookmark (jj git push -c).

        Callback receives (success, error, bookmark_name, pr_url).
        """

        def on_result(result):
            bookmark_name = None
            pr_url = None

            # Parse output for bookmark name
            # Format: "Creating bookmark X for revision Y"
            output = result.stdout + result.stderr
            for line in output.split("\n"):
                if "Creating bookmark" in line or "bookmark" in line.lower():
                    # Try to extract bookmark name
                    match = re.search(r"Creating bookmark (\S+)", line)
                    if match:
                        bookmark_name = match.group(1)

                # Look for GitHub PR URL
                if "github.com" in line and "/pull/new/" in line:
                    # Extract URL from line
                    match = re.search(r"(https://github\.com/\S+/pull/new/\S+)", line)
                    if match:
                        pr_url = match.group(1)

            callback(
                result.success,
                result.stderr if not result.success else "",
                bookmark_name,
                pr_url,
            )

        args = ["git", "push", "-c", revision]
        self.run_async(args, on_result)

    def git_fetch(self, callback):
        """Fetch from git remote."""
        self.run_async(["git", "fetch"], _make_success_callback(callback))

    def git_push(self, callback):
        """Push all tracked bookmarks pointing to ancestors of @.

        Callback receives (success, message) where message is jj's summary
        line on success (e.g. which bookmarks moved) or stderr on failure.
        """

        def on_result(result):
            if not result.success:
                callback(False, result.stderr)
                return
            output = (result.stderr or result.stdout).strip()
            summary = output.split("\n")[0] if output else "Push complete"
            callback(True, summary)

        self.run_async(["git", "push"], on_result)

    def duplicate(self, callback, revision=None):
        """Duplicate a change in place (default: the current change)."""
        args = ["duplicate"]
        if revision:
            args.append(revision)
        self.run_async(args, _make_success_callback(callback))

    def revert(self, revision, callback):
        """Create a new change on top of @ undoing the given revision."""
        args = ["revert", "-r", revision, "--onto", "@"]
        self.run_async(args, _make_success_callback(callback))

    def rebase_stack_to_trunk(self, callback):
        """Rebase current stack onto trunk.

        Runs: jj rebase -d trunk() -s roots(trunk()..stack(@))
        Requires trunk() and stack() revset aliases to be configured.
        """
        args = ["rebase", "-d", "trunk()", "-s", "roots(trunk()..stack(@))"]
        self.run_async(args, _make_success_callback(callback))

    def _run_with_diff_editor(self, diff_content, jj_args, callback, reverse=False):
        """Run a jj command with a diff editor script.

        Creates a shell script that applies the given diff and uses it as the
        diff editor for jj commands like split and squash --interactive.

        jj's diff editor receives two directories: left (original) and right (changed).
        The script:
        1. Copies left to right (baseline - deselects all changes)
        2. Applies the selected diff using patch

        With reverse=True the selected diff is reverse-applied instead. This
        is used for restore --interactive, where jj presents left=current and
        right=restored: resetting right to left and reverse-applying the
        selection discards exactly the selected hunks.

        Args:
            diff_content: The diff to apply
            jj_args: Additional jj command arguments (e.g., ["split"] or
                     ["squash", "--interactive", "--from", "@", "--into", "@-"])
            callback: Called with (success, error_message)
            reverse: Reverse-apply the diff (patch -R)
        """
        task_generation = _generation

        # Create temp file for the diff
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".diff", delete=False
        ) as diff_file:
            diff_file.write(diff_content)
            diff_path = diff_file.name

        # Create a shell script that acts as the diff editor
        # jj calls: script <left_dir> <right_dir>
        script_content = f"""#!/bin/bash
LEFT="$1"
RIGHT="$2"
# Copy left to right (baseline - deselects all changes)
rm -rf "$RIGHT"/*
cp -r "$LEFT"/* "$RIGHT"/ 2>/dev/null || true
# Apply selected diff to right directory
# Use -p1 to strip the a/ b/ prefix from git diffs
patch {"-R " if reverse else ""}-d "$RIGHT" -p1 --no-backup-if-mismatch < {shlex.quote(diff_path)} 2>/dev/null
exit 0
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False
        ) as script_file:
            script_file.write(script_content)
            script_path = script_file.name

        os.chmod(script_path, 0o755)

        def cleanup_temp_files():
            for path in (diff_path, script_path):
                try:
                    os.unlink(path)
                except OSError:
                    pass

        def run_and_cleanup(result):
            cleanup_temp_files()
            callback(result.success, result.stderr if not result.success else "")

        def execute():
            try:
                cmd = [self.jj_path] + jj_args + ["--tool", script_path]
                process = subprocess.Popen(
                    cmd,
                    cwd=self.repo_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    env={**os.environ, "NO_COLOR": "1"},
                    startupinfo=_get_startupinfo(),
                )
                stdout, stderr = process.communicate(timeout=30)
                result = JJResult(
                    success=process.returncode == 0,
                    stdout=stdout.decode("utf-8", errors="replace"),
                    stderr=stderr.decode("utf-8", errors="replace"),
                    returncode=process.returncode,
                )
                if task_generation == _generation:
                    sublime.set_timeout(lambda: run_and_cleanup(result), 0)
                else:
                    cleanup_temp_files()
            except subprocess.TimeoutExpired:
                process.kill()
                result = JJResult(
                    success=False,
                    stdout="",
                    stderr="Command timed out",
                    returncode=-1,
                )
                if task_generation == _generation:
                    sublime.set_timeout(lambda: run_and_cleanup(result), 0)
                else:
                    cleanup_temp_files()
            except Exception as e:
                result = JJResult(
                    success=False, stdout="", stderr=str(e), returncode=-1
                )
                if task_generation == _generation:
                    sublime.set_timeout(lambda: run_and_cleanup(result), 0)
                else:
                    cleanup_temp_files()

        _get_executor().submit(execute)

    def split_with_diff(self, diff_content, callback):
        """Split current change using diff content to select first part."""
        self._run_with_diff_editor(diff_content, ["split"], callback)

    def absorb_interactive(self, diff_content, callback, from_rev=None):
        """Absorb selected changes into ancestor commits.

        Only the hunks present in diff_content are considered for
        absorption. Requires jj 0.44 or later.
        """
        args = ["absorb", "--interactive"]
        if from_rev:
            args.extend(["--from", from_rev])
        self._run_with_diff_editor(diff_content, args, callback)

    def restore_paths(self, paths, callback):
        """Restore the given paths in the working copy from its parent(s).

        Discards working copy changes to those paths.
        """
        args = ["restore", "--"] + list(paths)
        self.run_async(args, _make_success_callback(callback))

    def restore_interactive(self, diff_content, callback):
        """Discard the changes in diff_content from the working copy.

        Uses jj restore --interactive; the hunks present in diff_content
        are restored to their parent state, everything else is kept.
        """
        self._run_with_diff_editor(
            diff_content, ["restore", "--interactive"], callback, reverse=True
        )

    def squash_interactive(self, diff_content, source, destination, callback):
        """Squash selected changes from source into destination.

        Args:
            diff_content: The diff representing selected changes
            source: Source revision to squash from
            destination: Destination revision to squash into
            callback: Called with (success, error_message)
        """
        self._run_with_diff_editor(
            diff_content,
            ["squash", "--interactive", "--from", source, "--into", destination],
            callback,
        )

    def _parse_change_info(self, line):
        """Parse a line of template output into ChangeInfo."""
        parts = line.split(self.FIELD_SEP)
        if len(parts) < 9:
            return None

        # Extract prefix/rest if available (fields 9 and 10)
        change_id_prefix = parts[9] if len(parts) > 9 else parts[0]
        change_id_rest = parts[10] if len(parts) > 10 else ""

        return ChangeInfo(
            change_id=parts[0],
            commit_id=parts[1],
            description=parts[2] or "(no description)",
            author=parts[3],
            timestamp=parts[4],
            is_empty=parts[5] == "true",
            is_immutable=parts[6] == "true",
            is_working_copy=parts[7] == "true",
            bookmarks=[b for b in parts[8].split(",") if b],
            change_id_prefix=change_id_prefix,
            change_id_rest=change_id_rest,
            has_conflict=len(parts) > 11 and parts[11] == "true",
        )

    def _parse_git_diff(self, diff_output, target_file=None):
        """Parse git-format diff output into hunks."""
        hunks = []
        current_file = None
        in_hunk = False
        current_hunk_lines = []
        hunk_header = None

        for line in diff_output.split("\n"):
            # New file in diff
            if line.startswith("diff --git"):
                # Save any previous hunk
                if hunk_header and (target_file is None or current_file == target_file):
                    hunk = self._create_hunk(hunk_header, current_hunk_lines)
                    if hunk:
                        hunks.append(hunk)
                current_hunk_lines = []
                hunk_header = None
                in_hunk = False

                # Extract file path (format: diff --git a/path b/path)
                parts = line.split(" ")
                if len(parts) >= 4:
                    current_file = parts[2][2:]  # Remove 'a/' prefix

            # Hunk header
            elif line.startswith("@@"):
                # Save any previous hunk
                if hunk_header and (target_file is None or current_file == target_file):
                    hunk = self._create_hunk(hunk_header, current_hunk_lines)
                    if hunk:
                        hunks.append(hunk)
                current_hunk_lines = []

                # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
                header_match = self._parse_hunk_header(line)
                if header_match:
                    hunk_header = header_match
                    in_hunk = True
                else:
                    hunk_header = None
                    in_hunk = False

            # Hunk content
            elif in_hunk and (
                line.startswith("+") or line.startswith("-") or line.startswith(" ")
            ):
                current_hunk_lines.append(line)

        # Don't forget the last hunk
        if hunk_header and (target_file is None or current_file == target_file):
            hunk = self._create_hunk(hunk_header, current_hunk_lines)
            if hunk:
                hunks.append(hunk)

        return hunks

    def _parse_hunk_header(self, line):
        """Parse @@ -old_start,old_count +new_start,new_count @@ format."""
        match = HUNK_HEADER_RE.match(line)
        if not match:
            return None

        old_start = int(match.group(1))
        old_count = int(match.group(2)) if match.group(2) else 1
        new_start = int(match.group(3))
        new_count = int(match.group(4)) if match.group(4) else 1

        return (old_start, old_count, new_start, new_count)

    def _create_hunk(self, header, lines):
        """Create a DiffHunk from parsed header and lines."""
        old_start, old_count, new_start, new_count = header

        # Determine hunk type
        has_additions = any(line.startswith("+") for line in lines)
        has_deletions = any(line.startswith("-") for line in lines)

        if has_additions and has_deletions:
            hunk_type = "modified"
        elif has_additions:
            hunk_type = "added"
        elif has_deletions:
            hunk_type = "deleted"
        else:
            return None

        return DiffHunk(
            old_start=old_start,
            old_count=old_count,
            new_start=new_start,
            new_count=new_count,
            hunk_type=hunk_type,
            lines=lines,
        )


def shutdown_executor():
    """Shutdown the thread pool executor."""
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=False)
        _executor = None
