"""File event listeners with debouncing."""

import time

import sublime
import sublime_plugin

from ..core.repo import get_repo_manager
from ..views.status_bar import update_status_bar


class Debouncer:
    """Simple debouncer for view updates."""

    def __init__(self, delay=0.5):
        self._delay = delay
        self._pending = {}

    def should_run(self, view_id):
        """Check if enough time has passed to run the update."""
        now = time.time()
        last_time = self._pending.get(view_id, 0)

        if now - last_time >= self._delay:
            self._pending[view_id] = now
            return True
        return False

    def schedule(self, view, callback):
        """Schedule a debounced callback."""
        view_id = view.id()
        self._pending[view_id] = time.time()

        def run_if_ready():
            if self.should_run(view_id):
                callback()

        # Schedule callback after delay
        sublime.set_timeout(run_if_ready, int(self._delay * 1000))


# Global debouncer instance
_debouncer = Debouncer()


def get_debounce_delay():
    """Get the debounce delay from settings."""
    settings = sublime.load_settings("SublimeJJ.sublime-settings")
    return settings.get("debounce_delay", 0.5)


class JjEventListener(sublime_plugin.EventListener):
    """Event listener for jj integration."""

    def on_activated(self, view):
        """Called when a view gains focus."""
        if view is None or view.window() is None:
            return

        # Skip special views (panels, consoles, etc.)
        if view.settings().get("is_widget", False):
            return

        settings = sublime.load_settings("SublimeJJ.sublime-settings")

        # Update status bar
        if settings.get("status_bar_enabled", True):
            update_status_bar(view)

    def on_post_save_async(self, view):
        """Called after a view is saved (async)."""
        if view is None:
            return

        file_path = view.file_name()
        if file_path is None:
            return

        # Invalidate cache for this file
        get_repo_manager().invalidate_file(file_path)

        settings = sublime.load_settings("SublimeJJ.sublime-settings")

        # Debounced updates
        def do_update():
            if settings.get("status_bar_enabled", True):
                update_status_bar(view)

        _debouncer._delay = get_debounce_delay()
        _debouncer.schedule(view, do_update)

    def on_load(self, view):
        """Called when a file is loaded."""
        if view is None or view.window() is None:
            return

        # Skip special views
        if view.settings().get("is_widget", False):
            return

        settings = sublime.load_settings("SublimeJJ.sublime-settings")

        if settings.get("status_bar_enabled", True):
            update_status_bar(view)
