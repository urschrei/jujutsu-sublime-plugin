"""Persistent read-only view showing the jj log graph."""

import html

import sublime

from ..core.formatting import build_log_line_map
from ..core.repo import get_repo_manager

LOG_VIEW_SETTING = "jj_log_view"
LOG_VIEW_REPO_SETTING = "jj_log_view_repo"
LOG_VIEW_NAME = "JJ Log"

SETTINGS_FILE = "Jujutsu.sublime-settings"

ANNOTATION_REGION_KEY = "jj_log_annotations"
GUTTER_WC_REGION_KEY = "jj_log_gutter_wc"
GUTTER_CONFLICT_REGION_KEY = "jj_log_gutter_conflict"
CURRENT_ENTRY_REGION_KEY = "jj_log_current_entry"

# Flags for invisible regions that only carry annotations or icons
INVISIBLE = sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE

# view id -> change id per buffer line (None before the first header)
_line_maps = {}
# view id -> {change_id: ChangeInfo}
_entry_maps = {}


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
    _entry_maps.pop(view_id, None)


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
        settings.set("gutter", True)
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

    def on_graph(success, text_or_error, changes_by_id):
        if not view.is_valid():
            return
        if not success:
            sublime.status_message(f"jj: failed to load log: {text_or_error}")
            return

        _line_maps[view.id()] = build_log_line_map(text_or_error, changes_by_id)
        _entry_maps[view.id()] = changes_by_id

        viewport = view.viewport_position()
        view.set_read_only(False)
        view.run_command("jj_log_view_replace", {"content": text_or_error})
        view.set_read_only(True)
        sublime.set_timeout(lambda: view.set_viewport_position(viewport, False), 0)

        _decorate(view)
        update_current_entry_highlight(view)

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


def _header_rows(view):
    """Yield (row, change) pairs for each entry's header line."""
    line_map = _line_maps.get(view.id())
    entries = _entry_maps.get(view.id())
    if not line_map or not entries:
        return

    previous = None
    for row, change_id in enumerate(line_map):
        if change_id is not None and change_id != previous:
            change = entries.get(change_id)
            if change is not None:
                yield row, change
        previous = change_id


def _decorate(view):
    """Add right-aligned annotations and gutter icons for each entry."""
    annotation_regions = []
    annotations = []
    wc_regions = []
    conflict_regions = []

    for row, change in _header_rows(view):
        line = view.line(view.text_point(row, 0))
        annotation_regions.append(line)
        annotations.append(_build_annotation(change))
        if change.is_working_copy:
            wc_regions.append(line)
        if change.has_conflict:
            conflict_regions.append(line)

    view.erase_regions(ANNOTATION_REGION_KEY)
    if annotation_regions:
        view.add_regions(
            ANNOTATION_REGION_KEY,
            annotation_regions,
            scope="",
            flags=INVISIBLE,
            annotations=annotations,
            annotation_color="color(var(--foreground) alpha(0.25))",
        )

    view.erase_regions(GUTTER_WC_REGION_KEY)
    if wc_regions:
        view.add_regions(
            GUTTER_WC_REGION_KEY,
            wc_regions,
            scope="region.bluish",
            icon="circle",
            flags=INVISIBLE,
        )

    view.erase_regions(GUTTER_CONFLICT_REGION_KEY)
    if conflict_regions:
        view.add_regions(
            GUTTER_CONFLICT_REGION_KEY,
            conflict_regions,
            scope="region.redish",
            icon="dot",
            flags=INVISIBLE,
        )


def _build_annotation(change):
    """Build the right-aligned annotation HTML for an entry."""
    parts = []
    if change.is_working_copy:
        parts.append('<span style="color: var(--bluish)">working copy</span>')
    if change.has_conflict:
        parts.append('<span style="color: var(--redish)">conflict</span>')
    for bookmark in change.bookmarks:
        parts.append(
            f'<span style="color: var(--greenish)">{html.escape(bookmark)}</span>'
        )
    if change.age:
        parts.append(
            '<span style="color: color(var(--foreground) alpha(0.5))">'
            f"{html.escape(change.age)}</span>"
        )
    return " &nbsp; ".join(parts)


