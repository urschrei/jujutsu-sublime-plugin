"""Jujutsu - Jujutsu (jj) integration for Sublime Text.

This is the main entry point for the plugin, providing:
- Status bar with current change ID and description
- Quick commands via command palette
"""

import sublime

from .commands.conflict_commands import (  # noqa: F401
    JjConflictedFilesCommand,
    JjConflictsCommand,
)
from .commands.log_view_commands import (  # noqa: F401
    JjLogViewAbandonCommand,
    JjLogViewCommand,
    JjLogViewDescribeCommand,
    JjLogViewEditCommand,
    JjLogViewHelpCommand,
    JjLogViewNewCommand,
    JjLogViewRefreshCommand,
    JjLogViewReplaceCommand,
)
from .commands.oplog_commands import JjOpLogCommand  # noqa: F401
from .commands.quick_commands import (  # noqa: F401
    JjAbandonCommand,
    JjAbsorbCommand,
    JjAbsorbInteractiveCommand,
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
    JjSquashInteractiveCommand,
    JjUndoCommand,
)
from .commands.restore_commands import (  # noqa: F401
    JjDiscardInteractiveCommand,
    JjRestoreFileCommand,
)
from .commands.split_command import (  # noqa: F401
    JjSplitCancelCommand,
    JjSplitCollapseCommand,
    JjSplitCommand,
    JjSplitConfirmCommand,
    JjSplitDeselectAllCommand,
    JjSplitExpandCommand,
    JjSplitNavNextCommand,
    JjSplitNavPrevCommand,
    JjSplitSelectAllCommand,
    JjSplitToggleCommand,
)
from .core.jj_cli import init_executor, shutdown_executor
from .listeners.file_events import JjEventListener  # noqa: F401
from .listeners.log_view_events import (  # noqa: F401
    LogViewEventListener,
    LogViewInputHandler,
)
from .listeners.split_events import (  # noqa: F401
    SplitViewEventListener,
    SplitViewInputHandler,
)

# Plugin version
__version__ = "0.3.0"


def plugin_loaded():
    """Called when the plugin is loaded."""
    init_executor()

    settings = sublime.load_settings("Jujutsu.sublime-settings")

    # Log startup
    if settings.get("debug", False):
        print(f"Jujutsu {__version__} loaded")


def plugin_unloaded():
    """Called when the plugin is unloaded."""
    # Shutdown the thread pool
    shutdown_executor()
