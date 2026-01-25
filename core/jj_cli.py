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
class BookmarkInfo:
    """Information about a jj bookmark."""

    name: str
    change_id: str
    description: str


# Compiled regex for hunk header parsing
_HUNK_HEADER_RE = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

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
            max_workers=2, thread_name_prefix="sublimejj-worker"
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
        "change_id.shortest(8).rest()"
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
        'change_id.shortest(8).rest() ++ "\\n"'
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

    def get_log(self, callback, revset="::", limit=50):
        """Get commit log."""

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

    def new(self, callback, message=None):
        """Create a new change."""
        args = ["new"]
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

    def abandon(self, callback):
        """Abandon current change."""
        self.run_async(["abandon"], _make_success_callback(callback))

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

    def get_diff_raw(self, callback, revision="@"):
        """Get raw diff output for a revision."""

        def on_result(result):
            callback(result.success, result.stdout if result.success else result.stderr)

        self.run_async(["diff", "-r", revision, "--git"], on_result)

    # Bookmark template for machine-readable output
    BOOKMARK_TEMPLATE = (
        'name ++ "|||" ++ '
        'if(normal_target, normal_target.change_id().short(8), "(deleted)") ++ "|||" ++ '
        'if(normal_target, normal_target.description().first_line(), "") ++ "\\n"'
    )

    def bookmark_list(self, callback):
        """Get list of bookmarks with their targets."""

        def on_result(result):
            if not result.success:
                callback([])
                return

            bookmarks = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split(self.FIELD_SEP)
                    if len(parts) >= 3:
                        bookmarks.append(
                            BookmarkInfo(
                                name=parts[0],
                                change_id=parts[1],
                                description=parts[2] or "(no description)",
                            )
                        )
            callback(bookmarks)

        self.run_async(["bookmark", "list", "-T", self.BOOKMARK_TEMPLATE], on_result)

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

    def rebase_stack_to_trunk(self, callback):
        """Rebase current stack onto trunk.

        Runs: jj rebase -d trunk() -s roots(trunk()..stack(@))
        Requires trunk() and stack() revset aliases to be configured.
        """
        args = ["rebase", "-d", "trunk()", "-s", "roots(trunk()..stack(@))"]
        self.run_async(args, _make_success_callback(callback))

    def split_with_diff(self, diff_content, callback):
        """Split current change using diff content to select first part.

        Uses a script as JJ_EDITOR that outputs the pre-selected diff content.
        """
        task_generation = _generation

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".diff", delete=False
        ) as temp_file:
            temp_file.write(diff_content)
            temp_path = temp_file.name

        env = os.environ.copy()
        env["NO_COLOR"] = "1"
        env["JJ_EDITOR"] = f"cat {shlex.quote(temp_path)}"

        def run_and_cleanup(result):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            callback(result.success, result.stderr if not result.success else "")

        def execute():
            try:
                process = subprocess.Popen(
                    [self.jj_path, "split"],
                    cwd=self.repo_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
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
                    # Still clean up temp file even if callback is stale
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass
            except Exception as e:
                result = JJResult(
                    success=False, stdout="", stderr=str(e), returncode=-1
                )
                if task_generation == _generation:
                    sublime.set_timeout(lambda: run_and_cleanup(result), 0)
                else:
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass

        _get_executor().submit(execute)

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
        match = _HUNK_HEADER_RE.match(line)
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
