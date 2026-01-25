"""HTML rendering functions for split selection phantoms."""

from __future__ import annotations

from ..core.diff_selection import LineType, SelectableHunk, SplitSelectionState

# CSS styles for phantoms - uses Sublime's CSS variable system
PHANTOM_STYLE = """
<style>
    body {
        margin: 0;
        padding: 0;
        font-family: system-ui, -apple-system, sans-serif;
    }
    a {
        text-decoration: none;
        color: inherit;
    }
    .hunk-row {
        padding: 2px 4px;
        border-radius: 3px;
        display: inline;
    }
    .hunk-row.selected {
        background-color: color(var(--greenish) alpha(0.4));
        color: var(--greenish);
    }
    .hunk-row.partial {
        background-color: color(var(--yellowish) alpha(0.4));
        color: var(--yellowish);
    }
    .hunk-row.focused {
        outline: 1px solid var(--accent);
    }
    .checkbox {
        font-family: monospace;
        color: var(--foreground);
        padding: 2px 4px;
    }
    .checkbox:hover {
        background-color: color(var(--background) blend(var(--foreground) 85%));
        border-radius: 3px;
    }
    .checkbox.selected {
        color: var(--greenish);
    }
    .checkbox.partial {
        color: var(--yellowish);
    }
    .expand-arrow {
        font-family: monospace;
        color: var(--foreground);
        padding: 2px 4px;
        opacity: 0.7;
    }
    .expand-arrow:hover {
        background-color: color(var(--background) blend(var(--foreground) 85%));
        border-radius: 3px;
    }
    .line-indicator {
        display: inline;
        padding: 0 2px 0 0;
        font-family: monospace;
    }
    .line-indicator.focused {
        background-color: color(var(--background) blend(var(--foreground) 90%));
        border-radius: 2px;
    }
    .line-indicator.addition {
        color: var(--greenish);
    }
    .line-indicator.deletion {
        color: var(--redish);
    }
    .line-indicator a {
        padding: 2px 4px;
    }
    .line-indicator a:hover {
        background-color: color(var(--background) blend(var(--foreground) 80%));
        border-radius: 3px;
    }
    .help-bar {
        background-color: color(var(--background) blend(var(--foreground) 95%));
        padding: 6px 10px;
        border-radius: 3px;
        margin-top: 8px;
        font-size: 0.9em;
    }
    .help-key {
        background-color: color(var(--background) blend(var(--foreground) 85%));
        padding: 2px 6px;
        border-radius: 3px;
        font-family: monospace;
        margin: 0 2px;
    }
    .help-text {
        color: var(--foreground);
        opacity: 0.8;
        margin-right: 12px;
    }
    .selection-count {
        color: var(--greenish);
        margin-left: 12px;
    }
</style>
"""


def render_hunk_indicator(
    hunk: SelectableHunk,
    is_focused: bool,
    file_idx: int = 0,
    local_hunk_idx: int = 0,
) -> str:
    """Render inline indicator for a hunk line.

    Shows: [expand] [checkbox] with colour-coded background
    - Green background if fully selected
    - Yellow background if partially selected
    """
    # Expand/collapse indicator
    expand_arrow = "▶" if not hunk.expanded else "▼"
    expand_href = f"expand:hunk:{file_idx}:{local_hunk_idx}"

    # Determine checkbox state and row class
    if hunk.is_fully_selected:
        checkbox_text = "[x]"
        checkbox_class = "checkbox selected"
        row_class = "hunk-row selected"
    elif hunk.is_partially_selected:
        checkbox_text = "[-]"
        checkbox_class = "checkbox partial"
        row_class = "hunk-row partial"
    else:
        checkbox_text = "[ ]"
        checkbox_class = "checkbox"
        row_class = "hunk-row"

    if is_focused:
        row_class += " focused"

    toggle_href = f"toggle:hunk:{file_idx}:{local_hunk_idx}"

    return f"""{PHANTOM_STYLE}
<body>
<span class="{row_class}"><a href="{expand_href}" class="expand-arrow">{expand_arrow}</a><a href="{toggle_href}" class="{checkbox_class}">{checkbox_text}</a></span>
</body>
"""


def render_line_indicator(
    line_type: LineType,
    is_selected: bool,
    is_focused: bool,
    file_idx: int = 0,
    hunk_idx: int = 0,
    line_idx: int = 0,
) -> str:
    """Render the inline checkbox indicator for a diff line."""
    if is_selected:
        checkbox_text = "[x]"
        checkbox_class = "checkbox selected"
    else:
        checkbox_text = "[ ]"
        checkbox_class = "checkbox"

    # Build class list
    classes = ["line-indicator"]
    if is_focused:
        classes.append("focused")
    if line_type == LineType.ADDITION:
        classes.append("addition")
    elif line_type == LineType.DELETION:
        classes.append("deletion")

    href = f"toggle:line:{file_idx}:{hunk_idx}:{line_idx}"

    return f"""{PHANTOM_STYLE}
<body>
<span class="{" ".join(classes)}"><a href="{href}" class="{checkbox_class}">{checkbox_text}</a></span>
</body>
"""


def render_context_line_indicator() -> str:
    """Render the indicator for context lines (not selectable)."""
    return f"""{PHANTOM_STYLE}
<body>
<span class="line-indicator">   </span>
</body>
"""


def render_help_bar(state: SplitSelectionState) -> str:
    """Render the help bar at the bottom of the view."""
    total_selected = sum(len(h.selected_lines) for f in state.files for h in f.hunks)
    total_selectable = sum(h.selectable_count for f in state.files for h in f.hunks)

    return f"""{PHANTOM_STYLE}
<body>
<div class="help-bar">
    <span class="help-key">↑↓</span> <span class="help-text">navigate</span>
    <span class="help-key">→</span> <span class="help-text">expand</span>
    <span class="help-key">←</span> <span class="help-text">collapse</span>
    <span class="help-key">x</span> <span class="help-text">toggle</span>
    <span class="help-key">Ctrl+A</span> <span class="help-text">all</span>
    <span class="help-key">Enter</span> <span class="help-text">confirm</span>
    <span class="help-key">Esc</span> <span class="help-text">cancel</span>
    <span class="selection-count">Selected: {total_selected}/{total_selectable}</span>
</div>
</body>
"""
