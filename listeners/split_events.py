"""Event listener for split selection views."""

from __future__ import annotations

import sublime_plugin

from ..views.split_selection import get_manager_for_view, is_split_view

print("[SublimeJJ] split_events.py loaded")


class SplitViewEventListener(sublime_plugin.ViewEventListener):
    """Event listener for split selection views.

    Handles view lifecycle events like close.
    """

    @classmethod
    def is_applicable(cls, settings):
        """Only attach to split selection views."""
        return settings.get("jj_split_view", False)

    def on_close(self):
        """Handle view close - clean up manager."""
        manager = get_manager_for_view(self.view)
        if manager:
            # Clean up without calling close() again (view is already closing)
            from ..views.split_selection import _active_managers

            if self.view.id() in _active_managers:
                del _active_managers[self.view.id()]


class SplitViewInputHandler(sublime_plugin.EventListener):
    """Global event listener to handle input in split views."""

    def on_text_command(self, view, command_name, args):
        """Intercept text commands in split views.

        Blocks editing commands to keep the view read-only.
        Navigation is handled by keybindings in Default.sublime-keymap.
        """
        if not is_split_view(view):
            return None

        # Block insert/delete commands
        blocked_commands = {
            "insert",
            "insert_snippet",
            "left_delete",
            "right_delete",
            "delete_word",
            "paste",
            "cut",
            "undo",
            "redo",
            "redo_or_repeat",
        }

        if command_name in blocked_commands:
            # Return a no-op to block the command
            return ("noop", None)

        return None

    def on_query_context(self, view, key, operator, operand, match_all):
        """Provide context for keybindings.

        Allows keybindings to check if we're in a split view.
        """
        import sublime

        if key == "jj_split_view":
            is_split = is_split_view(view)
            if operator == sublime.OP_EQUAL:
                return is_split == operand
            elif operator == sublime.OP_NOT_EQUAL:
                return is_split != operand
        return None
