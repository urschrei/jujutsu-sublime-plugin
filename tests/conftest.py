"""Pytest configuration and fixtures."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add parent directory to path first
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Mock sublime module before any imports
sublime_mock = MagicMock()
sublime_mock.set_timeout = lambda fn, delay: fn()
sublime_mock.KIND_ID_VARIABLE = 1
sublime_mock.KIND_ID_FUNCTION = 2
sublime_mock.KIND_ID_MARKUP = 3
sublime_mock.KIND_ID_SNIPPET = 4
sys.modules["sublime"] = sublime_mock

# Mock sublime_plugin module
sublime_plugin_mock = MagicMock()
sublime_plugin_mock.WindowCommand = MagicMock
sublime_plugin_mock.TextCommand = MagicMock
sys.modules["sublime_plugin"] = sublime_plugin_mock


@pytest.fixture
def sample_change_info():
    """ChangeInfo fixture for formatting tests."""
    from core.jj_cli import ChangeInfo

    return ChangeInfo(
        change_id="abcd1234",
        commit_id="fedcba98",
        description="Test description",
        author="test@example.com",
        timestamp="2024-01-01",
        is_empty=False,
        is_immutable=False,
        is_working_copy=True,
        bookmarks=["main"],
        change_id_prefix="abcd",
        change_id_rest="1234",
    )


@pytest.fixture
def fresh_cache():
    """Fresh TTLCache for each test."""
    from core.cache import TTLCache

    return TTLCache(default_ttl=5.0)
