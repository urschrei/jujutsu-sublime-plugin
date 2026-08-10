"""File-oriented commands: history, annotation, and change evolution."""

import os

import sublime

from ..views.diff_view import show_diff_view, show_scratch_view
from .base import JjWindowCommand
from .helpers import KIND_CHANGE, build_change_quick_panel_item


def get_active_relpath(window, repo_root):
    """Return the active file's path relative to the repo root, or None."""
    view = window.active_view()
    if view is None or view.file_name() is None:
        return None
    rel_path = os.path.relpath(view.file_name(), repo_root)
    if rel_path.startswith(".."):
        return None
    return rel_path


class JjFileHistoryCommand(JjWindowCommand):
    """Show the changes that touched the current file.

    Selecting a change opens its diff, restricted to the file.
    """

    def run(self):
        cli = self.get_cli()
        repo_root = self.get_repo_root()
        if cli is None or repo_root is None:
            return

        rel_path = get_active_relpath(self.window, repo_root)
        if rel_path is None:
            self.show_status("No repository file in the active view")
            return

        def on_log(changes):
            if not changes:
                self.show_status(f"No history for {rel_path}")
                return

            items = [build_change_quick_panel_item(c) for c in changes]

            def on_select(idx):
                if idx < 0:
                    return
                selected = changes[idx]

                def on_diff(success, text_or_error):
                    if not success:
                        self.show_error(f"Failed to get diff: {text_or_error}")
                        return
                    content = text_or_error.strip() or "(no changes to this file)"
                    name = (
                        f"JJ Diff: {selected.change_id} - {os.path.basename(rel_path)}"
                    )
                    show_diff_view(self.window, name, content + "\n")

                cli.get_diff_raw(on_diff, revision=selected.change_id, paths=[rel_path])

            self.window.show_quick_panel(
                items,
                on_select,
                placeholder=f"History of {rel_path} (select to view diff)",
            )

        cli.get_log(on_log, revset="::@", limit=100, paths=[rel_path])


class JjAnnotateFileCommand(JjWindowCommand):
    """Annotate the current file with per-line change information."""

    def run(self):
        cli = self.get_cli()
        repo_root = self.get_repo_root()
        if cli is None or repo_root is None:
            return

        rel_path = get_active_relpath(self.window, repo_root)
        if rel_path is None:
            self.show_status("No repository file in the active view")
            return

        def on_annotate(success, text_or_error):
            if not success:
                self.show_error(f"Failed to annotate: {text_or_error}")
                return
            name = f"JJ Annotate: {os.path.basename(rel_path)}"
            show_scratch_view(self.window, name, text_or_error)

        cli.annotate_file(rel_path, on_annotate)


class JjEvologCommand(JjWindowCommand):
    """Show how the current change has evolved (its past versions).

    Selecting an entry opens the diff of that commit version.
    """

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        def on_evolog(entries):
            if not entries:
                self.show_status("No evolution history for the current change")
                return

            items = [
                sublime.QuickPanelItem(
                    trigger=entry.commit_id,
                    details=entry.description,
                    annotation=entry.timestamp,
                    kind=KIND_CHANGE,
                )
                for entry in entries
            ]

            def on_select(idx):
                if idx < 0:
                    return
                selected = entries[idx]

                def on_diff(success, text_or_error):
                    if not success:
                        self.show_error(f"Failed to get diff: {text_or_error}")
                        return
                    content = text_or_error.strip() or "(no changes in this version)"
                    show_diff_view(
                        self.window,
                        f"JJ Diff: {selected.commit_id}",
                        content + "\n",
                    )

                cli.get_diff_raw(on_diff, revision=selected.commit_id)

            self.window.show_quick_panel(
                items,
                on_select,
                placeholder="Evolution of the current change (select to view diff)",
            )

        cli.get_evolog(on_evolog)
