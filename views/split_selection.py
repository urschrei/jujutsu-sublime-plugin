"""Split selection view manager - creates and manages the split selection UI."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import sublime

from ..core.diff_selection import (
    LineType,
    generate_split_diff,
    parse_diff,
)
from .split_phantoms import (
    render_context_line_indicator,
    render_help_bar,
    render_hunk_indicator,
    render_line_indicator,
)

if TYPE_CHECKING:
    from ..core.jj_cli import JJCli

# Global registry of active split views
_active_managers: dict[int, "SplitViewManager"] = {}

# View setting key to identify split views
SPLIT_VIEW_SETTING = "jj_split_view"


def get_manager_for_view(view: sublime.View) -> "SplitViewManager | None":
    """Get the SplitViewManager for a view, if it's a split selection view."""
    if view is None:
        return None
    return _active_managers.get(view.id())


def is_split_view(view: sublime.View) -> bool:
    """Check if a view is a split selection view."""
    return view.settings().get(SPLIT_VIEW_SETTING, False)


class SplitViewManager:
    """Manages a split selection view with phantoms and keyboard navigation."""

    # Phantom set keys
    PHANTOM_KEY_HEADERS = "jj_split_headers"
    PHANTOM_KEY_LINES = "jj_split_lines"
    PHANTOM_KEY_HELP = "jj_split_help"

    def __init__(
        self,
        window: sublime.Window,
        cli: "JJCli",
        diff_text: str,
        on_complete: callable,
        on_cancel: callable,
        title: str = "JJ Split: Select changes for first commit",
    ):
        """Initialise the diff selection view manager.

        Args:
            window: The Sublime window to create the view in
            cli: JJCli instance for executing commands
            diff_text: Raw diff text to parse and display
            on_complete: Callback when confirmed (receives filtered diff)
            on_cancel: Callback when cancelled
            title: Title for the view
        """
        self.window = window
        self.cli = cli
        self.on_complete = on_complete
        self.on_cancel = on_cancel
        self.title = title

        # Parse the diff
        self.state = parse_diff(diff_text)

        # Validate we have something to show
        if not self.state.files or not self.state.total_hunks:
            raise ValueError("No hunks found in diff")

        # Create the view
        self.view = self._create_view()

        # Register globally
        _active_managers[self.view.id()] = self

        # Render initial phantoms
        self._render_all_phantoms()

        # Position cursor on first hunk
        self._scroll_to_current()

    def _create_view(self) -> sublime.View:
        """Create a scratch view with simplified hunk listing."""
        view = self.window.new_file()

        # Configure as scratch view
        view.set_scratch(True)
        view.set_name(self.title)
        view.settings().set(SPLIT_VIEW_SETTING, True)
        view.settings().set("word_wrap", False)
        view.settings().set("line_numbers", False)
        view.settings().set("gutter", False)
        view.settings().set("draw_white_space", "none")
        view.settings().set("margin", 0)

        # Disable Vintage/NeoVintageous for this view
        view.settings().set("is_widget", True)
        view.settings().set("command_mode", False)
        view.settings().set("vintage_start_in_command_mode", False)
        view.settings().set("is_vintageous_widget", True)
        view.settings().set("__vi_external_disable", True)

        # No syntax - we'll use phantoms for all formatting
        view.assign_syntax("Packages/Text/Plain text.tmLanguage")

        # Build simplified content
        content = self._generate_view_content()
        view.run_command("append", {"characters": content})

        # Make read-only after inserting content
        view.set_read_only(True)

        return view

    def _generate_view_content(self) -> str:
        """Generate simplified view content showing files and numbered hunks."""
        lines = []
        view_line = 0

        for file_idx, file_diff in enumerate(self.state.files):
            # File header
            lines.append(file_diff.file_path)
            file_diff.view_start_line = view_line
            view_line += 1

            # Numbered hunks
            for hunk_idx, hunk in enumerate(file_diff.hunks):
                hunk_num = hunk_idx + 1
                line_info = self._extract_line_range(hunk.header_line)
                hunk_line = f"  Hunk {hunk_num}: {line_info}"
                lines.append(hunk_line)
                hunk.view_start_line = view_line
                view_line += 1

                # If expanded, add indented diff lines
                if hunk.expanded:
                    for diff_line in hunk.lines:
                        # Show the actual diff content indented
                        lines.append(f"    {diff_line.content}")
                        diff_line.view_line = view_line
                        view_line += 1

            # Blank line between files
            if file_idx < len(self.state.files) - 1:
                lines.append("")
                view_line += 1

        return "\n".join(lines)

    def _extract_line_range(self, header: str) -> str:
        """Extract human-readable line info from hunk header."""

        match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", header)
        if not match:
            return ""

        new_start = int(match.group(3))
        new_count = int(match.group(4)) if match.group(4) else 1

        # Show starting line and line count
        if new_count == 1:
            return f"line {new_start}"
        else:
            return f"lines {new_start}-{new_start + new_count - 1}"

    def _render_all_phantoms(self) -> None:
        """Render all phantoms (headers, line indicators, help bar)."""
        self._render_hunk_headers()
        self._render_line_indicators()
        self._render_help_bar()
        self._colour_diff_lines()

    def _colour_diff_lines(self) -> None:
        """Apply colour to diff lines and highlight focused line."""

        addition_regions = []
        deletion_regions = []
        focus_regions = []

        for file_idx, file_diff in enumerate(self.state.files):
            for hunk_idx, hunk in enumerate(file_diff.hunks):
                if not hunk.expanded:
                    continue

                for diff_line in hunk.lines:
                    line_region = self.view.line(
                        self.view.text_point(diff_line.view_line, 0)
                    )

                    # Check if this line is focused
                    is_focused = (
                        file_idx == self.state.current_file_idx
                        and hunk_idx == self.state.current_hunk_idx
                        and diff_line.original_index == self.state.current_line_idx
                    )
                    if is_focused:
                        focus_regions.append(line_region)

                    if diff_line.line_type == LineType.ADDITION:
                        addition_regions.append(line_region)
                    elif diff_line.line_type == LineType.DELETION:
                        deletion_regions.append(line_region)

        # Use scope names that map to green/red in most colour schemes
        self.view.add_regions(
            "jj_additions",
            addition_regions,
            "markup.inserted",
            "",
            sublime.DRAW_NO_OUTLINE,
        )
        self.view.add_regions(
            "jj_deletions",
            deletion_regions,
            "markup.deleted",
            "",
            sublime.DRAW_NO_OUTLINE,
        )
        # Highlight focused line with solid border
        self.view.add_regions(
            "jj_focus",
            focus_regions,
            "region.cyanish",
            "",
            sublime.DRAW_NO_FILL | sublime.DRAW_SOLID_UNDERLINE,
        )

    def _render_hunk_headers(self) -> None:
        """Render inline indicators at the start of each hunk line."""
        phantoms = []

        for file_idx, file_diff in enumerate(self.state.files):
            for local_hunk_idx, hunk in enumerate(file_diff.hunks):
                is_focused = (
                    file_idx == self.state.current_file_idx
                    and local_hunk_idx == self.state.current_hunk_idx
                    and self.state.current_line_idx < 0
                )

                # Position phantom at start of the hunk line (after the indent)
                point = self.view.text_point(hunk.view_start_line, 0)

                html = render_hunk_indicator(
                    hunk,
                    is_focused,
                    file_idx=file_idx,
                    local_hunk_idx=local_hunk_idx,
                )

                phantoms.append(
                    sublime.Phantom(
                        sublime.Region(point, point),
                        html,
                        sublime.LAYOUT_INLINE,
                        on_navigate=self._on_navigate,
                    )
                )

        # Create or update phantom set
        phantom_set = sublime.PhantomSet(self.view, self.PHANTOM_KEY_HEADERS)
        phantom_set.update(phantoms)
        # Store reference to prevent garbage collection - Sublime's PhantomSet
        # must remain referenced or phantoms disappear
        self._header_phantom_set = phantom_set

    def _render_line_indicators(self) -> None:
        """Render inline checkbox indicators at the start of each diff line."""
        phantoms = []

        for file_idx, file_diff in enumerate(self.state.files):
            for local_hunk_idx, hunk in enumerate(file_diff.hunks):
                # Only render line indicators for expanded hunks
                if not hunk.expanded:
                    continue

                for diff_line in hunk.lines:
                    is_focused = (
                        file_idx == self.state.current_file_idx
                        and local_hunk_idx == self.state.current_hunk_idx
                        and diff_line.original_index == self.state.current_line_idx
                    )

                    # Position phantom at start of the line content
                    point = self.view.text_point(diff_line.view_line, 0)

                    if diff_line.is_selectable:
                        is_selected = hunk.is_line_selected(diff_line.original_index)
                        html = render_line_indicator(
                            diff_line.line_type,
                            is_selected,
                            is_focused,
                            file_idx=file_idx,
                            hunk_idx=local_hunk_idx,
                            line_idx=diff_line.original_index,
                        )
                    else:
                        html = render_context_line_indicator()

                    phantoms.append(
                        sublime.Phantom(
                            sublime.Region(point, point),
                            html,
                            sublime.LAYOUT_INLINE,
                            on_navigate=self._on_navigate,
                        )
                    )

        phantom_set = sublime.PhantomSet(self.view, self.PHANTOM_KEY_LINES)
        phantom_set.update(phantoms)
        # Keep reference to prevent GC (see _render_hunk_headers)
        self._line_phantom_set = phantom_set

    def _render_help_bar(self) -> None:
        """Render the help bar at the end of the document."""
        html = render_help_bar(self.state)

        # Position at end of document
        point = self.view.size()

        phantom_set = sublime.PhantomSet(self.view, self.PHANTOM_KEY_HELP)
        phantom_set.update(
            [
                sublime.Phantom(
                    sublime.Region(point, point),
                    html,
                    sublime.LAYOUT_BLOCK,
                )
            ]
        )
        # Keep reference to prevent GC (see _render_hunk_headers)
        self._help_phantom_set = phantom_set

    def _scroll_to_current(self) -> None:
        """Move cursor and scroll to show the currently focused hunk/line."""
        hunk = self.state.current_hunk
        if not hunk:
            return

        if self.state.current_line_idx >= 0:
            # Focus is on a specific line
            line = self.state.current_line
            if line:
                point = self.view.text_point(line.view_line, 0)
                # Move cursor to this line
                self.view.sel().clear()
                self.view.sel().add(sublime.Region(point, point))
                self.view.show_at_center(point)
        else:
            # Focus is on hunk header
            point = self.view.text_point(hunk.view_start_line, 0)
            # Move cursor to hunk header
            self.view.sel().clear()
            self.view.sel().add(sublime.Region(point, point))
            self.view.show_at_center(point)

    def refresh_phantoms(self) -> None:
        """Refresh view content and phantoms after state change."""
        # Regenerate view content (handles expand/collapse)
        self.view.set_read_only(False)
        self.view.run_command("select_all")
        self.view.run_command("right_delete")
        content = self._generate_view_content()
        self.view.run_command("append", {"characters": content})
        self.view.set_read_only(True)

        self._render_all_phantoms()
        self._scroll_to_current()

    def _on_navigate(self, href: str) -> None:
        """Handle phantom link clicks.

        href format:
        - toggle:hunk:file_idx:hunk_idx - toggle hunk selection
        - toggle:line:file_idx:hunk_idx:line_idx - toggle line selection
        - expand:hunk:file_idx:hunk_idx - toggle hunk expand/collapse
        """
        parts = href.split(":")
        if len(parts) < 3:
            return

        action = parts[0]
        target = parts[1]

        if action == "toggle":
            if target == "hunk" and len(parts) >= 4:
                file_idx = int(parts[2])
                hunk_idx = int(parts[3])
                self._toggle_hunk(file_idx, hunk_idx)
            elif target == "line" and len(parts) >= 5:
                file_idx = int(parts[2])
                hunk_idx = int(parts[3])
                line_idx = int(parts[4])
                self._toggle_line(file_idx, hunk_idx, line_idx)
        elif action == "expand":
            if target == "hunk" and len(parts) >= 4:
                file_idx = int(parts[2])
                hunk_idx = int(parts[3])
                self._toggle_expand(file_idx, hunk_idx)

    def _toggle_hunk(self, file_idx: int, hunk_idx: int) -> None:
        """Toggle all selectable lines in a hunk."""
        if 0 <= file_idx < len(self.state.files):
            file_diff = self.state.files[file_idx]
            if 0 <= hunk_idx < len(file_diff.hunks):
                hunk = file_diff.hunks[hunk_idx]
                hunk.toggle_all()
                self.refresh_phantoms()

    def _toggle_line(self, file_idx: int, hunk_idx: int, line_idx: int) -> None:
        """Toggle selection of a specific line."""
        if 0 <= file_idx < len(self.state.files):
            file_diff = self.state.files[file_idx]
            if 0 <= hunk_idx < len(file_diff.hunks):
                hunk = file_diff.hunks[hunk_idx]
                hunk.toggle_line(line_idx)
                self.refresh_phantoms()

    def _toggle_expand(self, file_idx: int, hunk_idx: int) -> None:
        """Toggle expand/collapse state of a hunk."""
        if 0 <= file_idx < len(self.state.files):
            file_diff = self.state.files[file_idx]
            if 0 <= hunk_idx < len(file_diff.hunks):
                hunk = file_diff.hunks[hunk_idx]
                hunk.expanded = not hunk.expanded
                # Update current position if we're on this hunk
                if (
                    file_idx == self.state.current_file_idx
                    and hunk_idx == self.state.current_hunk_idx
                ):
                    if not hunk.expanded:
                        self.state.current_line_idx = -1
                self.refresh_phantoms()

    # Navigation methods - called from keyboard handler

    def nav_next(self) -> None:
        """Smart navigation: next line if in expanded hunk, next hunk otherwise."""
        if self.state.nav_next():
            self.refresh_phantoms()

    def nav_prev(self) -> None:
        """Smart navigation: prev line if in expanded hunk, prev hunk otherwise."""
        if self.state.nav_prev():
            self.refresh_phantoms()

    def expand_current(self) -> None:
        """Expand current hunk and enter it."""
        if self.state.expand_current():
            self.refresh_phantoms()

    def collapse_current(self) -> None:
        """Collapse current hunk and exit to hunk level."""
        if self.state.collapse_current():
            self.refresh_phantoms()

    def toggle_current(self) -> None:
        """Toggle selection of current item."""
        self.state.toggle_current()
        self.refresh_phantoms()

    def select_all(self) -> None:
        """Select all selectable lines."""
        self.state.select_all()
        self.refresh_phantoms()

    def deselect_all(self) -> None:
        """Deselect all lines."""
        self.state.deselect_all()
        self.refresh_phantoms()

    def confirm(self) -> None:
        """Confirm the split and execute."""
        if not self.state.has_any_selection:
            sublime.status_message("jj: No lines selected for split")
            return

        # Generate the filtered diff
        filtered_diff = generate_split_diff(self.state)

        # Close the view
        self.close()

        # Execute callback
        self.on_complete(filtered_diff)

    def cancel(self) -> None:
        """Cancel the split operation."""
        self.close()
        self.on_cancel()

    def close(self) -> None:
        """Close the split view and clean up."""
        # Unregister
        if self.view.id() in _active_managers:
            del _active_managers[self.view.id()]

        # Close the view
        self.view.close()
