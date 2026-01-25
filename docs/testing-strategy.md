# Testing Strategy for SublimeJJ

This document describes the testing approach for SublimeJJ and provides guidance for adding tests when developing new features.

## Overview

SublimeJJ is a Sublime Text plugin, which presents unique testing challenges:

1. **Runtime dependency on Sublime Text**: The `sublime` and `sublime_plugin` modules only exist within Sublime Text's Python environment
2. **Relative imports**: The plugin uses relative imports that assume a specific package structure
3. **UI interactions**: Many features involve Sublime Text's UI (panels, input fields, status bar)

Our strategy focuses on testing the parts that can be tested in isolation, while accepting that some integration testing must be done manually within Sublime Text.

## What We Test

### High Priority (Always Test)

**Pure logic modules** - Functions and classes with no Sublime Text dependencies:

- `core/cache.py` - TTLCache for caching expensive operations
- `core/jj_cli.py` - CLI wrapper, output parsing, command construction
- `core/repo.py` - Repository detection and management

These provide the most value because:
- They contain complex logic that can break subtly
- They are easy to test in isolation
- Bugs here affect the entire plugin

**Command argument building** - The construction of jj CLI arguments:

```python
# Example: Testing that rebase_flexible builds correct flags
def test_source_mode_uses_s_flag(self):
    self.cli.rebase_flexible(
        source_mode="source",
        source_rev="abc123",
        dest_mode="onto",
        dest_rev="def456",
        callback=lambda *args: None,
    )
    assert "-s" in self.captured_args
```

**Output parsing** - Parsing jj command output into structured data:

```python
# Example: Testing change info parsing
def test_parse_basic_change(self):
    line = "abcd1234|||fedcba98|||Fix the bug|||..."
    info = self.cli._parse_change_info(line)
    assert info.change_id == "abcd1234"
```

**Error handling** - Edge cases and failure modes:

```python
# Example: Testing timeout handling
def test_timeout_returns_error(self):
    mock_process.communicate.side_effect = subprocess.TimeoutExpired(...)
    result = self.cli._run_sync(["long-running"])
    assert result.success is False
    assert "timed out" in result.stderr.lower()
```

### Medium Priority (Test When Practical)

**Formatting functions** - Functions that format data for display. These are often pure functions but may have import challenges due to the plugin structure.

**State management** - Singleton patterns, caching behaviour, instance lifecycle.

### Low Priority (Manual Testing)

**UI components** - Quick panels, input panels, phantoms, status bar updates. These require Sublime Text's runtime and are best tested manually.

**Event listeners** - `on_activated`, `on_post_save`, etc. These respond to editor events that are difficult to simulate.

**Command execution flow** - The full path from command invocation to UI update. Test the individual pieces, but verify the integration manually.

## Test Structure

### Directory Layout

```
tests/
├── conftest.py           # Shared fixtures and module mocks
├── test_cache.py         # TTLCache tests
├── test_cli_parsing.py   # Output parsing tests
├── test_command_args.py  # CLI argument construction
├── test_formatting.py    # Display formatting
├── test_repo_manager.py  # Repository detection
└── test_subprocess.py    # Process execution and error handling
```

### conftest.py Setup

The `conftest.py` file handles the Sublime Text module mocking:

```python
import sys
from unittest.mock import MagicMock

# Mock sublime module before any imports
sublime_mock = MagicMock()
sublime_mock.set_timeout = lambda fn, delay: fn()
sublime_mock.KIND_ID_VARIABLE = 1
# ... other constants
sys.modules["sublime"] = sublime_mock

# Mock sublime_plugin module
sublime_plugin_mock = MagicMock()
sublime_plugin_mock.WindowCommand = MagicMock
sublime_plugin_mock.TextCommand = MagicMock
sys.modules["sublime_plugin"] = sublime_plugin_mock
```

This allows importing from `core/` modules that reference `sublime`.

### Handling Import Constraints

The plugin's relative import structure (`from ..views.status_bar import ...`) can make testing `commands/` modules difficult. Two approaches:

**1. Test the logic directly** - If a function is pure, copy its logic to the test file:

```python
# In test_formatting.py
def format_change_details(change):
    """Copy of function from commands/quick_commands.py for testing."""
    if change.change_id_prefix and change.change_id_rest:
        return f"<u>{change.change_id_prefix}</u>{change.change_id_rest}"
    # ...
```

