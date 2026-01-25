"""Data model for interactive diff selection in split operations."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class LineType(Enum):
    """Type of diff line."""

    CONTEXT = "context"
    ADDITION = "addition"
    DELETION = "deletion"


@dataclass
class DiffLine:
    """A single line within a diff hunk."""

    line_type: LineType
    content: str  # Full line including +/-/space prefix
    original_index: int  # Index within hunk (0-based)
    view_line: int = 0  # Line number in Sublime view (set during rendering)

    @property
    def is_selectable(self) -> bool:
        """Only additions and deletions are selectable."""
        return self.line_type in (LineType.ADDITION, LineType.DELETION)

    @property
    def display_content(self) -> str:
        """Content without the prefix character."""
        return self.content[1:] if self.content else ""


@dataclass
class SelectableHunk:
    """A selectable diff hunk containing lines."""

    file_path: str
    header_line: str  # @@ -10,5 +10,7 @@
    lines: list[DiffLine] = field(default_factory=list)
    selected_lines: set[int] = field(
        default_factory=set
    )  # Set of original_index values
    view_start_line: int = 0  # Line number where hunk starts in view
    expanded: bool = False  # Whether hunk is expanded to show individual lines

    @property
    def is_fully_selected(self) -> bool:
        """All selectable lines are selected."""
        selectable = {ln.original_index for ln in self.lines if ln.is_selectable}
        return selectable and selectable == self.selected_lines

    @property
    def is_partially_selected(self) -> bool:
        """Some but not all selectable lines are selected."""
        selectable = {ln.original_index for ln in self.lines if ln.is_selectable}
        return bool(self.selected_lines) and self.selected_lines != selectable

    @property
    def is_empty(self) -> bool:
        """No lines are selected."""
        return not self.selected_lines

    @property
    def selectable_count(self) -> int:
        """Count of selectable lines in this hunk."""
        return sum(1 for ln in self.lines if ln.is_selectable)

    def select_all(self) -> None:
        """Select all selectable lines."""
        self.selected_lines = {
            ln.original_index for ln in self.lines if ln.is_selectable
        }

    def deselect_all(self) -> None:
        """Deselect all lines."""
        self.selected_lines = set()

    def toggle_line(self, idx: int) -> None:
        """Toggle selection of a specific line."""
        if idx in self.selected_lines:
            self.selected_lines.remove(idx)
        else:
            # Only add if it's a selectable line
            for ln in self.lines:
                if ln.original_index == idx and ln.is_selectable:
                    self.selected_lines.add(idx)
                    break

    def toggle_all(self) -> None:
        """Toggle all selectable lines - if any selected, deselect all; else select all."""
        if self.selected_lines:
            self.deselect_all()
        else:
            self.select_all()

    def is_line_selected(self, idx: int) -> bool:
        """Check if a line at index is selected."""
        return idx in self.selected_lines


@dataclass
class FileDiff:
    """Represents a file's diff with its hunks."""

    file_path: str
    old_path: str | None  # For renames
    new_path: str | None  # For renames
    hunks: list[SelectableHunk] = field(default_factory=list)
    is_binary: bool = False  # Binary files are non-selectable
    header_lines: list[str] = field(default_factory=list)  # diff --git, ---, +++
    view_start_line: int = 0  # Line number where file starts in view

    @property
    def is_fully_selected(self) -> bool:
        """All hunks are fully selected."""
        return all(h.is_fully_selected for h in self.hunks)

    @property
    def has_selection(self) -> bool:
        """At least one line is selected in any hunk."""
        return any(not h.is_empty for h in self.hunks)


