"""Event listeners for the persistent log view."""

import sublime
import sublime_plugin

from ..views.log_view import LOG_VIEW_SETTING, cleanup_log_view, is_log_view


class LogViewEventListener(sublime_plugin.ViewEventListener):
    """Lifecycle handling for log views."""

    @classmethod
    def is_applicable(cls, settings):
        """Only attach to log views."""
        return settings.get(LOG_VIEW_SETTING, False)

    def on_close(self):
        """Drop cached state when the view closes."""
        cleanup_log_view(self.view.id())


class LogViewInputHandler(sublime_plugin.EventListener):
    """Blocks editing commands and provides the keybinding context."""

    BLOCKED_COMMANDS = {
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

    def on_text_command(self, view, command_name, args):
        """Keep the log view read-only."""
        if not is_log_view(view):
            return None
        if command_name in self.BLOCKED_COMMANDS:
            return ("noop", None)
        return None

    def on_query_context(self, view, key, operator, operand, match_all):
        """Provide the jj_log_view context for keybindings."""
        if key == "jj_log_view":
            active = is_log_view(view)
            if operator == sublime.OP_EQUAL:
                return active == operand
            elif operator == sublime.OP_NOT_EQUAL:
                return active != operand
        return None
