"""Quick commands for jj operations."""

import webbrowser

import sublime

from ..core.formatting import format_change_details
from ..views.status_bar import update_status_bar
from .base import JjWindowCommand

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


class JjNewCommand(JjWindowCommand):
    """Create a new change."""

    def run(self, message=None):
        cli = self.get_cli()
        if cli is None:
            return

        def on_done(msg):
            if not msg.strip():
                msg = None

            def on_result(success, error):
                if success:
                    self.show_status("Created new change")
                    refresh_all_views(self.window)
                else:
                    self.show_error(f"Failed to create new change: {error}")

            cli.new(on_result, msg)

        if message is not None:
            on_done(message)
        else:
            self.window.show_input_panel(
                "New change message (optional):",
                "",
                on_done,
                None,
                None,
            )


class JjDescribeCommand(JjWindowCommand):
    """Set description for current or selected change."""

    def run(self, mode=None):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli

        if mode == "current":
            cli.get_current_change(self._describe_change)
        elif mode == "pick":
            self._show_revision_picker()
        else:
            # Show choice picker
            self._show_mode_picker()

    def _show_mode_picker(self):
        """Show picker to choose between current change or picking one."""
        items = [
            sublime.QuickPanelItem(
                trigger="Current change",
                details="Describe the working copy (@)",
                kind=KIND_WORKING_COPY,
            ),
            sublime.QuickPanelItem(
                trigger="Pick a change",
                details="Choose from mutable changes",
                kind=KIND_ACTION,
            ),
        ]

        def on_select(idx):
            if idx == 0:
                self.cli.get_current_change(self._describe_change)
            elif idx == 1:
                self._show_revision_picker()

        self.window.show_quick_panel(
            items, on_select, placeholder="Describe which change?"
        )

    def _show_revision_picker(self):
        """Show picker to select a mutable revision to describe."""

        def on_log(changes):
            if not changes:
                self.show_error("Could not get change log")
                return

            self.changes = changes
            items = [
                build_change_quick_panel_item(change, include_immutable=False)
                for change in changes
            ]

            def on_select(idx):
                if idx < 0:
                    return
                self._describe_change(self.changes[idx])

            self.window.show_quick_panel(
                items, on_select, placeholder="Select change to describe"
            )

        self.cli.get_log(on_log, revset="mutable()", limit=DEFAULT_LOG_LIMIT)

    def _describe_change(self, info):
        """Show input panel to describe the given change."""
        if info is None:
            self.show_error("Could not get change info")
            return

        self.selected_change = info
        current_desc = (
            info.description if info.description != "(no description)" else ""
        )

        def on_done(msg):
            if not msg.strip():
                self.show_status("Description unchanged (empty input)")
                return

            def on_result(success, error):
                if success:
                    self.show_status(f"Description updated for {info.change_id}")
                    refresh_all_views(self.window)
                else:
                    self.show_error(f"Failed to update description: {error}")

            self.cli.describe(msg, on_result, revision=info.change_id)

        self.window.show_input_panel(
            f"Description for {info.change_id}:",
            current_desc,
            on_done,
            None,
            None,
        )


class JjCommitCommand(JjWindowCommand):
    """Commit current change (describe + new)."""

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        def on_done(msg):
            if not msg.strip():
                self.show_status("Commit cancelled (empty message)")
                return

            def on_result(success, error):
                if success:
                    self.show_status("Change committed")
                    refresh_all_views(self.window)
                else:
                    self.show_error(f"Failed to commit: {error}")

            cli.commit(msg, on_result)

        self.window.show_input_panel(
            "Commit message:",
            "",
            on_done,
            None,
            None,
        )


