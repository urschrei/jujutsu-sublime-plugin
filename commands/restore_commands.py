"""Commands for restoring (discarding) working copy changes."""

import os

import sublime

from .base import JjWindowCommand
from .helpers import KIND_ACTION, refresh_all_views


class JjRestoreFileCommand(JjWindowCommand):
    """Restore the current file to its parent-revision state.

    Discards all working copy changes to the file (undoable via the
    operation log).
    """

    def run(self):
        cli = self.get_cli()
        repo_root = self.get_repo_root()
        if cli is None or repo_root is None:
            return

        view = self.window.active_view()
        if view is None or view.file_name() is None:
            self.show_status("No file to restore")
            return

        if view.is_dirty():
            self.show_error(
                "The file has unsaved changes. Save or revert it before restoring."
            )
            return

        file_path = view.file_name()
        rel_path = os.path.relpath(file_path, repo_root)
        if rel_path.startswith(".."):
            self.show_status("File is not inside the repository")
            return

        def on_confirm(confirmed):
            if not confirmed:
                self.show_status("Restore cancelled")
                return

            def on_result(success, error):
                if success:
                    self.show_status(f"Restored {rel_path}")
                    refresh_all_views(self.window)
                else:
                    self.show_error(f"Failed to restore: {error}")

            cli.restore_paths([rel_path], on_result)

        self.window.show_quick_panel(
            [
                sublime.QuickPanelItem(
                    trigger=f"Restore {rel_path}",
                    details="Discard all working copy changes to this file",
                    annotation="undoable via the operation log",
                    kind=KIND_ACTION,
                ),
                sublime.QuickPanelItem(
                    trigger="Cancel",
                    details="Keep the changes",
                    kind=KIND_ACTION,
                ),
            ],
            lambda idx: on_confirm(idx == 0),
            placeholder="Restore file from parent revision?",
        )


class JjDiscardInteractiveCommand(JjWindowCommand):
    """Interactively choose hunks/lines to discard from the working copy.

    Opens the diff selection UI; the selected changes are restored to
    their parent-revision state, everything else is kept.
    """

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli
        self.show_status("Loading diff...")
        cli.get_diff_raw(self._on_diff_loaded)

    def _on_diff_loaded(self, success: bool, result: str) -> None:
        if not success:
            self.show_error(f"Failed to get diff: {result}")
            return

        diff_text = result.strip()
        if not diff_text or "diff --git" not in diff_text:
            self.show_status("Nothing to discard (no changes)")
            return

        from ..views.split_selection import SplitViewManager

        try:
            SplitViewManager(
                window=self.window,
                cli=self.cli,
                diff_text=diff_text,
                on_complete=self._on_discard_complete,
                on_cancel=self._on_discard_cancel,
                title="JJ Discard: Select changes to discard",
            )
        except ValueError as e:
            self.show_error(str(e))

    def _on_discard_complete(self, filtered_diff: str) -> None:
        """Discard the selected changes."""
        self.show_status("Discarding selected changes...")

        def on_result(success: bool, error: str) -> None:
            if success:
                self.show_status("Selected changes discarded")
                refresh_all_views(self.window)
            else:
                self.show_error(f"Failed to discard: {error}")

        self.cli.restore_interactive(filtered_diff, on_result)

    def _on_discard_cancel(self) -> None:
        """Handle discard cancellation."""
        self.show_status("Discard cancelled")
