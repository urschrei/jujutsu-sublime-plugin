"""Base command classes for SublimeJJ."""

import sublime
import sublime_plugin

from ..core.repo import get_repo_manager


class JjCommandMixin:
    """Mixin providing shared functionality for jj commands."""

    def is_enabled(self):
        """Command is enabled only in jj repositories."""
        return self.get_cli() is not None

    def show_error(self, message):
        """Show an error message."""
        sublime.error_message(f"SublimeJJ: {message}")

    def show_status(self, message):
        """Show a status message."""
        sublime.status_message(f"jj: {message}")


class JjWindowCommand(JjCommandMixin, sublime_plugin.WindowCommand):
    """Base class for jj window commands."""

    def get_cli(self):
        """Get the JJCli instance for the current window."""
        view = self.window.active_view()
        if view is None:
            return None

        file_path = view.file_name()
        if file_path is None:
            # Try to get from folders
            folders = self.window.folders()
            if folders:
                return get_repo_manager().get_cli(folders[0])
            return None

        return get_repo_manager().get_cli(file_path)

    def get_repo_root(self):
        """Get the repository root for the current window."""
        view = self.window.active_view()
        if view is None:
            return None

        file_path = view.file_name()
        if file_path is None:
            folders = self.window.folders()
            if folders:
                repo_info = get_repo_manager().find_repo_root(folders[0])
                return repo_info.root if repo_info else None
            return None

        repo_info = get_repo_manager().find_repo_root(file_path)
        return repo_info.root if repo_info else None


class JjTextCommand(JjCommandMixin, sublime_plugin.TextCommand):
    """Base class for jj text commands."""

    def get_cli(self):
        """Get the JJCli instance for the current view."""
        file_path = self.view.file_name()
        if file_path is None:
            return None

        return get_repo_manager().get_cli(file_path)

    def get_repo_root(self):
        """Get the repository root for the current view."""
        file_path = self.view.file_name()
        if file_path is None:
            return None

        repo_info = get_repo_manager().find_repo_root(file_path)
        return repo_info.root if repo_info else None