class JjSquashCommand(JjWindowCommand):
    """Squash changes with wizard-style UI for selecting sources and destination."""

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli
        self.selected_sources = set()
        self._step1_load_changes()

    def _step1_load_changes(self):
        """Load changes and start source selection."""

        def on_log(changes):
            if not changes:
                self.show_error("Could not get change log")
                return

            self.all_changes = changes
            self._step1_show_source_picker()

        # Only show mutable changes - can't squash immutable commits
        self.cli.get_log(on_log, revset="mutable()", limit=50)

    def _step1_show_source_picker(self, restore_index=0):
        """Step 1: Select source change(s) to squash - toggle selection."""
        items = []

        # Add "Done" option at top if we have selections
        has_done_option = bool(self.selected_sources)
        if has_done_option:
            items.append(
                sublime.QuickPanelItem(
                    trigger=f"Squash {len(self.selected_sources)} selected change(s)",
                    details="Proceed to select destination",
                    kind=KIND_ACTION,
                )
            )

        # Add changes with selection indicators
        for change in self.all_changes:
            is_selected = change.change_id in self.selected_sources

            # Build annotation with optional "selected" prefix
            extra = ["selected"] if is_selected else None
            annotations = (extra or []) + build_change_annotations(change)

            # Bold the details if selected
            details = format_change_details(change)
            if is_selected:
                details = f"<b>{details}</b>"

            items.append(
                sublime.QuickPanelItem(
                    trigger=change.change_id,
                    details=details,
                    annotation=" | ".join(annotations) if annotations else "",
                    kind=KIND_WORKING_COPY if change.is_working_copy else KIND_CHANGE,
                )
            )

        def on_select(idx):
            if idx < 0:
                return

            # Account for "Done" option offset
            offset = 1 if has_done_option else 0

            if has_done_option and idx == 0:
                # User selected "Done" - proceed to destination
                self._step2_select_destination()
            else:
                # Toggle selection for this change
                change = self.all_changes[idx - offset]
                if change.change_id in self.selected_sources:
                    self.selected_sources.remove(change.change_id)
                else:
                    self.selected_sources.add(change.change_id)
                # Show picker again, restoring position
                # Adjust index if "Done" option was just added or removed
                new_has_done = bool(self.selected_sources)
                new_idx = idx
                if new_has_done and not has_done_option:
                    new_idx = idx + 1  # "Done" option was added
                elif not new_has_done and has_done_option:
                    new_idx = idx - 1  # "Done" option was removed
                self._step1_show_source_picker(restore_index=new_idx)

        self.window.show_quick_panel(
            items,
            on_select,
            selected_index=restore_index,
            placeholder="Select changes to squash (toggle selection)",
        )

    def _step2_select_destination(self):
        """Step 2: Select destination change to squash into."""
        items = []
        valid_changes = []

        for change in self.all_changes:
            # Exclude selected sources from destinations
            if change.change_id in self.selected_sources:
                continue

            items.append(build_change_quick_panel_item(change))
            valid_changes.append(change)

        if not items:
            self.show_status("No valid destinations for squash")
            return

        def on_select(idx):
            if idx < 0:
                return
            self.selected_destination = valid_changes[idx]
            self._step3_message_option()

        self.window.show_quick_panel(
            items, on_select, placeholder="Select destination to squash into"
        )

    def _step3_message_option(self):
        """Step 3: Ask about commit message handling."""
        items = [
            sublime.QuickPanelItem(
                trigger="Keep source commit messages",
                details="Combine messages from source and destination",
                kind=KIND_ACTION,
            ),
            sublime.QuickPanelItem(
                trigger="Discard source commit messages",
                details="Use only the destination's message",
                kind=KIND_ACTION,
            ),
        ]

        def on_select(idx):
            if idx < 0:
                return
            use_dest_message = idx == 1
            self._execute_squash(use_dest_message)

        self.window.show_quick_panel(
            items, on_select, placeholder="Commit message handling"
        )

    def _execute_squash(self, use_dest_message):
        """Execute the squash with selected options."""
        sources = list(self.selected_sources)
        dest = self.selected_destination.change_id

        def on_result(success, error):
            if success:
                self.show_status(f"Squashed {len(sources)} change(s) into {dest}")
                refresh_all_views(self.window)
            else:
                self.show_error(f"Failed to squash: {error}")

        self.cli.squash_flexible(sources, dest, use_dest_message, on_result)


