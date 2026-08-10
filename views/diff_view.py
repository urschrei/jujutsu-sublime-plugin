"""Read-only scratch views for command output."""

DIFF_SYNTAX = "Packages/Diff/Diff.sublime-syntax"


def show_scratch_view(window, name, content, syntax=None):
    """Open a read-only scratch view containing the given text."""
    view = window.new_file()
    view.set_name(name)
    view.set_scratch(True)
    if syntax:
        view.assign_syntax(syntax)
    view.settings().set("word_wrap", False)
    view.run_command("append", {"characters": content})
    view.set_read_only(True)
    return view


def show_diff_view(window, name, content):
    """Open a read-only scratch view containing diff output.

    Uses Sublime's built-in Diff syntax for highlighting.
    """
    return show_scratch_view(window, name, content, syntax=DIFF_SYNTAX)
