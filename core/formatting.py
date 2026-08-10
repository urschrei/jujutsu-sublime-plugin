"""Formatting utilities for change display."""

import re

# A log view header line consists of graph symbols followed by an
# 8-character change id and two spaces. Change ids only use the letters
# k-z. Candidate matches are validated against the set of ids actually
# present in the log, which rules out description text that happens to
# look like an id.
LOG_HEADER_RE = re.compile(r"^[^0-9A-Za-z]*([k-z]{8})(?=\s{2})")


def build_log_line_map(content, valid_ids):
    """Map each rendered log line to the change id of its log entry.

    Lines before the first header map to None; all other lines map to
    the nearest header above them.
    """
    line_map = []
    current = None
    for line in content.split("\n"):
        match = LOG_HEADER_RE.match(line)
        if match and match.group(1) in valid_ids:
            current = match.group(1)
        line_map.append(current)
    return line_map


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