class JjQuickSquashCommand(JjWindowCommand):
    """Squash current change into parent with no interaction.

    Does nothing if the current change is empty. Designed for keybinding.
    """

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        def on_change_info(info):
            if info is None:
                return

            if info.is_empty:
                self.show_status("Nothing to squash (change is empty)")
                return

            def on_result(success, error):
                if success:
                    self.show_status("Squashed into parent")
                    refresh_all_views(self.window)
                else:
                    self.show_error(f"Failed to squash: {error}")

            cli.squash(on_result)

        cli.get_current_change(on_change_info)


class JjAbsorbCommand(JjWindowCommand):
    """Absorb changes into ancestor commits.

    Moves changes from the working copy into the stack of mutable revisions
    where the corresponding lines were last modified.
    """

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        def on_change_info(info):
            if info is None:
                return

            if info.is_empty:
                self.show_status("Nothing to absorb (change is empty)")
                return

            def on_result(success, error):
                if success:
                    self.show_status("Changes absorbed into ancestors")
                    refresh_all_views(self.window)
                else:
                    self.show_error(f"Failed to absorb: {error}")

            cli.absorb(on_result)

        cli.get_current_change(on_change_info)


class JjSquashInteractiveCommand(JjWindowCommand):
    """Interactively squash selected parts of current change into a destination.

    Opens a destination picker, then a diff selection UI to choose which
    hunks/lines to squash.
    """

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli
        self._select_destination()

    def _select_destination(self):
        """Step 1: Select destination commit to squash into."""

        def on_log(changes):
            if not changes:
                self.show_error("Could not get change log")
                return

            # Filter out the working copy - can't squash into yourself
            valid_changes = [c for c in changes if not c.is_working_copy]
            if not valid_changes:
                self.show_error("No valid destinations for squash")
                return

            items = [
                build_change_quick_panel_item(change, include_immutable=False)
                for change in valid_changes
            ]

            # Find @- (parent) to set as default selection
            default_index = 0
            for i, change in enumerate(valid_changes):
                # The first non-working-copy commit is typically @-
                # We could also check if it's the parent, but this is simpler
                break

            def on_select(idx):
                if idx < 0:
                    return
                self.destination = valid_changes[idx]
                self._load_diff()

            self.window.show_quick_panel(
                items,
                on_select,
                selected_index=default_index,
                placeholder="Select destination to squash into",
            )

        # Show mutable commits as potential destinations
        self.cli.get_log(on_log, revset="mutable()", limit=DEFAULT_LOG_LIMIT)

    def _load_diff(self):
        """Step 2: Load the diff for current change."""
        self.show_status("Loading diff...")
        self.cli.get_diff_raw(self._on_diff_loaded)

    def _on_diff_loaded(self, success: bool, result: str) -> None:
        if not success:
            self.show_error(f"Failed to get diff: {result}")
            return

        diff_text = result.strip()
        if not diff_text:
            self.show_status("Nothing to squash (no changes)")
            return

        if "diff --git" not in diff_text:
            self.show_status("Nothing to squash (no changes)")
            return

        from ..views.split_selection import SplitViewManager

        dest_id = self.destination.change_id
        try:
            SplitViewManager(
                window=self.window,
                cli=self.cli,
                diff_text=diff_text,
                on_complete=self._on_squash_complete,
                on_cancel=self._on_squash_cancel,
                title=f"JJ Squash: Select changes to squash into {dest_id}",
            )
        except ValueError as e:
            self.show_error(str(e))

    def _on_squash_complete(self, filtered_diff: str) -> None:
        """Execute the squash with the selected changes."""
        dest_id = self.destination.change_id
        self.show_status(f"Squashing selected changes into {dest_id}...")

        def on_result(success: bool, error: str) -> None:
            if success:
                self.show_status(f"Changes squashed into {dest_id}")
                refresh_all_views(self.window)
            else:
                self.show_error(f"Failed to squash: {error}")

        self.cli.squash_interactive(filtered_diff, "@", dest_id, on_result)

    def _on_squash_cancel(self) -> None:
        """Handle squash cancellation."""
        self.show_status("Squash cancelled")


