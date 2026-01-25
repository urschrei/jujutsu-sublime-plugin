"""Formatting utilities for change display."""


def format_change_details(change):
    """Format change details with highlighted unique prefix.

    Returns HTML string with underlined prefix followed by description.
    """
    # Format the change ID with highlighted prefix
    if change.change_id_prefix and change.change_id_rest:
        change_id_html = f"<u>{change.change_id_prefix}</u>{change.change_id_rest}"
    elif change.change_id_prefix:
        # Prefix is the whole ID
        change_id_html = f"<u>{change.change_id_prefix}</u>"
    else:
        # Fallback to full change_id
        change_id_html = change.change_id

    return f"{change_id_html} {change.description}"
