"""Workspace management commands."""

import os

import sublime

from ..views.diff_view import show_diff_view
from .base import JjWindowCommand
from .helpers import KIND_ACTION, KIND_WORKING_COPY, refresh_all_views


class JjWorkspaceListCommand(JjWindowCommand):
    """List workspaces; selecting one shows its working-copy diff.

    jj does not record workspace paths (workspaces can be moved), so the
    list cannot open other workspaces' directories.
    """

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli

        def on_current(current):
            current_id = current.change_id if current else None

            def on_workspaces(workspaces):
                if not workspaces:
                    self.show_error("Could not list workspaces")
                    return

                items = [
                    sublime.QuickPanelItem(
                        trigger=f"{ws.name}@",
                        details=f"{ws.change_id}: {ws.description}",
                        annotation="current" if ws.change_id == current_id else "",
                        kind=KIND_WORKING_COPY,
                    )
                    for ws in workspaces
                ]

                def on_select(idx):
                    if idx < 0:
                        return
                    selected = workspaces[idx]

                    def on_diff(success, text_or_error):
                        if not success:
                            self.show_error(f"Failed to get diff: {text_or_error}")
                            return
                        content = (
                            text_or_error.strip() or "(no changes in this working copy)"
                        )
                        show_diff_view(
                            self.window,
                            f"JJ Diff: {selected.name}@",
                            content + "\n",
                        )

                    self.cli.get_diff_raw(on_diff, revision=selected.change_id)

                self.window.show_quick_panel(
                    items,
                    on_select,
                    placeholder="Workspaces (select to view working-copy diff)",
                )

            self.cli.workspace_list(on_workspaces)

        cli.get_current_change(on_current)


class JjWorkspaceAddCommand(JjWindowCommand):
    """Add a workspace and open it in a new Sublime window."""

    def run(self):
        cli = self.get_cli()
        repo_root = self.get_repo_root()
        if cli is None or repo_root is None:
            return

        self.cli = cli
        self.repo_root = repo_root

        default_path = os.path.join(
            os.path.dirname(repo_root), os.path.basename(repo_root) + "-ws"
        )
        self.window.show_input_panel(
            "New workspace directory:", default_path, self._on_path, None, None
        )

    def _on_path(self, path):
        path = os.path.expanduser(path.strip())
        if not path:
            return
        if not os.path.isabs(path):
            path = os.path.join(os.path.dirname(self.repo_root), path)

        if os.path.exists(path) and os.listdir(path):
            self.show_error(f"Directory already exists and is not empty: {path}")
            return

        def on_result(success, error):
            if not success:
                self.show_error(f"Failed to add workspace: {error}")
                return

            self.show_status(f"Workspace created at {path}")
            refresh_all_views(self.window)
            self._open_window(path)

        # The workspace name defaults to the directory basename
        self.cli.workspace_add(path, on_result)

    def _open_window(self, path):
        """Open the new workspace in a new Sublime window."""
        sublime.run_command("new_window")
        new_window = sublime.active_window()
        new_window.set_project_data({"folders": [{"path": path}]})


class JjWorkspaceForgetCommand(JjWindowCommand):
    """Stop tracking one or more workspaces (multi-select)."""

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli
        self.selected_workspaces = set()
        self._load_workspaces()

    def _load_workspaces(self):
        def on_workspaces(workspaces):
            if not workspaces:
                self.show_error("Could not list workspaces")
                return
            if len(workspaces) == 1:
                self.show_status("Only one workspace exists")
                return

            self.workspaces = workspaces
            self._show_picker()

        self.cli.workspace_list(on_workspaces)

    def _show_picker(self, restore_index=0):
        items = []

        has_confirm = bool(self.selected_workspaces)
        if has_confirm:
            items.append(
                sublime.QuickPanelItem(
                    trigger=f"Forget {len(self.selected_workspaces)} workspace(s)",
                    details="Stop tracking their working-copy commits",
                    kind=KIND_ACTION,
                )
            )

        for ws in self.workspaces:
            is_selected = ws.name in self.selected_workspaces
            details = f"{ws.change_id}: {ws.description}"
            if is_selected:
                details = f"<b>{details}</b>"
            items.append(
                sublime.QuickPanelItem(
                    trigger=f"{ws.name}@",
                    details=details,
                    annotation="selected" if is_selected else "",
                    kind=KIND_WORKING_COPY,
                )
            )

        def on_select(idx):
            if idx < 0:
                return

            offset = 1 if has_confirm else 0

            if has_confirm and idx == 0:
                self._forget_selected()
                return

            ws = self.workspaces[idx - offset]
            if ws.name in self.selected_workspaces:
                self.selected_workspaces.remove(ws.name)
            else:
                self.selected_workspaces.add(ws.name)

            self._show_picker(restore_index=idx)

        self.window.show_quick_panel(
            items,
            on_select,
            selected_index=restore_index,
            placeholder="Toggle workspaces to forget, then confirm",
        )

    def _forget_selected(self):
        names = sorted(self.selected_workspaces)

        def on_result(success, error):
            if success:
                self.show_status(f"Forgot {len(names)} workspace(s)")
                refresh_all_views(self.window)
            else:
                self.show_error(f"Failed to forget workspaces: {error}")

        self.cli.workspace_forget(names, on_result)


class JjWorkspaceRenameCommand(JjWindowCommand):
    """Rename the current workspace."""

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli

        def on_done(name):
            name = name.strip()
            if not name:
                self.show_status("Rename cancelled (empty name)")
                return

            def on_result(success, error):
                if success:
                    self.show_status(f"Workspace renamed to {name}")
                else:
                    self.show_error(f"Failed to rename workspace: {error}")

            self.cli.workspace_rename(name, on_result)

        self.window.show_input_panel(
            "New name for current workspace:", "", on_done, None, None
        )


class JjWorkspaceUpdateStaleCommand(JjWindowCommand):
    """Update a stale working copy to the repo's current state.

    Needed after another workspace (or process) has rewritten this
    workspace's working-copy commit.
    """

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        def on_result(success, error):
            if success:
                self.show_status("Working copy updated")
                refresh_all_views(self.window)
            else:
                self.show_error(f"Failed to update: {error}")

        cli.workspace_update_stale(on_result)