class JjAbandonCommand(JjWindowCommand):
    """Abandon current change."""

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        def on_confirm(confirmed):
            if not confirmed:
                self.show_status("Abandon cancelled")
                return

            def on_result(success, error):
                if success:
                    self.show_status("Change abandoned")
                    refresh_all_views(self.window)
                else:
                    self.show_error(f"Failed to abandon: {error}")

            cli.abandon(on_result)

        self.window.show_quick_panel(
            [
                sublime.QuickPanelItem(
                    trigger="Abandon current change",
                    details="Discard all modifications",
                    kind=KIND_ACTION,
                ),
                sublime.QuickPanelItem(
                    trigger="Cancel",
                    details="Keep the current change",
                    kind=KIND_ACTION,
                ),
            ],
            lambda idx: on_confirm(idx == 0),
            placeholder="Confirm abandon?",
        )


class JjUndoCommand(JjWindowCommand):
    """Undo last jj operation."""

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        def on_result(success, error):
            if success:
                self.show_status("Undo successful")
                refresh_all_views(self.window)
            else:
                self.show_error(f"Failed to undo: {error}")

        cli.undo(on_result)


class JjPullRetrunkCommand(JjWindowCommand):
    """Fetch from git and rebase current stack onto trunk.

    Runs jj git fetch, then jj rebase -d trunk() -s roots(trunk()..stack(@)).
    Requires trunk() and stack() revset aliases to be configured.
    """

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli
        self.show_status("Fetching from git...")
        cli.git_fetch(self._on_fetch_complete)

    def _on_fetch_complete(self, success, error):
        if not success:
            self.show_error(f"Failed to fetch: {error}")
            return

        self.show_status("Rebasing stack onto trunk...")
        self.cli.rebase_stack_to_trunk(self._on_rebase_complete)

    def _on_rebase_complete(self, success, error):
        if success:
            self.show_status("Fetched and rebased onto trunk")
            refresh_all_views(self.window)
        else:
            self.show_error(f"Failed to rebase: {error}")


class JjEditCommand(JjWindowCommand):
    """Edit (checkout) a specific revision."""

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        def on_log(changes):
            if not changes:
                self.show_error("Could not get change log")
                return

            items = [
                build_change_quick_panel_item(change, include_immutable=False)
                for change in changes
            ]

            def on_select(idx):
                if idx < 0:
                    return

                selected = changes[idx]
                if selected.is_working_copy:
                    self.show_status("Already at this change")
                    return

                def on_result(success, error):
                    if success:
                        self.show_status(f"Now editing {selected.change_id}")
                        refresh_all_views(self.window)
                    else:
                        self.show_error(f"Failed to edit: {error}")

                cli.edit(selected.change_id, on_result)

            self.window.show_quick_panel(
                items, on_select, placeholder="Select change to edit"
            )

        # Show all ancestors - editing immutable creates a new mutable copy
        cli.get_log(on_log, revset="::", limit=DEFAULT_LOG_LIMIT)


class JjRefreshCommand(JjWindowCommand):
    """Refresh jj status for all views."""

    def run(self):
        refresh_all_views(self.window)
        self.show_status("Status refreshed")


class JjLogCommand(JjWindowCommand):
    """Show changes matching a custom revset expression."""

    # Common revset examples for the placeholder
    PLACEHOLDER = "mutable() | trunk()"

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli

        self.window.show_input_panel(
            "Revset expression:",
            self.PLACEHOLDER,
            self._on_revset_entered,
            None,
            None,
        )

    def _on_revset_entered(self, revset):
        if not revset.strip():
            return

        def on_log(changes):
            if not changes:
                self.show_status(f"No changes match revset: {revset}")
                return

            items = [build_change_quick_panel_item(change) for change in changes]

            def on_select(idx):
                if idx < 0:
                    return

                selected = changes[idx]
                if selected.is_working_copy:
                    self.show_status("Already at this change")
                    return

                def on_result(success, error):
                    if success:
                        self.show_status(f"Now editing {selected.change_id}")
                        refresh_all_views(self.window)
                    else:
                        self.show_error(f"Failed to edit: {error}")

                self.cli.edit(selected.change_id, on_result)

            self.window.show_quick_panel(
                items, on_select, placeholder="Select change to edit"
            )

        self.cli.get_log(on_log, revset=revset, limit=100)


