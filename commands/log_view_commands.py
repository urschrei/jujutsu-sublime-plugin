"""Commands for the persistent log view."""

import sublime
import sublime_plugin

from ..views.diff_view import show_diff_view
from ..views.log_view import (
    get_change_id_for_cursor,
    get_cli_for_log_view,
    is_log_view,
    open_log_view,
    render_log_view,
)
from .base import JjWindowCommand
from .helpers import KIND_ACTION, refresh_all_views

HELP_TEXT = """
<body id="jj-log-help">
    <style>
        body { padding: 0.5em; }
        h1 { font-size: 1.1em; }
        code { color: var(--accent); }
    </style>
    <h1>JJ Log View</h1>
    <p><code>enter</code> edit change under cursor</p>
    <p><code>o</code> show diff of change under cursor</p>
    <p><code>n</code> new change on top of change under cursor</p>
    <p><code>d</code> describe change under cursor</p>
    <p><code>a</code> abandon change under cursor</p>
    <p><code>s</code> squash change under cursor into its parent</p>
    <p><code>b</code> set bookmark on change under cursor</p>
    <p><code>r</code> refresh</p>
    <p><code>escape</code> close</p>
</body>
"""


class JjLogViewCommand(JjWindowCommand):
    """Open the persistent log view for the current repository."""

    def run(self):
        repo_root = self.get_repo_root()
        if repo_root is None:
            return
        open_log_view(self.window, repo_root)


class LogViewTextCommand(sublime_plugin.TextCommand):
    """Base class for commands operating inside the log view."""

    def is_enabled(self):
        return is_log_view(self.view)

    def get_cli(self):
        return get_cli_for_log_view(self.view)

    def get_target(self):
        """Get (cli, change_id) for the entry under the cursor."""
        cli = self.get_cli()
        change_id = get_change_id_for_cursor(self.view)
        if change_id is None:
            self.show_status("No change under cursor")
        return cli, change_id

    def refresh(self):
        render_log_view(self.view)
        window = self.view.window()
        if window is not None:
            refresh_all_views(window)

    def show_status(self, message):
        sublime.status_message(f"jj: {message}")

    def show_error(self, message):
        sublime.error_message(f"Jujutsu: {message}")


class JjLogViewReplaceCommand(sublime_plugin.TextCommand):
    """Internal: replace the entire contents of the log view."""

    def run(self, edit, content):
        self.view.replace(edit, sublime.Region(0, self.view.size()), content)

    def is_visible(self):
        return False


class JjLogViewRefreshCommand(LogViewTextCommand):
    """Re-render the log view."""

    def run(self, edit):
        self.refresh()


class JjLogViewEditCommand(LogViewTextCommand):
    """Edit (check out) the change under the cursor."""

    def run(self, edit):
        cli, change_id = self.get_target()
        if cli is None or change_id is None:
            return

        def on_result(success, error):
            if success:
                self.show_status(f"Now editing {change_id}")
                self.refresh()
            else:
                self.show_error(f"Failed to edit: {error}")

        cli.edit(change_id, on_result)


class JjLogViewNewCommand(LogViewTextCommand):
    """Create a new change on top of the change under the cursor."""

    def run(self, edit):
        cli, change_id = self.get_target()
        if cli is None or change_id is None:
            return

        def on_result(success, error):
            if success:
                self.show_status(f"Created new change on top of {change_id}")
                self.refresh()
            else:
                self.show_error(f"Failed to create change: {error}")

        cli.new(on_result, revision=change_id)


class JjLogViewDescribeCommand(LogViewTextCommand):
    """Set the description of the change under the cursor."""

    def run(self, edit):
        cli, change_id = self.get_target()
        if cli is None or change_id is None:
            return

        window = self.view.window()
        if window is None:
            return

        def on_done(message):
            if not message.strip():
                self.show_status("Describe cancelled (empty message)")
                return

            def on_result(success, error):
                if success:
                    self.show_status(f"Described {change_id}")
                    self.refresh()
                else:
                    self.show_error(f"Failed to describe: {error}")

            cli.describe(message, on_result, revision=change_id)

        window.show_input_panel(
            f"Description for {change_id}:", "", on_done, None, None
        )