@dataclass
class SplitSelectionState:
    """Complete state for the split selection UI."""

    files: list[FileDiff] = field(default_factory=list)
    current_file_idx: int = 0
    current_hunk_idx: int = 0
    current_line_idx: int = -1  # -1 = hunk header focused

    @property
    def current_file(self) -> FileDiff | None:
        """Get the currently focused file."""
        if 0 <= self.current_file_idx < len(self.files):
            return self.files[self.current_file_idx]
        return None

    @property
    def current_hunk(self) -> SelectableHunk | None:
        """Get the currently focused hunk."""
        file = self.current_file
        if file and 0 <= self.current_hunk_idx < len(file.hunks):
            return file.hunks[self.current_hunk_idx]
        return None

    @property
    def current_line(self) -> DiffLine | None:
        """Get the currently focused line (None if on hunk header)."""
        hunk = self.current_hunk
        if hunk and self.current_line_idx >= 0:
            for ln in hunk.lines:
                if ln.original_index == self.current_line_idx:
                    return ln
        return None

    @property
    def has_any_selection(self) -> bool:
        """Check if any lines are selected across all files."""
        return any(f.has_selection for f in self.files)

    @property
    def total_hunks(self) -> int:
        """Total number of hunks across all files."""
        return sum(len(f.hunks) for f in self.files)

    def _flat_hunk_index(self) -> int:
        """Get flat index of current hunk across all files."""
        idx = 0
        for i, f in enumerate(self.files):
            if i == self.current_file_idx:
                return idx + self.current_hunk_idx
            idx += len(f.hunks)
        return idx

    def _set_from_flat_hunk_index(self, flat_idx: int) -> None:
        """Set file and hunk indices from a flat hunk index."""
        idx = 0
        for i, f in enumerate(self.files):
            if flat_idx < idx + len(f.hunks):
                self.current_file_idx = i
                self.current_hunk_idx = flat_idx - idx
                return
            idx += len(f.hunks)

    def nav_next_hunk(self) -> bool:
        """Move to next hunk. Returns True if moved."""
        flat = self._flat_hunk_index()
        if flat < self.total_hunks - 1:
            self._set_from_flat_hunk_index(flat + 1)
            self.current_line_idx = -1  # Reset to hunk header
            return True
        return False

    def nav_prev_hunk(self) -> bool:
        """Move to previous hunk. Returns True if moved."""
        flat = self._flat_hunk_index()
        if flat > 0:
            self._set_from_flat_hunk_index(flat - 1)
            self.current_line_idx = -1  # Reset to hunk header
            return True
        return False

    def nav_next_line(self) -> bool:
        """Move to next selectable line within current hunk. Returns True if moved."""
        hunk = self.current_hunk
        if not hunk:
            return False

        # Find next selectable line after current
        selectable_indices = sorted(
            ln.original_index for ln in hunk.lines if ln.is_selectable
        )

        if not selectable_indices:
            return False

        if self.current_line_idx < 0:
            # On hunk header, move to first selectable line
            self.current_line_idx = selectable_indices[0]
            return True

        # Find next selectable line
        for idx in selectable_indices:
            if idx > self.current_line_idx:
                self.current_line_idx = idx
                return True

        return False

    def nav_prev_line(self) -> bool:
        """Move to previous selectable line or back to hunk header. Returns True if moved."""
        hunk = self.current_hunk
        if not hunk:
            return False

        if self.current_line_idx < 0:
            # Already on hunk header
            return False

        # Find previous selectable line
        selectable_indices = sorted(
            ln.original_index for ln in hunk.lines if ln.is_selectable
        )

        for idx in reversed(selectable_indices):
            if idx < self.current_line_idx:
                self.current_line_idx = idx
                return True

        # No previous line, go back to hunk header
        self.current_line_idx = -1
        return True

    def toggle_current(self) -> None:
        """Toggle selection of current item (hunk or line)."""
        hunk = self.current_hunk
        if not hunk:
            return

        if self.current_line_idx < 0:
            # On hunk header - toggle all lines
            hunk.toggle_all()
        else:
            # On specific line
            hunk.toggle_line(self.current_line_idx)

    def select_all(self) -> None:
        """Select all selectable lines in all hunks."""
        for f in self.files:
            for h in f.hunks:
                h.select_all()

    def deselect_all(self) -> None:
        """Deselect all lines in all hunks."""
        for f in self.files:
            for h in f.hunks:
                h.deselect_all()

    def nav_next(self) -> bool:
        """Smart DOWN navigation.

        - Collapsed hunk: move to next hunk
        - Expanded hunk on header: move to first line
        - Expanded hunk on line: move to next line, or next hunk if at end
        """
        hunk = self.current_hunk
        if not hunk:
            return False

        if not hunk.expanded:
            # Collapsed: move to next hunk
            return self.nav_next_hunk()

        # Expanded hunk
        if self.current_line_idx < 0:
            # On header: move to first line
            return self.nav_next_line()

        # On a line: try to move to next line
        if self.nav_next_line():
            return True

        # At last line: move to next hunk
        return self.nav_next_hunk()

    def nav_prev(self) -> bool:
        """Smart UP navigation.

        - Collapsed hunk: move to previous hunk
        - Expanded hunk on header: move to previous hunk
        - Expanded hunk on first line: move to header
        - Expanded hunk on other line: move to previous line
        """
        hunk = self.current_hunk
        if not hunk:
            return False

        if not hunk.expanded:
            # Collapsed: move to previous hunk
            return self.nav_prev_hunk()

        # Expanded hunk
        if self.current_line_idx < 0:
            # On header: move to previous hunk
            return self.nav_prev_hunk()

        # On a line: try to move to previous line (or back to header)
        return self.nav_prev_line()

    def expand_current(self) -> bool:
        """Expand current hunk and enter it.

        RIGHT on collapsed hunk: expand AND move to first selectable line
        RIGHT on expanded hunk header: move to first selectable line
        RIGHT on a line: move to next line within hunk
        """
        hunk = self.current_hunk
        if not hunk:
            return False

        if not hunk.expanded:
            # Expand and enter in one action
            hunk.expanded = True
            # Move to first selectable line
            selectable = sorted(
                ln.original_index for ln in hunk.lines if ln.is_selectable
            )
            if selectable:
                self.current_line_idx = selectable[0]
            return True

        # Hunk is already expanded
        if self.current_line_idx < 0:
            # On header, enter the hunk (move to first line)
            return self.nav_next_line()
        else:
            # Already on a line, move to next line
            return self.nav_next_line()

    def collapse_current(self) -> bool:
        """Exit line navigation or collapse hunk.

        If on a line: go back to hunk header
        If on hunk header: collapse the hunk
        """
        hunk = self.current_hunk
        if not hunk:
            return False

        if self.current_line_idx >= 0:
            # On a line, go back to hunk header
            self.current_line_idx = -1
            return True

        if hunk.expanded:
            # On header, collapse the hunk
            hunk.expanded = False
            return True

        # Already collapsed
        return False


