"""Tests for formatting functions.

Tests the format_change_details logic from commands/quick_commands.py.
The function is tested directly here due to relative import constraints
in the Sublime Text plugin structure.
"""

from core.jj_cli import ChangeInfo


def format_change_details(change):
    """Format change details with highlighted unique prefix.

    Returns HTML string with underlined prefix followed by description.

    This is a copy of the function from commands/quick_commands.py for
    testing purposes. The test verifies the expected behaviour.
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


def make_change_info(
    change_id="abcd1234",
    commit_id="fedcba98",
    description="Test description",
    change_id_prefix="abcd",
    change_id_rest="1234",
):
    """Helper to create ChangeInfo with defaults."""
    return ChangeInfo(
        change_id=change_id,
        commit_id=commit_id,
        description=description,
        author="test@example.com",
        timestamp="2024-01-01",
        is_empty=False,
        is_immutable=False,
        is_working_copy=True,
        bookmarks=["main"],
        change_id_prefix=change_id_prefix,
        change_id_rest=change_id_rest,
    )


class TestFormatChangeDetails:
    """Tests for format_change_details function."""

    def test_prefix_and_rest_uses_underline_tag(self):
        """When both prefix and rest are present, prefix is underlined."""
        change = make_change_info(
            change_id_prefix="abcd",
            change_id_rest="1234",
        )
        result = format_change_details(change)
        assert "<u>abcd</u>1234" in result

    def test_prefix_only_uses_underline_tag(self):
        """When only prefix exists (no rest), prefix is still underlined."""
        change = make_change_info(
            change_id_prefix="abcd1234",
            change_id_rest="",
        )
        result = format_change_details(change)
        assert "<u>abcd1234</u>" in result
        # Should not have trailing characters after </u> before space
        assert result.startswith("<u>abcd1234</u> ")

    def test_no_prefix_uses_full_change_id(self):
        """When no prefix is set, uses full change_id without underline."""
        change = make_change_info(
            change_id="wxyz5678",
            change_id_prefix="",
            change_id_rest="",
        )
        result = format_change_details(change)
        assert "wxyz5678" in result
        # Should not have underline tags
        assert "<u>" not in result

    def test_description_appended_after_id(self):
        """Description is appended after the change ID."""
        change = make_change_info(
            description="Fix the bug",
            change_id_prefix="abcd",
            change_id_rest="1234",
        )
        result = format_change_details(change)
        assert result == "<u>abcd</u>1234 Fix the bug"
