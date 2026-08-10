"""Event listeners for the persistent log view."""

import sublime
import sublime_plugin

from ..views.log_view import (
    LOG_VIEW_SETTING,
    build_hover_html,
    cleanup_log_view,
    get_change_id_at_point,
    get_change_info,
    get_cli_for_log_view,
    is_log_view,
    update_current_entry_highlight,
)

# Maps hover popup action hrefs to log view commands
HOVER_ACTIONS = {
    "edit": "jj_log_view_edit",
    "diff": "jj_log_view_show_diff",
    "squash": "jj_log_view_squash",
    "abandon": "jj_log_view_abandon",
}

HOVER_POPUP_MAX_WIDTH = 640


class LogViewEventListener(sublime_plugin.ViewEventListener):
    """Lifecycle, hover, and highlight handling for log views."""

    @classmethod
    def is_applicable(cls, settings):
        """Only attach to log views."""
        return settings.get(LOG_VIEW_SETTING, False)

    def on_close(self):
        """Drop cached state when the view closes."""
        cleanup_log_view(self.view.id())

    def on_selection_modified(self):
        """Keep the current-entry outline in sync with the cursor."""
        update_current_entry_highlight(self.view)

    def on_hover(self, point, hover_zone):
        """Show a detail card for the hovered log entry."""
        if hover_zone != sublime.HOVER_TEXT:
            return

        view = self.view
        change_id = get_change_id_at_point(view, point)
        if change_id is None:
            return
        change = get_change_info(view, change_id)
        if change is None:
            return

        def on_navigate(action):
            view.hide_popup()
            command = HOVER_ACTIONS.get(action)
            if command is None:
                return
            # Log view commands act on the entry under the cursor
            view.sel().clear()
            view.sel().add(sublime.Region(point, point))
            view.run_command(command)

        view.show_popup(
            build_hover_html(change),
            flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
            location=point,
            max_width=HOVER_POPUP_MAX_WIDTH,
            on_navigate=on_navigate,
        )

        # Enrich the popup with the full description and diff stat once
        # they arrive
        cli = get_cli_for_log_view(view)
        if cli is None:
            return

        state = {"description": None, "diff_stat": None, "arrived": 0}

        def refresh_popup():
            if not view.is_popup_visible():
                return
            view.update_popup(
                build_hover_html(
                    change,
                    description=state["description"],
                    diff_stat=state["diff_stat"],
                )
            )

        def on_description(success, text):
            state["arrived"] += 1
            if success:
                state["description"] = text
            if state["arrived"] == 2:
                refresh_popup()

        def on_stat(success, text):
            state["arrived"] += 1
            if success:
                state["diff_stat"] = text
            if state["arrived"] == 2:
                refresh_popup()

        cli.get_description(on_description, revision=change_id)
        cli.get_diff_stat(on_stat, revision=change_id)


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