# Regex for parsing diff components
_DIFF_HEADER_RE = re.compile(r"^diff --git a/(.+) b/(.+)$")
_HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")


def parse_diff(diff_text: str) -> SplitSelectionState:
    """Parse raw git diff text into a SplitSelectionState.

    All selectable lines start unselected.
    """
    state = SplitSelectionState()
    current_file: FileDiff | None = None
    current_hunk: SelectableHunk | None = None
    line_index = 0

    lines = diff_text.split("\n")

    for line in lines:
        # Check for new file diff
        match = _DIFF_HEADER_RE.match(line)
        if match:
            # Save previous hunk if exists
            if current_hunk and current_file:
                current_file.hunks.append(current_hunk)
            # Save previous file if exists
            if current_file:
                state.files.append(current_file)

            current_file = FileDiff(
                file_path=match.group(2),
                old_path=match.group(1),
                new_path=match.group(2),
            )
            current_file.header_lines.append(line)
            current_hunk = None
            line_index = 0
            continue

        # Collect file header lines (---, +++, etc.)
        if current_file and current_hunk is None:
            if line.startswith("---") or line.startswith("+++"):
                current_file.header_lines.append(line)
                continue
            if (
                line.startswith("index ")
                or line.startswith("new file")
                or line.startswith("deleted file")
            ):
                current_file.header_lines.append(line)
                continue
            if line.startswith("Binary files"):
                current_file.is_binary = True
                current_file.header_lines.append(line)
                continue

        # Check for hunk header
        hunk_match = _HUNK_HEADER_RE.match(line)
        if hunk_match:
            # Save previous hunk if exists
            if current_hunk and current_file:
                current_file.hunks.append(current_hunk)

            current_hunk = SelectableHunk(
                file_path=current_file.file_path if current_file else "",
                header_line=line,
            )
            line_index = 0
            continue

        # Parse hunk content
        if current_hunk and line:
            if line.startswith("+") and not line.startswith("+++"):
                current_hunk.lines.append(
                    DiffLine(
                        line_type=LineType.ADDITION,
                        content=line,
                        original_index=line_index,
                    )
                )
                line_index += 1
            elif line.startswith("-") and not line.startswith("---"):
                current_hunk.lines.append(
                    DiffLine(
                        line_type=LineType.DELETION,
                        content=line,
                        original_index=line_index,
                    )
                )
                line_index += 1
            elif line.startswith(" "):
                current_hunk.lines.append(
                    DiffLine(
                        line_type=LineType.CONTEXT,
                        content=line,
                        original_index=line_index,
                    )
                )
                line_index += 1
            elif line.startswith("\\"):
                # "\ No newline at end of file" - treat as context
                current_hunk.lines.append(
                    DiffLine(
                        line_type=LineType.CONTEXT,
                        content=line,
                        original_index=line_index,
                    )
                )
                line_index += 1

    # Don't forget the last hunk and file
    if current_hunk and current_file:
        current_file.hunks.append(current_hunk)
    if current_file:
        state.files.append(current_file)

    return state


