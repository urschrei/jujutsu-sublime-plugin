"""Shared helpers for building quick panel items from jj data."""

import sublime

from ..core.formatting import format_change_details
from ..views.status_bar import update_status_bar

# Kind tuples for QuickPanelItem visual styling
KIND_CHANGE = (sublime.KIND_ID_VARIABLE, "C", "Change")
KIND_WORKING_COPY = (sublime.KIND_ID_FUNCTION, "@", "Working Copy")
KIND_BOOKMARK = (sublime.KIND_ID_MARKUP, "B", "Bookmark")
KIND_ACTION = (sublime.KIND_ID_SNIPPET, ">", "Action")

# Default limit for log queries
DEFAULT_LOG_LIMIT = 50


def build_change_annotations(change, include_immutable=True):
    """Build annotation list for a change.

    Returns a list of annotation strings for display in quick panels.
    """
    annotations = []
    if change.is_empty:
        annotations.append("empty")
    if include_immutable and change.is_immutable:
        annotations.append("immutable")
    if change.bookmarks:
        annotations.append(", ".join(change.bookmarks))
    return annotations


def build_change_quick_panel_item(
    change, extra_annotations=None, include_immutable=True
):
    """Build a QuickPanelItem for a change.

    Args:
        change: ChangeInfo object
        extra_annotations: Optional list of additional annotations to prepend
        include_immutable: Whether to include 'immutable' in annotations

    Returns:
        sublime.QuickPanelItem configured for the change
    """
    annotations = extra_annotations[:] if extra_annotations else []
    annotations.extend(build_change_annotations(change, include_immutable))

    return sublime.QuickPanelItem(
        trigger=change.change_id,
        details=format_change_details(change),
        annotation=" | ".join(annotations) if annotations else "",
        kind=KIND_WORKING_COPY if change.is_working_copy else KIND_CHANGE,
    )


def refresh_all_views(window):
    """Refresh status bar for all views in a window."""
    for view in window.views():
        update_status_bar(view)
