"""Persistent read-only view showing the jj log graph."""

import sublime

from ..core.formatting import build_log_line_map
from ..core.repo import get_repo_manager

LOG_VIEW_SETTING = "jj_log_view"
LOG_VIEW_REPO_SETTING = "jj_log_view_repo"
LOG_VIEW_NAME = "JJ Log"

SETTINGS_FILE = "Jujutsu.sublime-settings"

# view id -> change id per buffer line (None before the first header)
_line_maps = {}


def is_log_view(view):
    """Check whether a view is a jj log view."""
    return bool(view.settings().get(LOG_VIEW_SETTING, False))


def get_cli_for_log_view(view):
    """Get the JJCli instance for a log view."""
    repo_root = view.settings().get(LOG_VIEW_REPO_SETTING)
    if not repo_root:
        return None
    return get_repo_manager().get_cli_for_root(repo_root)


def cleanup_log_view(view_id):
    """Drop cached state for a closed log view."""
    _line_maps.pop(view_id, None)


def find_log_view(window, repo_root):
    """Find an existing log view for the repository in the window."""
    for view in window.views():
        if (
            is_log_view(view)
            and view.settings().get(LOG_VIEW_REPO_SETTING) == repo_root
        ):
            return view
    return None


def open_log_view(window, repo_root):
    """Open (or focus) the log view for a repository and render it."""
    view = find_log_view(window, repo_root)
    if view is None:
        view = window.new_file()
        view.set_name(LOG_VIEW_NAME)
        view.set_scratch(True)
        settings = view.settings()
        settings.set(LOG_VIEW_SETTING, True)
        settings.set(LOG_VIEW_REPO_SETTING, repo_root)
        settings.set("word_wrap", False)
        settings.set("line_numbers", False)
        settings.set("gutter", False)
        settings.set("draw_white_space", "none")
        settings.set("caret_style", "solid")
        settings.set("command_mode", False)
        _assign_log_syntax(view)
        view.set_read_only(True)
    window.focus_view(view)
    render_log_view(view)
    return view


def render_log_view(view):
    """Fetch the log and (re)draw the view contents."""
    cli = get_cli_for_log_view(view)
    if cli is None:
        return

    settings = sublime.load_settings(SETTINGS_FILE)
    revset = settings.get("log_view_revset") or None
    limit = settings.get("log_view_limit", 200)

    def on_graph(success, text_or_error, change_ids):
        if not view.is_valid():
            return
        if not success:
            sublime.status_message(f"jj: failed to load log: {text_or_error}")
            return

        _line_maps[view.id()] = build_log_line_map(text_or_error, change_ids)

        viewport = view.viewport_position()
        view.set_read_only(False)
        view.run_command("jj_log_view_replace", {"content": text_or_error})
        view.set_read_only(True)
        sublime.set_timeout(lambda: view.set_viewport_position(viewport, False), 0)

    cli.get_log_graph(on_graph, revset=revset, limit=limit)


def _assign_log_syntax(view):
    """Assign the bundled JJ Log syntax to the view.

    The package name is derived from this module's import path so the
    syntax resolves regardless of the installed package directory name.
    """
    package = __name__.split(".")[0]
    try:
        view.assign_syntax(f"Packages/{package}/JJLog.sublime-syntax")
    except Exception:
        # Fall back to plain text if the syntax cannot be resolved
        pass


def get_change_id_for_cursor(view):
    """Return the change id of the log entry under the cursor, or None."""
    line_map = _line_maps.get(view.id())
    if not line_map:
        return None
    selection = view.sel()
    if not selection:
        return None
    row, _ = view.rowcol(selection[0].begin())
    if row >= len(line_map):
        return None
    return line_map[row]