class JjRebaseCommand(JjWindowCommand):
    """Unified rebase command with wizard-style UI."""

    OPERATIONS = [
        {
            "label": "Move this revision onto...",
            "description": "Rebase just this revision (-r -d)",
            "source_mode": "revision",
            "dest_mode": "onto",
        },
        {
            "label": "Move this + descendants onto...",
            "description": "Rebase revision and descendants (-s -d)",
            "source_mode": "source",
            "dest_mode": "onto",
        },
        {
            "label": "Move whole branch onto...",
            "description": "Rebase entire branch (-b -d)",
            "source_mode": "branch",
            "dest_mode": "onto",
        },
        {
            "label": "Insert this revision after...",
            "description": "Insert after target, moving target's descendants (-r -A)",
            "source_mode": "revision",
            "dest_mode": "after",
        },
        {
            "label": "Insert this + descendants after...",
            "description": "Insert with descendants after target (-s -A)",
            "source_mode": "source",
            "dest_mode": "after",
        },
        {
            "label": "Insert whole branch after...",
            "description": "Insert entire branch after target (-b -A)",
            "source_mode": "branch",
            "dest_mode": "after",
        },
        {
            "label": "Insert this revision before...",
            "description": "Insert before target (-r -B)",
            "source_mode": "revision",
            "dest_mode": "before",
        },
        {
            "label": "Insert this + descendants before...",
            "description": "Insert with descendants before target (-s -B)",
            "source_mode": "source",
            "dest_mode": "before",
        },
        {
            "label": "Insert whole branch before...",
            "description": "Insert entire branch before target (-b -B)",
            "source_mode": "branch",
            "dest_mode": "before",
        },
    ]

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli
        self._step1_select_source()

    def _step1_select_source(self):
        """Step 1: Select the revision to rebase."""

        def on_log(changes):
            if not changes:
                self.show_error("Could not get change log")
                return

            self.all_changes = changes

            # Build items for quick panel
            items = []
            # Track which index should be selected by default
            default_index = 0
            for i, change in enumerate(changes):
                items.append(
                    build_change_quick_panel_item(change, include_immutable=False)
                )
                # If @ is empty, default to the next one (@-)
                if change.is_working_copy and change.is_empty and i + 1 < len(changes):
                    default_index = i + 1
                elif change.is_working_copy and not change.is_empty:
                    default_index = i

            def on_select(idx):
                if idx < 0:
                    return
                self.selected_source = changes[idx]
                self._step2_select_operation()

            self.window.show_quick_panel(
                items,
                on_select,
                selected_index=default_index,
                placeholder="Select revision to begin rebasing",
            )

        # Only show mutable changes as rebase sources
        self.cli.get_log(on_log, revset="mutable()", limit=DEFAULT_LOG_LIMIT)

    def _step2_select_operation(self):
        """Step 2: Select the rebase operation type."""
        items = []
        for op in self.OPERATIONS:
            # Style the details based on operation type
            details = op["description"]

            # Colour based on source mode
            if op["source_mode"] == "source":
                # + descendants in cyan
                colour = "var(--cyanish)"
            elif op["source_mode"] == "branch":
                # whole branch in purple
                colour = "var(--purplish)"
            else:
                # single revision in default
                colour = "var(--foreground)"

            # Italicise before/after operations
            if op["dest_mode"] in ("before", "after"):
                details = f'<i style="color: {colour}">{details}</i>'
            else:
                details = f'<span style="color: {colour}">{details}</span>'

            items.append(
                sublime.QuickPanelItem(
                    trigger=op["label"],
                    details=details,
                    kind=KIND_ACTION,
                )
            )

        def on_select(idx):
            if idx < 0:
                return
            self.selected_operation = self.OPERATIONS[idx]
            self._step3_select_destination()

        self.window.show_quick_panel(
            items, on_select, placeholder="Select rebase operation"
        )

    def _step3_select_destination(self):
        """Step 3: Select the destination revision."""
        # Filter out the source revision from destinations
        exclude_ids = {self.selected_source.change_id}

        items = []
        valid_changes = []
        for change in self.all_changes:
            if change.change_id in exclude_ids:
                continue

            items.append(build_change_quick_panel_item(change))
            valid_changes.append(change)

        if not items:
            self.show_status("No valid destinations for rebase")
            return

        def on_select(idx):
            if idx < 0:
                return
            dest = valid_changes[idx]
            self._execute_rebase(dest)

        self.window.show_quick_panel(items, on_select, placeholder="Select destination")

    def _execute_rebase(self, dest):
        """Execute the rebase with selected options."""
        source_rev = self.selected_source.change_id
        source_mode = self.selected_operation["source_mode"]
        dest_mode = self.selected_operation["dest_mode"]

        def on_result(success, error):
            if success:
                dest_mode_display = "onto" if dest_mode == "onto" else dest_mode
                self.show_status(
                    f"Rebased {source_rev} {dest_mode_display} {dest.change_id}"
                )
                refresh_all_views(self.window)
            else:
                self.show_error(f"Failed to rebase: {error}")

        self.cli.rebase_flexible(
            source_mode, source_rev, dest_mode, dest.change_id, on_result
        )


