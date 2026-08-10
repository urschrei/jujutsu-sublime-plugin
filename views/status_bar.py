"""Status bar integration for jj."""

from ..core.repo import get_repo_manager


def update_status_bar(view):
    """Update the status bar with current jj change information."""
    if view is None or view.window() is None:
        return

    file_path = view.file_name()
    if file_path is None:
        # Try to get from window folders
        folders = view.window().folders()
        if folders:
            file_path = folders[0]
        else:
            view.erase_status("jj")
            return

    cli = get_repo_manager().get_cli(file_path)
    if cli is None:
        view.erase_status("jj")
        return

    def on_status_info(info, conflicted):
        if info is None:
            view.erase_status("jj")
            return

        # Format: jj: change_id (description)
        desc = info.description
        if len(desc) > 40:
            desc = desc[:37] + "..."

        markers = ""
        if info.is_empty:
            markers += " (empty)"
        if info.has_conflict:
            markers += " (conflict)"
        status = f"jj: {info.change_id}{markers} - {desc}"

        # Conflicts elsewhere in the repo (the working copy is already
        # flagged by its own marker above)
        others = [c for c in conflicted if not c.is_working_copy]
        if others:
            noun = "change" if len(others) == 1 else "changes"
            status += f" | {len(others)} conflicted {noun}"

        view.set_status("jj", status)

    cli.get_status_info(on_status_info)


def clear_status_bar(view):
    """Clear the jj status bar."""
    if view is not None:
        view.erase_status("jj")
