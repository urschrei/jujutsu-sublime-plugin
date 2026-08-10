"""Run a command across a set of revisions, reporting results per change."""

import os

import sublime

from .base import JjWindowCommand

SETTINGS_FILE = "Jujutsu.sublime-settings"

OUTPUT_PANEL_NAME = "jj_run"

# Remembered within the session so re-runs prefill the previous values
_last_command = ""
_last_revset = ""


def build_shell_command(command_string):
    """Wrap a user command string for execution through the shell."""
    if os.name == "nt":
        return ["cmd", "/c", command_string]
    return ["sh", "-c", command_string]


class JjRunCommand(JjWindowCommand):
    """Run a command once per change in a revset (e.g. a test runner).

    Each revision is checked out into a private working copy by jj run;
    --ignore-changes ensures no commits are rewritten. Results are shown
    in an output panel: one summary line per change, with captured output
    for failures.
    """

    def run(self):
        cli = self.get_cli()
        if cli is None:
            return

        self.cli = cli

        self.window.show_input_panel(
            "Command to run per change:",
            _last_command,
            self._on_command,
            None,
            None,
        )

    def _on_command(self, command_string):
        global _last_command
        command_string = command_string.strip()
        if not command_string:
            return
        _last_command = command_string
        self.command_string = command_string

        settings = sublime.load_settings(SETTINGS_FILE)
        default_revset = _last_revset or settings.get(
            "run_default_revset", "trunk()..@ | @"
        )

        self.window.show_input_panel(
            "Revset:", default_revset, self._on_revset, None, None
        )

    def _on_revset(self, revset):
        global _last_revset
        revset = revset.strip()
        if not revset:
            return
        _last_revset = revset
        self.revset = revset

        def on_log(changes):
            if not changes:
                self.show_status(f"No changes match revset: {self.revset}")
                return

            # jj log lists newest first; run oldest to newest
            self.changes = list(reversed(changes))
            self.results = []
            self._open_panel()
            self._run_next(0)

        self.cli.get_log(on_log, revset=self.revset, limit=100)

    def _open_panel(self):
        """Create and show the output panel."""
        self.panel = self.window.create_output_panel(OUTPUT_PANEL_NAME)
        self.panel.settings().set("word_wrap", False)
        self.window.run_command("show_panel", {"panel": f"output.{OUTPUT_PANEL_NAME}"})
        self._append(
            f"$ {self.command_string}\n"
            f"revset: {self.revset} ({len(self.changes)} change(s))\n\n"
        )

    def _append(self, text):
        """Append text to the output panel."""
        self.panel.run_command("append", {"characters": text, "scroll_to_end": True})

    def _run_next(self, index):
        """Run the command for the change at index, then continue."""
        if index >= len(self.changes):
            self._finish()
            return

        change = self.changes[index]
        settings = sublime.load_settings(SETTINGS_FILE)
        timeout = settings.get("run_command_timeout", 600)

        def on_result(result):
            passed = result.success
            self.results.append(passed)

            status = "PASS" if passed else "FAIL"
            desc = change.description
            if len(desc) > 60:
                desc = desc[:57] + "..."
            self._append(f"{status}  {change.change_id}  {desc}\n")

            if not passed:
                output = (result.stdout + result.stderr).strip()
                if output:
                    indented = "".join(f"      {line}\n" for line in output.split("\n"))
                    self._append(indented)

            self._run_next(index + 1)

        self.cli.run_in_revision(
            build_shell_command(self.command_string),
            change.change_id,
            on_result,
            timeout=timeout,
        )

    def _finish(self):
        """Print the final summary."""
        passed = sum(1 for r in self.results if r)
        failed = len(self.results) - passed
        self._append(f"\n{passed} passed, {failed} failed\n")
        if failed:
            self.show_status(f"jj run: {failed} of {len(self.results)} failed")
        else:
            self.show_status(f"jj run: all {len(self.results)} passed")