class JjBookmarkSetCommand(JjWindowCommand):
    """Create or update a bookmark."""

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli

        def on_name(name):
            if not name.strip():
                self.show_status("Bookmark set cancelled (empty name)")
                return

            self.bookmark_name = name.strip()
            self._select_revision()

        self.window.show_input_panel(
            "Bookmark name:",
            "",
            on_name,
            None,
            None,
        )

    def _select_revision(self):
        """Select revision for the bookmark."""

        def on_log(changes):
            if not changes:
                self.show_error("Could not get change log")
                return

            items = [
                build_change_quick_panel_item(change, include_immutable=False)
                for change in changes
            ]

            def on_select(idx):
                if idx < 0:
                    return

                selected = changes[idx]

                def on_result(success, error):
                    if success:
                        self.show_status(
                            f"Bookmark '{self.bookmark_name}' set to {selected.change_id}"
                        )
                        refresh_all_views(self.window)
                    else:
                        self.show_error(f"Failed to set bookmark: {error}")

                self.cli.bookmark_set(self.bookmark_name, selected.change_id, on_result)

            self.window.show_quick_panel(
                items, on_select, placeholder="Select revision for bookmark"
            )

        self.cli.get_log(on_log, revset="::", limit=DEFAULT_LOG_LIMIT)


class JjBookmarkMoveCommand(JjWindowCommand):
    """Move an existing bookmark to a different revision."""

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli
        self._step1_select_bookmark()

    def _step1_select_bookmark(self):
        """Step 1: Select bookmark to move."""

        def on_bookmarks(bookmarks):
            if not bookmarks:
                self.show_status("No bookmarks found")
                return

            self.bookmarks = bookmarks
            items = []
            for bm in bookmarks:
                items.append(
                    sublime.QuickPanelItem(
                        trigger=bm.name,
                        details=f"{bm.change_id}: {bm.description}",
                        kind=KIND_BOOKMARK,
                    )
                )

            def on_select(idx):
                if idx < 0:
                    return
                self.selected_bookmark = bookmarks[idx]
                self._step2_select_revision()

            self.window.show_quick_panel(
                items, on_select, placeholder="Select bookmark to move"
            )

        self.cli.bookmark_list(on_bookmarks)

    def _step2_select_revision(self):
        """Step 2: Select target revision."""

        def on_log(changes):
            if not changes:
                self.show_error("Could not get change log")
                return

            items = [
                build_change_quick_panel_item(change, include_immutable=False)
                for change in changes
            ]

            def on_select(idx):
                if idx < 0:
                    return

                selected = changes[idx]

                def on_result(success, error):
                    if success:
                        self.show_status(
                            f"Moved bookmark '{self.selected_bookmark.name}' to {selected.change_id}"
                        )
                        refresh_all_views(self.window)
                    else:
                        self.show_error(f"Failed to move bookmark: {error}")

                self.cli.bookmark_move(
                    self.selected_bookmark.name, selected.change_id, on_result
                )

            self.window.show_quick_panel(
                items, on_select, placeholder="Select destination revision"
            )

        self.cli.get_log(on_log, revset="::", limit=DEFAULT_LOG_LIMIT)