**2. Extract to core/** - Move pure functions to `core/` modules that have simpler import structures, then import and test normally.

## Writing Tests

### Test Naming

Use descriptive names that explain what is being tested:

```python
# Good
def test_get_expired_value_returns_none(self):
def test_multiple_sources_builds_multiple_from_flags(self):
def test_nested_file_walks_up_to_root(self):

# Avoid
def test_cache_1(self):
def test_it_works(self):
```

### Test Organisation

Group related tests in classes:

```python
class TestSquashFlexible:
    """Tests for squash_flexible argument building."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = JJCli("/tmp/fake-repo")

    def test_single_source_builds_from_flag(self):
        ...

    def test_multiple_sources_builds_multiple_from_flags(self):
        ...
```

### Mocking Strategies

**Mock subprocess.Popen** for testing CLI execution:

```python
def test_successful_command_returns_success(self):
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.communicate.return_value = (b"output", b"")

    with patch("subprocess.Popen", return_value=mock_process):
        result = self.cli._run_sync(["status"])

    assert result.success is True
```

**Mock time.time** for testing TTL expiration:

```python
def test_get_expired_value_returns_none(self):
    with patch("core.cache.time.time", return_value=0):
        cache.set("key", "value")  # Set at time 0

    with patch("core.cache.time.time", return_value=10):
        assert cache.get("key") is None  # Expired after TTL of 5
```

**Capture arguments** by replacing methods:

```python
def setup_method(self):
    self.captured_args = None

    def capture_run_async(args, callback, **kwargs):
        self.captured_args = args

    self.cli.run_async = capture_run_async
```

**Use tmp_path** for filesystem tests:

```python
def test_file_in_jj_repo_finds_root(self, tmp_path):
    jj_dir = tmp_path / ".jj"
    jj_dir.mkdir()

    test_file = tmp_path / "test.py"
    test_file.write_text("content")

    result = repo_manager.find_repo_root(str(test_file))
    assert result.root == str(tmp_path)
```

### Singleton Cleanup

When testing singletons like `RepoManager`, reset state between tests:

```python
@pytest.fixture
def clean_repo_manager():
    RepoManager._instance = None
    repo_cache.clear()
    yield RepoManager()
    RepoManager._instance = None
    repo_cache.clear()
```

## Adding Tests for New Features

When adding a new feature, consider:

### 1. Identify the Testable Parts

Break the feature into components:

- **Pure logic**: Parsing, formatting, data transformation
- **CLI interaction**: Command construction, output handling
- **UI presentation**: Panels, status updates, user input

Focus testing effort on the first two categories.

### 2. Write Tests First (When Practical)

For pure logic, writing tests first helps clarify the expected behaviour:

```python
# Define expected behaviour
def test_bookmark_with_remote_shows_tracking_status(self):
    bookmark = BookmarkInfo(name="main", tracking="origin/main", ...)
    result = format_bookmark_display(bookmark)
    assert "origin/main" in result
```

### 3. Test Edge Cases

Consider:

- Empty inputs
- Missing optional fields
- Malformed data
- Timeouts and errors
- Unicode handling

```python
def test_parse_malformed_line_returns_none(self):
    info = self.cli._parse_change_info("not enough fields")
    assert info is None

def test_unicode_output_decoded(self):
    mock_process.communicate.return_value = (
        "Hello \u00e9\u00e8".encode("utf-8"),
        b"",
    )
    result = self.cli._run_sync(["status"])
    assert result.stdout == "Hello \u00e9\u00e8"
```

### 4. Document Test Coverage Gaps

If something cannot be tested automatically, note it:

```python
class TestQuickPanel:
    """Tests for quick panel display.

    Note: Actual panel rendering requires Sublime Text runtime.
    These tests verify data preparation only.
    """
```

## Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_cache.py -v

# Run tests matching a pattern
uv run pytest tests/ -k "test_expired" -v

# Run with coverage (if pytest-cov is installed)
uv run pytest tests/ --cov=core --cov-report=term-missing
```

## Manual Testing Checklist

For changes that affect UI or integration, verify manually in Sublime Text:

1. **Reload the plugin**: Ctrl+Shift+P > "Package Development: Reload Plugin"
2. **Check the console**: View > Show Console for errors
3. **Test the happy path**: Does the feature work as expected?
4. **Test error cases**: What happens with invalid input?
5. **Test in different contexts**: Multiple windows, no file open, non-jj directory

## Summary

| Component | Test Approach |
|-----------|---------------|
| Cache logic | Unit tests with mocked time |
| CLI argument building | Capture args, verify structure |
| Output parsing | Unit tests with sample output |
| Error handling | Mock subprocess failures |
| Repository detection | Filesystem fixtures (tmp_path) |
| Formatting functions | Unit tests (may need function copy) |
| UI components | Manual testing in Sublime Text |
| Event listeners | Manual testing in Sublime Text |
