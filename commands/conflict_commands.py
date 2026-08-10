"""Commands for finding and resolving conflicts."""

import os
import re

import sublime

from .base import JjWindowCommand
from .helpers import (
    KIND_CONFLICT,
    build_change_quick_panel_item,
    refresh_all_views,
)

# Revset for mutable changes containing conflicted files
CONFLICTS_REVSET = "mutable() & conflicts()"

# Matches the start of a jj conflict marker line, e.g.
# "<<<<<<< conflict 1 of 2"
CONFLICT_MARKER_RE = re.compile(r"^<{7}")


def find_first_conflict_line(file_path):
    """Return the 1-based line number of the first conflict marker, or None."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for lineno, line in enumerate(f, start=1):
                if CONFLICT_MARKER_RE.match(line):
                    return lineno
    except OSError:
        return None
    return None


def open_at_first_conflict(window, repo_root, rel_path):
    """Open a file, positioning the cursor at its first conflict marker."""
    abs_path = os.path.join(repo_root, rel_path)
    line = find_first_conflict_line(abs_path)
    if line is not None:
        window.open_file(f"{abs_path}:{line}:1", sublime.ENCODED_POSITION)
    else:
        window.open_file(abs_path)


class JjConflictedFilesCommand(JjWindowCommand):
    """List conflicted files in the working copy and jump to their markers."""

    def run(self):
        cli = self.get_cli()
        repo_root = self.get_repo_root()
        if cli is None or repo_root is None:
            return

        def on_files(success, files_or_error):
            if not success:
                self.show_error(f"Failed to list conflicts: {files_or_error}")
                return

            files = files_or_error
            if not files:
                self.show_status("No conflicts in the working copy")
                return

            items = [
                sublime.QuickPanelItem(
                    trigger=f.path,
                    annotation=f.description,
                    kind=KIND_CONFLICT,
                )
                for f in files
            ]

            def on_select(idx):
                if idx < 0:
                    return
                open_at_first_conflict(self.window, repo_root, files[idx].path)

            self.window.show_quick_panel(
                items, on_select, placeholder="Open conflicted file"
            )

        cli.resolve_list(on_files)


class JjConflictsCommand(JjWindowCommand):
    """Browse conflicted changes; select one to edit it and open its files."""

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli

        def on_log(changes):
            if not changes:
                self.show_status("No conflicted changes")
                return

            items = [build_change_quick_panel_item(c) for c in changes]

            def on_select(idx):
                if idx < 0:
                    return

                selected = changes[idx]
                if selected.is_working_copy:
                    self.window.run_command("jj_conflicted_files")
                    return

                def on_edit(success, error):
                    if not success:
                        self.show_error(f"Failed to edit: {error}")
                        return
                    self.show_status(f"Now editing {selected.change_id}")
                    refresh_all_views(self.window)
                    self.window.run_command("jj_conflicted_files")

                self.cli.edit(selected.change_id, on_edit)

            self.window.show_quick_panel(
                items,
                on_select,
                placeholder="Select conflicted change to resolve",
            )

        cli.get_log(on_log, revset=CONFLICTS_REVSET, limit=100)