class JjBookmarkDeleteCommand(JjWindowCommand):
    """Delete one or more bookmarks."""

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli
        self.selected_bookmarks = set()
        self._load_bookmarks()

    def _load_bookmarks(self):
        """Load bookmarks and show selection picker."""

        def on_bookmarks(bookmarks):
            if not bookmarks:
                self.show_status("No bookmarks found")
                return

            self.bookmarks = bookmarks
            self._show_bookmark_picker()

        self.cli.bookmark_list(on_bookmarks)

    def _show_bookmark_picker(self, restore_index=0):
        """Show bookmark picker with multi-select support."""
        items = []

        # Add "Delete" option at top if we have selections
        has_delete_option = bool(self.selected_bookmarks)
        if has_delete_option:
            items.append(
                sublime.QuickPanelItem(
                    trigger=f"Delete {len(self.selected_bookmarks)} bookmark(s)",
                    details="Confirm deletion",
                    kind=KIND_ACTION,
                )
            )

        # Add bookmarks with selection indicators
        for bm in self.bookmarks:
            is_selected = bm.name in self.selected_bookmarks
            details = f"{bm.change_id}: {bm.description}"
            if is_selected:
                details = f"<b>{details}</b>"
            items.append(
                sublime.QuickPanelItem(
                    trigger=bm.name,
                    details=details,
                    annotation="selected" if is_selected else "",
                    kind=KIND_BOOKMARK,
                )
            )

        def on_select(idx):
            if idx < 0:
                return

            offset = 1 if has_delete_option else 0

            if has_delete_option and idx == 0:
                # User selected "Delete" - confirm and execute
                self._confirm_delete()
            else:
                # Toggle selection
                bm = self.bookmarks[idx - offset]
                if bm.name in self.selected_bookmarks:
                    self.selected_bookmarks.remove(bm.name)
                else:
                    self.selected_bookmarks.add(bm.name)
                # Adjust index for picker refresh
                new_has_delete = bool(self.selected_bookmarks)
                new_idx = idx
                if new_has_delete and not has_delete_option:
                    new_idx = idx + 1
                elif not new_has_delete and has_delete_option:
                    new_idx = idx - 1
                self._show_bookmark_picker(restore_index=new_idx)

        self.window.show_quick_panel(
            items,
            on_select,
            selected_index=restore_index,
            placeholder="Select bookmarks to delete (toggle selection)",
        )

    def _confirm_delete(self):
        """Confirm deletion of selected bookmarks."""
        names = list(self.selected_bookmarks)
        msg = f"Delete {len(names)} bookmark(s): {', '.join(names)}?"

        def on_confirm(idx):
            if idx != 0:
                return

            def on_result(success, error):
                if success:
                    self.show_status(f"Deleted {len(names)} bookmark(s)")
                    refresh_all_views(self.window)
                else:
                    self.show_error(f"Failed to delete bookmarks: {error}")

            self.cli.bookmark_delete(names, on_result)

        self.window.show_quick_panel(
            [msg, "Cancel"],
            on_confirm,
            placeholder="Confirm deletion",
        )


class JjBookmarkRenameCommand(JjWindowCommand):
    """Rename a bookmark."""

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli
        self._step1_select_bookmark()

    def _step1_select_bookmark(self):
        """Step 1: Select bookmark to rename."""

        def on_bookmarks(bookmarks):
            if not bookmarks:
                self.show_status("No bookmarks found")
                return

            items = []
            for bm in bookmarks:
                items.append(
                    sublime.QuickPanelItem(
                        trigger=bm.name,
                        details=f"{bm.change_id}: {bm.description}",
                        kind=KIND_BOOKMARK,
                    )
                )

            def on_select(idx):
                if idx < 0:
                    return
                self.old_bookmark = bookmarks[idx]
                self._step2_enter_new_name()

            self.window.show_quick_panel(
                items, on_select, placeholder="Select bookmark to rename"
            )

        self.cli.bookmark_list(on_bookmarks)

    def _step2_enter_new_name(self):
        """Step 2: Enter new bookmark name."""

        def on_name(name):
            if not name.strip():
                self.show_status("Rename cancelled (empty name)")
                return

            new_name = name.strip()
            if new_name == self.old_bookmark.name:
                self.show_status("Rename cancelled (same name)")
                return

            def on_result(success, error):
                if success:
                    self.show_status(
                        f"Renamed bookmark '{self.old_bookmark.name}' to '{new_name}'"
                    )
                    refresh_all_views(self.window)
                else:
                    self.show_error(f"Failed to rename bookmark: {error}")

            self.cli.bookmark_rename(self.old_bookmark.name, new_name, on_result)

        self.window.show_input_panel(
            "New bookmark name:",
            self.old_bookmark.name,
            on_name,
            None,
            None,
        )


