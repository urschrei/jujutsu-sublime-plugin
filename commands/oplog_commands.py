"""Operation log browsing and restore commands."""

import sublime

from .base import JjWindowCommand
from .helpers import KIND_ACTION, refresh_all_views

# Kind tuples for operation display
KIND_OPERATION = (sublime.KIND_ID_NAVIGATION, "O", "Operation")
KIND_CURRENT_OPERATION = (sublime.KIND_ID_FUNCTION, "@", "Current Operation")


def build_operation_quick_panel_item(op):
    """Build a QuickPanelItem for an operation."""
    annotations = [op.timestamp]
    if op.is_current:
        annotations.append("current")

    return sublime.QuickPanelItem(
        trigger=op.description,
        details=f"{op.op_id} by {op.user}",
        annotation=" | ".join(annotations),
        kind=KIND_CURRENT_OPERATION if op.is_current else KIND_OPERATION,
    )


class JjOpLogCommand(JjWindowCommand):
    """Browse the operation log; select an operation to restore to it.

    This is a safe multi-step undo: jj op restore is itself an operation,
    so a restore can in turn be undone.
    """

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli

        def on_op_log(operations):
            if not operations:
                self.show_error("Failed to read operation log")
                return

            items = [build_operation_quick_panel_item(op) for op in operations]

            def on_select(idx):
                if idx < 0:
                    return
                selected = operations[idx]
                if selected.is_current:
                    self.show_status("Already at this operation")
                    return
                self._confirm_restore(selected)

            self.window.show_quick_panel(
                items,
                on_select,
                placeholder="Select operation to restore to",
            )

        cli.op_log(on_op_log)

    def _confirm_restore(self, operation):
        """Ask for confirmation, then restore to the operation."""

        def on_confirm(confirmed):
            if not confirmed:
                self.show_status("Restore cancelled")
                return

            def on_result(success, error):
                if success:
                    self.show_status(f"Restored to operation {operation.op_id}")
                    refresh_all_views(self.window)
                else:
                    self.show_error(f"Failed to restore: {error}")

            self.cli.op_restore(operation.op_id, on_result)

        self.window.show_quick_panel(
            [
                sublime.QuickPanelItem(
                    trigger=f"Restore to {operation.op_id}",
                    details=f"{operation.description} ({operation.timestamp})",
                    annotation="restore is undoable via this same command",
                    kind=KIND_ACTION,
                ),
                sublime.QuickPanelItem(
                    trigger="Cancel",
                    details="Keep the current state",
                    kind=KIND_ACTION,
                ),
            ],
            lambda idx: on_confirm(idx == 0),
            placeholder="Restore repository to this operation?",
        )