def update_current_entry_highlight(view):
    """Outline the log entry containing the cursor."""
    line_map = _line_maps.get(view.id())
    if not line_map:
        return

    selection = view.sel()
    if not selection:
        view.erase_regions(CURRENT_ENTRY_REGION_KEY)
        return

    row, _ = view.rowcol(selection[0].begin())
    if row >= len(line_map) or line_map[row] is None:
        view.erase_regions(CURRENT_ENTRY_REGION_KEY)
        return

    change_id = line_map[row]
    first = row
    while first > 0 and line_map[first - 1] == change_id:
        first -= 1
    last = row
    while last + 1 < len(line_map) and line_map[last + 1] == change_id:
        last += 1

    region = sublime.Region(
        view.text_point(first, 0),
        view.line(view.text_point(last, 0)).end(),
    )
    view.add_regions(
        CURRENT_ENTRY_REGION_KEY,
        [region],
        scope="region.bluish",
        flags=sublime.DRAW_NO_FILL,
    )


def get_change_id_at_point(view, point):
    """Return the change id of the log entry at a buffer point, or None."""
    line_map = _line_maps.get(view.id())
    if not line_map:
        return None
    row, _ = view.rowcol(point)
    if row >= len(line_map):
        return None
    return line_map[row]


def get_change_id_for_cursor(view):
    """Return the change id of the log entry under the cursor, or None."""
    selection = view.sel()
    if not selection:
        return None
    return get_change_id_at_point(view, selection[0].begin())


def get_change_info(view, change_id):
    """Return the cached ChangeInfo for a change id, or None."""
    entries = _entry_maps.get(view.id())
    if not entries:
        return None
    return entries.get(change_id)


def build_hover_html(change, description=None, diff_stat=None):
    """Build the hover card HTML for a log entry."""
    markers = []
    if change.is_working_copy:
        markers.append('<span style="color: var(--bluish)">@ working copy</span>')
    if change.has_conflict:
        markers.append('<span style="color: var(--redish)">conflict</span>')
    if change.is_empty:
        markers.append("(empty)")
    if change.is_immutable:
        markers.append("immutable")
    for bookmark in change.bookmarks:
        markers.append(
            f'<span style="color: var(--greenish)">{html.escape(bookmark)}</span>'
        )
    marker_html = " &nbsp; ".join(markers)

    if description is None:
        desc_html = html.escape(change.description)
    else:
        desc_html = html.escape(description.strip() or "(no description set)")
    desc_html = desc_html.replace("\n", "<br>")

    stat_html = ""
    if diff_stat is not None:
        stat_lines = diff_stat.strip().split("\n")
        # Show at most five file lines plus the summary
        if len(stat_lines) > 6:
            stat_lines = stat_lines[:5] + ["..."] + stat_lines[-1:]
        stat_html = (
            '<div style="margin-top: 0.5em; font-family: monospace; '
            'color: color(var(--foreground) alpha(0.7))">'
            + "<br>".join(html.escape(line) for line in stat_lines)
            + "</div>"
        )

    actions = (
        '<div style="margin-top: 0.5em">'
        '<a href="edit">edit</a> &nbsp; '
        '<a href="diff">diff</a> &nbsp; '
        '<a href="squash">squash</a> &nbsp; '
        '<a href="abandon">abandon</a>'
        "</div>"
    )

    return f"""
<body id="jj-log-hover">
    <style>
        body {{ padding: 0.4em 0.6em; }}
        .head {{ margin-bottom: 0.3em; }}
    </style>
    <div class="head">
        <b>{html.escape(change.change_id)}</b> &nbsp;
        <span style="color: color(var(--foreground) alpha(0.6))">
            {html.escape(change.author)} &nbsp; {html.escape(change.timestamp)}
            {" &nbsp; " + html.escape(change.age) if change.age else ""}
        </span>
    </div>
    {f'<div class="head">{marker_html}</div>' if marker_html else ""}
    <div>{desc_html}</div>
    {stat_html}
    {actions}
</body>
"""