class JjBookmarkListCommand(JjWindowCommand):
    """List all bookmarks and optionally navigate to one."""

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli

        def on_bookmarks(bookmarks):
            if not bookmarks:
                self.show_status("No bookmarks found")
                return

            items = []
            for bm in bookmarks:
                items.append(
                    sublime.QuickPanelItem(
                        trigger=bm.name,
                        details=f"{bm.change_id}: {bm.description}",
                        kind=KIND_BOOKMARK,
                    )
                )

            def on_select(idx):
                if idx < 0:
                    return

                # Navigate to the selected bookmark's revision
                selected = bookmarks[idx]

                def on_result(success, error):
                    if success:
                        self.show_status(f"Now editing {selected.change_id}")
                        refresh_all_views(self.window)
                    else:
                        self.show_error(f"Failed to edit: {error}")

                self.cli.edit(selected.change_id, on_result)

            self.window.show_quick_panel(
                items, on_select, placeholder="Select bookmark to edit"
            )

        self.cli.bookmark_list(on_bookmarks)


class JjGitPushChangeCommand(JjWindowCommand):
    """Push a change by creating a bookmark (jj git push -c)."""

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli
        self._select_revision()

    def _select_revision(self):
        """Select revision to push."""

        def on_log(changes):
            if not changes:
                self.show_status("No pushable changes found")
                return

            items = []
            # Default to @- if @ is empty, otherwise @
            default_index = 0
            for i, change in enumerate(changes):
                items.append(
                    build_change_quick_panel_item(change, include_immutable=False)
                )
                # Default to @- if @ is empty
                if change.is_working_copy and change.is_empty and i + 1 < len(changes):
                    default_index = i + 1
                elif change.is_working_copy and not change.is_empty:
                    default_index = i

            def on_select(idx):
                if idx < 0:
                    return

                selected = changes[idx]
                self._execute_push(selected)

            self.window.show_quick_panel(
                items,
                on_select,
                selected_index=default_index,
                placeholder="Select change to push",
            )

        # Only show mutable changes - can't push immutable commits
        self.cli.get_log(on_log, revset="mutable()", limit=DEFAULT_LOG_LIMIT)

    def _execute_push(self, change):
        """Execute the push and handle result."""

        def on_result(success, error, bookmark_name, pr_url):
            if success:
                if bookmark_name:
                    self.show_status(
                        f"Pushed {change.change_id} as bookmark '{bookmark_name}'"
                    )
                else:
                    self.show_status(f"Pushed {change.change_id}")

                refresh_all_views(self.window)

                # If we have a PR URL, offer to open it
                if pr_url:
                    self._offer_open_pr(pr_url, bookmark_name)
            else:
                self.show_error(f"Failed to push: {error}")

        self.cli.git_push_change(change.change_id, on_result)

    def _offer_open_pr(self, pr_url, bookmark_name):
        """Offer to open the PR creation URL."""
        items = [
            sublime.QuickPanelItem(
                trigger="Open GitHub to create PR",
                details=pr_url,
                kind=KIND_ACTION,
            ),
            sublime.QuickPanelItem(
                trigger="Dismiss",
                details="Copy URL to clipboard instead",
                kind=KIND_ACTION,
            ),
        ]

        def on_select(idx):
            if idx == 0:
                webbrowser.open(pr_url)
            elif idx == 1:
                sublime.set_clipboard(pr_url)
                self.show_status("PR URL copied to clipboard")

        self.window.show_quick_panel(
            items, on_select, placeholder="Create pull request?"
        )
