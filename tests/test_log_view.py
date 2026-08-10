"""Tests for log view line mapping."""

from unittest import TestCase

from core.formatting import build_log_line_map as _build_line_map

GRAPH = """\
@  kwwrurty  (no description set) (empty)
│  user@example.com  2026-08-10 09:52
○  puzzpqxk  Add restore commands
│  user@example.com  2026-08-10 09:52
◆  ytwnzqwr  Add settings menu  [main]
│  user@example.com  2026-04-03 19:40
~
"""

VALID_IDS = {"kwwrurty", "puzzpqxk", "ytwnzqwr"}


class TestBuildLineMap(TestCase):
    """Test mapping of rendered graph lines to change ids."""

    def test_header_lines_map_to_their_change(self):
        """Header lines map to the change id they contain."""
        line_map = _build_line_map(GRAPH, VALID_IDS)

        self.assertEqual(line_map[0], "kwwrurty")
        self.assertEqual(line_map[2], "puzzpqxk")
        self.assertEqual(line_map[4], "ytwnzqwr")

    def test_detail_lines_inherit_previous_header(self):
        """Author/timestamp lines map to the entry above them."""
        line_map = _build_line_map(GRAPH, VALID_IDS)

        self.assertEqual(line_map[1], "kwwrurty")
        self.assertEqual(line_map[3], "puzzpqxk")
        self.assertEqual(line_map[5], "ytwnzqwr")

    def test_elided_line_inherits_previous_header(self):
        """The ~ elision marker maps to the entry above it."""
        line_map = _build_line_map(GRAPH, VALID_IDS)

        self.assertEqual(line_map[6], "ytwnzqwr")

    def test_lines_before_first_header_map_to_none(self):
        """Content before any header has no associated change."""
        line_map = _build_line_map("~\n" + GRAPH, VALID_IDS)

        self.assertIsNone(line_map[0])
        self.assertEqual(line_map[1], "kwwrurty")

    def test_id_like_description_text_is_not_a_header(self):
        """Description words that look like change ids are ignored."""
        graph = "@  kwwrurty  something\n│  monopoly  looks like an id but is not\n"
        line_map = _build_line_map(graph, VALID_IDS)

        self.assertEqual(line_map[0], "kwwrurty")
        self.assertEqual(line_map[1], "kwwrurty")

    def test_merge_graph_lines_are_handled(self):
        """Graph-only connector lines inherit the previous entry."""
        graph = "@    kwwrurty  merge change\n├─╮\n│ ○  puzzpqxk  side branch\n"
        line_map = _build_line_map(graph, VALID_IDS)

        self.assertEqual(line_map[0], "kwwrurty")
        self.assertEqual(line_map[1], "kwwrurty")
        self.assertEqual(line_map[2], "puzzpqxk")
