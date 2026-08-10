"""Tests for CLI output parsing logic."""

from unittest import TestCase

from core.jj_cli import JJCli


class TestChangeInfoParsing(TestCase):
    """Test parsing of jj log output into ChangeInfo objects."""

    def setUp(self):
        """Create a CLI instance for testing."""
        self.cli = JJCli("/tmp/fake-repo")

    def test_parse_basic_change(self):
        """Test parsing a basic change line."""
        # Format: change_id|||commit_id|||description|||author|||timestamp|||
        #         is_empty|||is_immutable|||is_working_copy|||bookmarks|||
        #         prefix|||rest
        line = (
            "abcd1234|||fedcba98|||Fix the bug|||"
            "Test Author|||2024-01-01|||"
            "false|||false|||true|||main,dev|||"
            "abcd|||1234"
        )
        info = self.cli._parse_change_info(line)

        self.assertIsNotNone(info)
        self.assertEqual(info.change_id, "abcd1234")
        self.assertEqual(info.commit_id, "fedcba98")
        self.assertEqual(info.description, "Fix the bug")
        self.assertEqual(info.author, "Test Author")
        self.assertEqual(info.is_empty, False)
        self.assertEqual(info.is_immutable, False)
        self.assertEqual(info.is_working_copy, True)
        self.assertEqual(info.bookmarks, ["main", "dev"])
        self.assertEqual(info.change_id_prefix, "abcd")
        self.assertEqual(info.change_id_rest, "1234")

    def test_parse_empty_change(self):
        """Test parsing an empty change."""
        line = (
            "xyz789|||abc123|||(no description)|||"
            "Author|||2024-01-01|||"
            "true|||false|||false||||||"
            "xyz|||789"
        )
        info = self.cli._parse_change_info(line)

        self.assertIsNotNone(info)
        self.assertEqual(info.is_empty, True)
        self.assertEqual(info.description, "(no description)")
        self.assertEqual(info.bookmarks, [])

    def test_parse_immutable_change(self):
        """Test parsing an immutable change."""
        line = (
            "imm123|||cmt456|||Initial commit|||"
            "Author|||2024-01-01|||"
            "false|||true|||false|||trunk|||"
            "imm|||123"
        )
        info = self.cli._parse_change_info(line)

        self.assertIsNotNone(info)
        self.assertEqual(info.is_immutable, True)
        self.assertEqual(info.bookmarks, ["trunk"])

    def test_parse_conflicted_change(self):
        """Test parsing a change with a conflict flag."""
        line = (
            "abcd1234|||fedcba98|||Fix the bug|||"
            "Test Author|||2024-01-01|||"
            "false|||false|||true|||main|||"
            "abcd|||1234|||true"
        )
        info = self.cli._parse_change_info(line)

        self.assertIsNotNone(info)
        self.assertEqual(info.has_conflict, True)

    def test_parse_unconflicted_change(self):
        """Test parsing a change with an explicit false conflict flag."""
        line = (
            "abcd1234|||fedcba98|||Fix the bug|||"
            "Test Author|||2024-01-01|||"
            "false|||false|||true|||main|||"
            "abcd|||1234|||false"
        )
        info = self.cli._parse_change_info(line)

        self.assertIsNotNone(info)
        self.assertEqual(info.has_conflict, False)

    def test_parse_line_without_conflict_field(self):
        """Lines without the conflict field default to no conflict."""
        line = (
            "abcd1234|||fedcba98|||Fix the bug|||"
            "Test Author|||2024-01-01|||"
            "false|||false|||true|||main|||"
            "abcd|||1234"
        )
        info = self.cli._parse_change_info(line)

        self.assertIsNotNone(info)
        self.assertEqual(info.has_conflict, False)

    def test_parse_malformed_line_returns_none(self):
        """Test that malformed lines return None."""
        info = self.cli._parse_change_info("not enough fields")
        self.assertIsNone(info)

        info = self.cli._parse_change_info("")
        self.assertIsNone(info)


