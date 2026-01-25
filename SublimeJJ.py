"""SublimeJJ - Jujutsu (jj) integration for Sublime Text.

This is the main entry point for the plugin, providing:
- Status bar with current change ID and description
- Quick commands via command palette
"""

import sublime

from .commands.quick_commands import (  # noqa: F401
    JjAbandonCommand,
    JjAbsorbCommand,
    JjBookmarkDeleteCommand,
    JjBookmarkListCommand,
    JjBookmarkMoveCommand,
    JjBookmarkRenameCommand,
    JjBookmarkSetCommand,
    JjCommitCommand,
    JjDescribeCommand,
    JjEditCommand,
    JjGitPushChangeCommand,
    JjLogCommand,
    JjNewCommand,
    JjPullRetrunkCommand,
    JjQuickSquashCommand,
    JjRebaseCommand,
    JjRefreshCommand,
    JjSquashCommand,
    JjUndoCommand,
)
from .core.jj_cli import init_executor, shutdown_executor
from .listeners.file_events import JjEventListener  # noqa: F401

# Plugin version
__version__ = "0.1.0"


def plugin_loaded():
    """Called when the plugin is loaded."""
    init_executor()

    settings = sublime.load_settings("SublimeJJ.sublime-settings")

    # Log startup
    if settings.get("debug", False):
        print(f"SublimeJJ {__version__} loaded")


def plugin_unloaded():
    """Called when the plugin is unloaded."""
    # Shutdown the thread pool
    shutdown_executor()
