"""Scratch views displaying diff output."""

DIFF_SYNTAX = "Packages/Diff/Diff.sublime-syntax"


def show_diff_view(window, name, content):
    """Open a read-only scratch view containing diff output.

    Uses Sublime's built-in Diff syntax for highlighting.
    """
    view = window.new_file()
    view.set_name(name)
    view.set_scratch(True)
    view.assign_syntax(DIFF_SYNTAX)
    view.settings().set("word_wrap", False)
    view.run_command("append", {"characters": content})
    view.set_read_only(True)
    return view