class TestResolveListParsing(TestCase):
    """Test parsing of jj resolve --list output."""

    def setUp(self):
        """Create a CLI instance for testing."""
        self.cli = JJCli("/tmp/fake-repo")

    def test_parse_conflicted_files(self):
        """Test parsing standard resolve --list output."""
        output = "a.txt    2-sided conflict\nsrc/b.py    2-sided conflict\n"
        files = self.cli._parse_resolve_list(output)

        self.assertEqual(len(files), 2)
        self.assertEqual(files[0].path, "a.txt")
        self.assertEqual(files[0].description, "2-sided conflict")
        self.assertEqual(files[1].path, "src/b.py")

    def test_parse_path_with_single_spaces(self):
        """Paths containing single spaces are kept intact."""
        output = "my file.txt    2-sided conflict\n"
        files = self.cli._parse_resolve_list(output)

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].path, "my file.txt")
        self.assertEqual(files[0].description, "2-sided conflict")

    def test_parse_tab_separated(self):
        """Tab-separated columns are handled."""
        output = "a.txt\t2-sided conflict\n"
        files = self.cli._parse_resolve_list(output)

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].path, "a.txt")
        self.assertEqual(files[0].description, "2-sided conflict")

    def test_parse_line_without_description(self):
        """A line with no separator falls back to path only."""
        output = "just-a-path.txt\n"
        files = self.cli._parse_resolve_list(output)

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].path, "just-a-path.txt")
        self.assertEqual(files[0].description, "")

    def test_parse_empty_output(self):
        """Empty output yields no files."""
        self.assertEqual(self.cli._parse_resolve_list(""), [])


class TestDiffParsing(TestCase):
    """Test parsing of git diff output."""

    def setUp(self):
        """Create a CLI instance for testing."""
        self.cli = JJCli("/tmp/fake-repo")

    def test_parse_added_lines(self):
        """Test parsing a diff with added lines."""
        diff = """diff --git a/file.py b/file.py
index 1234567..abcdefg 100644
--- a/file.py
+++ b/file.py
@@ -10,0 +11,3 @@
+new line 1
+new line 2
+new line 3
"""
        hunks = self.cli._parse_git_diff(diff, target_file="file.py")

        self.assertEqual(len(hunks), 1)
        self.assertEqual(hunks[0].hunk_type, "added")
        self.assertEqual(hunks[0].new_start, 11)
        self.assertEqual(hunks[0].new_count, 3)

    def test_parse_deleted_lines(self):
        """Test parsing a diff with deleted lines."""
        diff = """diff --git a/file.py b/file.py
index 1234567..abcdefg 100644
--- a/file.py
+++ b/file.py
@@ -5,2 +5,0 @@
-removed line 1
-removed line 2
"""
        hunks = self.cli._parse_git_diff(diff, target_file="file.py")

        self.assertEqual(len(hunks), 1)
        self.assertEqual(hunks[0].hunk_type, "deleted")

    def test_parse_modified_lines(self):
        """Test parsing a diff with modified lines."""
        diff = """diff --git a/file.py b/file.py
index 1234567..abcdefg 100644
--- a/file.py
+++ b/file.py
@@ -10,2 +10,2 @@
-old line
+new line
"""
        hunks = self.cli._parse_git_diff(diff, target_file="file.py")

        self.assertEqual(len(hunks), 1)
        self.assertEqual(hunks[0].hunk_type, "modified")


class TestHunkHeaderParsing(TestCase):
    """Test parsing of diff hunk headers."""

    def setUp(self):
        """Create a CLI instance for testing."""
        self.cli = JJCli("/tmp/fake-repo")

    def test_parse_standard_hunk_header(self):
        """Test parsing a standard @@ header."""
        result = self.cli._parse_hunk_header("@@ -10,5 +12,7 @@")

        self.assertIsNotNone(result)
        old_start, old_count, new_start, new_count = result
        self.assertEqual(old_start, 10)
        self.assertEqual(old_count, 5)
        self.assertEqual(new_start, 12)
        self.assertEqual(new_count, 7)

    def test_parse_single_line_hunk(self):
        """Test parsing a hunk with single line (no count)."""
        result = self.cli._parse_hunk_header("@@ -10 +12 @@")

        self.assertIsNotNone(result)
        old_start, old_count, new_start, new_count = result
        self.assertEqual(old_start, 10)
        self.assertEqual(old_count, 1)
        self.assertEqual(new_start, 12)
        self.assertEqual(new_count, 1)

    def test_parse_zero_count_hunk(self):
        """Test parsing a hunk with zero line count (pure add/delete)."""
        result = self.cli._parse_hunk_header("@@ -10,0 +11,3 @@")

        self.assertIsNotNone(result)
        old_start, old_count, new_start, new_count = result
        self.assertEqual(old_count, 0)
        self.assertEqual(new_count, 3)

    def test_create_hunk_added(self):
        """Test creating a hunk for added lines."""
        header = (10, 0, 11, 3)
        lines = ["+line1", "+line2", "+line3"]
        hunk = self.cli._create_hunk(header, lines)

        self.assertIsNotNone(hunk)
        self.assertEqual(hunk.hunk_type, "added")

    def test_create_hunk_modified(self):
        """Test creating a hunk for modified lines."""
        header = (10, 2, 10, 2)
        lines = ["-old", "+new"]
        hunk = self.cli._create_hunk(header, lines)

        self.assertIsNotNone(hunk)
        self.assertEqual(hunk.hunk_type, "modified")
