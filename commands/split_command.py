"""Commands for split selection UI."""

from __future__ import annotations

import sublime_plugin

from ..views.split_selection import (
    SplitViewManager,
    get_manager_for_view,
    is_split_view,
)
from .base import JjWindowCommand


class JjSplitCommand(JjWindowCommand):
    """Split the current change interactively.

    Opens a phantom-based UI for selecting which changes go into the first commit.
    """

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli
        self.show_status("Loading diff...")

        # Fetch the current diff
        cli.get_diff_raw(self._on_diff_loaded)

    def _on_diff_loaded(self, success: bool, result: str) -> None:
        if not success:
            self.show_error(f"Failed to get diff: {result}")
            return

        diff_text = result.strip()
        if not diff_text:
            self.show_status("Nothing to split (no changes)")
            return

        # Check for actual content
        if "diff --git" not in diff_text:
            self.show_status("Nothing to split (no changes)")
            return

        try:
            SplitViewManager(
                window=self.window,
                cli=self.cli,
                diff_text=diff_text,
                on_complete=self._on_split_complete,
                on_cancel=self._on_split_cancel,
            )
        except ValueError as e:
            self.show_error(str(e))

    def _on_split_complete(self, filtered_diff: str) -> None:
        """Execute the split with the selected changes."""
        self.show_status("Splitting change...")

        def on_result(success: bool, error: str) -> None:
            if success:
                self.show_status("Change split successfully")
                # Refresh all views to update status bars
                from .quick_commands import refresh_all_views

                refresh_all_views(self.window)
            else:
                self.show_error(f"Failed to split: {error}")

        self.cli.split_with_diff(filtered_diff, on_result)

    def _on_split_cancel(self) -> None:
        """Handle split cancellation."""
        self.show_status("Split cancelled")


# Navigation commands for split view
# These are text commands that operate on the current view


class JjSplitNavNextCommand(sublime_plugin.TextCommand):
    """Smart navigation: next line if in expanded hunk, next hunk otherwise."""

    def run(self, edit):
        manager = get_manager_for_view(self.view)
        if manager:
            manager.nav_next()

    def is_enabled(self):
        return is_split_view(self.view)


class JjSplitNavPrevCommand(sublime_plugin.TextCommand):
    """Smart navigation: prev line if in expanded hunk, prev hunk otherwise."""

    def run(self, edit):
        manager = get_manager_for_view(self.view)
        if manager:
            manager.nav_prev()

    def is_enabled(self):
        return is_split_view(self.view)


class JjSplitExpandCommand(sublime_plugin.TextCommand):
    """Expand current hunk and enter it."""

    def run(self, edit):
        manager = get_manager_for_view(self.view)
        if manager:
            manager.expand_current()

    def is_enabled(self):
        return is_split_view(self.view)


class JjSplitCollapseCommand(sublime_plugin.TextCommand):
    """Collapse current hunk and exit to hunk level."""

    def run(self, edit):
        manager = get_manager_for_view(self.view)
        if manager:
            manager.collapse_current()

    def is_enabled(self):
        return is_split_view(self.view)


class JjSplitToggleCommand(sublime_plugin.TextCommand):
    """Toggle selection of current item in split view."""

    def run(self, edit):
        manager = get_manager_for_view(self.view)
        if manager:
            manager.toggle_current()

    def is_enabled(self):
        return is_split_view(self.view)


class JjSplitSelectAllCommand(sublime_plugin.TextCommand):
    """Select all selectable lines in split view."""

    def run(self, edit):
        manager = get_manager_for_view(self.view)
        if manager:
            manager.select_all()

    def is_enabled(self):
        return is_split_view(self.view)


class JjSplitDeselectAllCommand(sublime_plugin.TextCommand):
    """Deselect all lines in split view."""

    def run(self, edit):
        manager = get_manager_for_view(self.view)
        if manager:
            manager.deselect_all()

    def is_enabled(self):
        return is_split_view(self.view)


class JjSplitConfirmCommand(sublime_plugin.TextCommand):
    """Confirm the split operation."""

    def run(self, edit):
        manager = get_manager_for_view(self.view)
        if manager:
            manager.confirm()

    def is_enabled(self):
        return is_split_view(self.view)


class JjSplitCancelCommand(sublime_plugin.TextCommand):
    """Cancel the split operation."""

    def run(self, edit):
        manager = get_manager_for_view(self.view)
        if manager:
            manager.cancel()

    def is_enabled(self):
        return is_split_view(self.view)
