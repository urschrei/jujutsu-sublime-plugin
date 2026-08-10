"""Tag management commands. Requires jj 0.44 or later."""

import sublime

from .base import JjWindowCommand
from .helpers import (
    KIND_ACTION,
    KIND_BOOKMARK,
    build_change_quick_panel_item,
    refresh_all_views,
)


class JjTagListCommand(JjWindowCommand):
    """List all tags; selecting one navigates to that revision."""

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli

        def on_tags(tags):
            if not tags:
                self.show_status("No tags found")
                return

            items = [
                sublime.QuickPanelItem(
                    trigger=tag.name,
                    details=f"{tag.change_id}: {tag.description}",
                    kind=KIND_BOOKMARK,
                )
                for tag in tags
            ]

            def on_select(idx):
                if idx < 0:
                    return
                selected = tags[idx]

                def on_result(success, error):
                    if success:
                        self.show_status(f"Now editing {selected.change_id}")
                        refresh_all_views(self.window)
                    else:
                        self.show_error(f"Failed to edit: {error}")

                self.cli.edit(selected.change_id, on_result)

            self.window.show_quick_panel(
                items, on_select, placeholder="Select tag to navigate to"
            )

        cli.tag_list(on_tags)


class JjTagSetCommand(JjWindowCommand):
    """Create or update a tag on a revision."""

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli

        def on_name(name):
            if not name.strip():
                self.show_status("Tag set cancelled (empty name)")
                return

            self.tag_name = name.strip()
            self._select_revision()

        self.window.show_input_panel("Tag name:", "", on_name, None, None)

    def _select_revision(self):
        """Select revision for the tag."""

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
                            f"Tag '{self.tag_name}' set to {selected.change_id}"
                        )
                        refresh_all_views(self.window)
                    else:
                        self.show_error(f"Failed to set tag: {error}")

                self.cli.tag_set(self.tag_name, selected.change_id, on_result)

            self.window.show_quick_panel(
                items, on_select, placeholder="Select revision for tag"
            )

        self.cli.get_log(on_log, revset="::", limit=50)


class JjTagDeleteCommand(JjWindowCommand):
    """Delete one or more tags."""

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli
        self.selected_tags = set()
        self._load_tags()

    def _load_tags(self):
        """Load tags and show selection picker."""

        def on_tags(tags):
            if not tags:
                self.show_status("No tags found")
                return

            self.tags = tags
            self._show_tag_picker()

        self.cli.tag_list(on_tags)

    def _show_tag_picker(self, restore_index=0):
        """Show tag picker with multi-select support."""
        items = []

        has_delete_option = bool(self.selected_tags)
        if has_delete_option:
            items.append(
                sublime.QuickPanelItem(
                    trigger=f"Delete {len(self.selected_tags)} tag(s)",
                    details="Confirm deletion",
                    kind=KIND_ACTION,
                )
            )

        for tag in self.tags:
            is_selected = tag.name in self.selected_tags
            details = f"{tag.change_id}: {tag.description}"
            if is_selected:
                details = f"<b>{details}</b>"
            items.append(
                sublime.QuickPanelItem(
                    trigger=tag.name,
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
                self._delete_selected()
                return

            tag = self.tags[idx - offset]
            if tag.name in self.selected_tags:
                self.selected_tags.remove(tag.name)
            else:
                self.selected_tags.add(tag.name)

            self._show_tag_picker(restore_index=idx)

        self.window.show_quick_panel(
            items,
            on_select,
            selected_index=restore_index,
            placeholder="Toggle tags to delete, then confirm",
        )

    def _delete_selected(self):
        """Delete the selected tags."""
        names = sorted(self.selected_tags)

        def on_result(success, error):
            if success:
                self.show_status(f"Deleted {len(names)} tag(s)")
                refresh_all_views(self.window)
            else:
                self.show_error(f"Failed to delete tags: {error}")

        self.cli.tag_delete(names, on_result)