def generate_split_diff(state: SplitSelectionState) -> str:
    """Generate a diff containing only the selected changes.

    This diff is suitable for passing to `jj split`.

    Rules:
    - Include file headers (diff --git, ---, +++)
    - For each hunk with selected lines:
      - Recalculate @@ header based on selected line counts
      - Selected additions (+): include as-is
      - Selected deletions (-): include as-is
      - Unselected additions: omit entirely
      - Unselected deletions: convert to context (keep the line)
      - Context lines: include as-is
    """
    output_lines = []

    for file_diff in state.files:
        if not file_diff.has_selection:
            continue

        # Add file headers
        for header in file_diff.header_lines:
            output_lines.append(header)

        for hunk in file_diff.hunks:
            if hunk.is_empty:
                continue

            # Build the filtered hunk content
            hunk_lines = []
            for diff_line in hunk.lines:
                is_selected = diff_line.original_index in hunk.selected_lines

                if diff_line.line_type == LineType.CONTEXT:
                    # Context lines always included
                    hunk_lines.append(diff_line.content)
                elif diff_line.line_type == LineType.ADDITION:
                    if is_selected:
                        hunk_lines.append(diff_line.content)
                    # Unselected additions: omit entirely
                elif diff_line.line_type == LineType.DELETION:
                    if is_selected:
                        hunk_lines.append(diff_line.content)
                    else:
                        # Unselected deletions: convert to context
                        hunk_lines.append(" " + diff_line.display_content)

            # Recalculate hunk header
            new_header = _recalculate_hunk_header(hunk.header_line, hunk_lines)
            output_lines.append(new_header)
            output_lines.extend(hunk_lines)

    return "\n".join(output_lines)


def _recalculate_hunk_header(original_header: str, filtered_lines: list[str]) -> str:
    """Recalculate the @@ header based on filtered content."""
    match = _HUNK_HEADER_RE.match(original_header)
    if not match:
        return original_header

    old_start = int(match.group(1))
    suffix = match.group(5) or ""

    # Count lines for old and new sides
    old_count = sum(
        1 for ln in filtered_lines if ln.startswith(" ") or ln.startswith("-")
    )
    new_count = sum(
        1 for ln in filtered_lines if ln.startswith(" ") or ln.startswith("+")
    )

    # Handle "\ No newline" lines - they don't count
    old_count -= sum(1 for ln in filtered_lines if ln.startswith("\\"))
    new_count -= sum(1 for ln in filtered_lines if ln.startswith("\\"))

    # Also need to figure out new_start - this is tricky
    # For simplicity, we keep the same start positions
    # jj should handle the actual positioning
    new_start = old_start

    if old_count == 1:
        old_part = f"-{old_start}"
    else:
        old_part = f"-{old_start},{old_count}"

    if new_count == 1:
        new_part = f"+{new_start}"
    else:
        new_part = f"+{new_start},{new_count}"

    return f"@@ {old_part} {new_part} @@{suffix}"
