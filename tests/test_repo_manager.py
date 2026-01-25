"""Tests for RepoManager."""

import pytest

from core.cache import repo_cache
from core.repo import RepoManager


@pytest.fixture
def clean_repo_manager():
    """Create a fresh RepoManager instance for each test.

    Since RepoManager is a singleton, we need to reset its state.
    """
    # Clear the singleton instance
    RepoManager._instance = None
    # Clear the cache
    repo_cache.clear()
    yield RepoManager()
    # Clean up after test
    RepoManager._instance = None
    repo_cache.clear()


class TestRepoManagerFindRoot:
    """Tests for find_repo_root method."""

    def test_file_in_jj_repo_finds_root(self, tmp_path, clean_repo_manager):
        """File inside a jj repo returns the repo root."""
        # Create a .jj directory at the root
        jj_dir = tmp_path / ".jj"
        jj_dir.mkdir()

        # Create a file in the repo
        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        result = clean_repo_manager.find_repo_root(str(test_file))

        assert result is not None
        assert result.root == str(tmp_path)

    def test_nested_file_walks_up_to_root(self, tmp_path, clean_repo_manager):
        """Nested file walks up directories to find repo root."""
        # Create .jj at root
        jj_dir = tmp_path / ".jj"
        jj_dir.mkdir()

        # Create nested directory structure
        nested_dir = tmp_path / "src" / "deep" / "nested"
        nested_dir.mkdir(parents=True)

        # Create a file deep in the structure
        test_file = nested_dir / "module.py"
        test_file.write_text("content")

        result = clean_repo_manager.find_repo_root(str(test_file))

        assert result is not None
        assert result.root == str(tmp_path)

    def test_file_not_in_repo_returns_none(self, tmp_path, clean_repo_manager):
        """File outside any jj repo returns None."""
        # Create a file without any .jj directory
        test_file = tmp_path / "orphan.py"
        test_file.write_text("content")

        result = clean_repo_manager.find_repo_root(str(test_file))

        assert result is None

    def test_detects_colocated_git(self, tmp_path, clean_repo_manager):
        """Repo with both .jj and .git is marked as colocated."""
        # Create both .jj and .git directories
        jj_dir = tmp_path / ".jj"
        jj_dir.mkdir()
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        result = clean_repo_manager.find_repo_root(str(test_file))

        assert result is not None
        assert result.is_colocated is True

    def test_jj_only_not_colocated(self, tmp_path, clean_repo_manager):
        """Repo with only .jj (no .git) is not marked as colocated."""
        jj_dir = tmp_path / ".jj"
        jj_dir.mkdir()

        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        result = clean_repo_manager.find_repo_root(str(test_file))

        assert result is not None
        assert result.is_colocated is False

    def test_caches_results(self, tmp_path, clean_repo_manager):
        """Results are cached for performance."""
        jj_dir = tmp_path / ".jj"
        jj_dir.mkdir()

        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        # First call
        result1 = clean_repo_manager.find_repo_root(str(test_file))
        # Second call should hit cache
        result2 = clean_repo_manager.find_repo_root(str(test_file))

        assert result1.root == result2.root
        # Both should be valid
        assert result1 is not None
        assert result2 is not None

    def test_none_file_path_returns_none(self, clean_repo_manager):
        """None file path returns None."""
        result = clean_repo_manager.find_repo_root(None)
        assert result is None

    def test_empty_file_path_returns_none(self, clean_repo_manager):
        """Empty file path returns None."""
        result = clean_repo_manager.find_repo_root("")
        assert result is None


class TestRepoManagerGetCli:
    """Tests for get_cli method."""

    def test_get_cli_returns_cached_instance(self, tmp_path, clean_repo_manager):
        """get_cli returns the same JJCli instance for same repo."""
        jj_dir = tmp_path / ".jj"
        jj_dir.mkdir()

        file1 = tmp_path / "file1.py"
        file1.write_text("content")
        file2 = tmp_path / "file2.py"
        file2.write_text("content")

        cli1 = clean_repo_manager.get_cli(str(file1))
        cli2 = clean_repo_manager.get_cli(str(file2))

        assert cli1 is cli2

    def test_get_cli_for_non_repo_returns_none(self, tmp_path, clean_repo_manager):
        """get_cli for file not in repo returns None."""
        test_file = tmp_path / "orphan.py"
        test_file.write_text("content")

        result = clean_repo_manager.get_cli(str(test_file))

        assert result is None

    def test_get_cli_for_root_creates_instance(self, tmp_path, clean_repo_manager):
        """get_cli_for_root creates and caches JJCli instance."""
        cli1 = clean_repo_manager.get_cli_for_root(str(tmp_path))
        cli2 = clean_repo_manager.get_cli_for_root(str(tmp_path))

        assert cli1 is cli2
        assert cli1.repo_root == str(tmp_path)


class TestRepoManagerCacheInvalidation:
    """Tests for cache invalidation methods."""

    def test_clear_caches_removes_all(self, tmp_path, clean_repo_manager):
        """clear_caches removes all cached data."""
        jj_dir = tmp_path / ".jj"
        jj_dir.mkdir()

        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        # Populate cache
        clean_repo_manager.find_repo_root(str(test_file))

        # Clear caches
        clean_repo_manager.clear_caches()

        # Verify cache is cleared by checking repo_cache directly
        # The next find_repo_root call will need to re-scan
        cache_key = f"repo_root:{test_file}"
        assert repo_cache.get(cache_key) is None