class JjLogViewAbandonCommand(LogViewTextCommand):
    """Abandon the change under the cursor (with confirmation)."""

    def run(self, edit):
        cli, change_id = self.get_target()
        if cli is None or change_id is None:
            return

        window = self.view.window()
        if window is None:
            return

        def on_confirm(confirmed):
            if not confirmed:
                self.show_status("Abandon cancelled")
                return

            def on_result(success, error):
                if success:
                    self.show_status(f"Abandoned {change_id}")
                    self.refresh()
                else:
                    self.show_error(f"Failed to abandon: {error}")

            cli.abandon(on_result, revision=change_id)

        window.show_quick_panel(
            [
                sublime.QuickPanelItem(
                    trigger=f"Abandon {change_id}",
                    details="Discard this change (descendants are rebased)",
                    annotation="undoable via the operation log",
                    kind=KIND_ACTION,
                ),
                sublime.QuickPanelItem(
                    trigger="Cancel",
                    details="Keep the change",
                    kind=KIND_ACTION,
                ),
            ],
            lambda idx: on_confirm(idx == 0),
            placeholder=f"Abandon {change_id}?",
        )


class JjLogViewSquashCommand(LogViewTextCommand):
    """Squash the change under the cursor into its parent (with confirmation)."""

    def run(self, edit):
        cli, change_id = self.get_target()
        if cli is None or change_id is None:
            return

        window = self.view.window()
        if window is None:
            return

        def on_confirm(confirmed):
            if not confirmed:
                self.show_status("Squash cancelled")
                return

            def on_result(success, error):
                if success:
                    self.show_status(f"Squashed {change_id} into its parent")
                    self.refresh()
                else:
                    self.show_error(f"Failed to squash: {error}")

            cli.squash_flexible(
                sources=[change_id],
                destination=f"{change_id}-",
                use_dest_message=False,
                callback=on_result,
            )

        window.show_quick_panel(
            [
                sublime.QuickPanelItem(
                    trigger=f"Squash {change_id} into its parent",
                    details="Move its changes into the parent revision",
                    annotation="undoable via the operation log",
                    kind=KIND_ACTION,
                ),
                sublime.QuickPanelItem(
                    trigger="Cancel",
                    details="Keep the change",
                    kind=KIND_ACTION,
                ),
            ],
            lambda idx: on_confirm(idx == 0),
            placeholder=f"Squash {change_id} into its parent?",
        )


class JjLogViewBookmarkCommand(LogViewTextCommand):
    """Set a bookmark on the change under the cursor."""

    def run(self, edit):
        cli, change_id = self.get_target()
        if cli is None or change_id is None:
            return

        window = self.view.window()
        if window is None:
            return

        def on_done(name):
            name = name.strip()
            if not name:
                self.show_status("Bookmark cancelled (empty name)")
                return

            def on_result(success, error):
                if success:
                    self.show_status(f"Bookmark {name} set on {change_id}")
                    self.refresh()
                else:
                    self.show_error(f"Failed to set bookmark: {error}")

            cli.bookmark_set(name, change_id, on_result)

        window.show_input_panel(
            f"Bookmark name for {change_id}:", "", on_done, None, None
        )


class JjLogViewShowDiffCommand(LogViewTextCommand):
    """Show the diff of the change under the cursor in a scratch view."""

    def run(self, edit):
        cli, change_id = self.get_target()
        if cli is None or change_id is None:
            return

        window = self.view.window()
        if window is None:
            return

        def on_diff(success, text_or_error):
            if not success:
                self.show_error(f"Failed to get diff: {text_or_error}")
                return
            content = text_or_error.strip() or "(no changes in this revision)"
            show_diff_view(window, f"JJ Diff: {change_id}", content + "\n")

        cli.get_diff_raw(on_diff, revision=change_id)


class JjLogViewHelpCommand(LogViewTextCommand):
    """Show the key bindings available in the log view."""

    def run(self, edit):
        self.view.show_popup(HELP_TEXT, max_width=480)
