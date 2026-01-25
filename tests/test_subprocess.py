"""Tests for subprocess handling in _run_sync."""

import subprocess
from unittest.mock import MagicMock, patch

from core.jj_cli import JJCli


class TestRunSync:
    """Tests for _run_sync error handling and edge cases."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = JJCli("/tmp/fake-repo")

    def test_successful_command_returns_success(self):
        """Successful command returns JJResult with success=True."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"output", b"")

        with patch("subprocess.Popen", return_value=mock_process):
            result = self.cli._run_sync(["status"])

        assert result.success is True
        assert result.stdout == "output"
        assert result.stderr == ""
        assert result.returncode == 0

    def test_failed_command_returns_failure(self):
        """Failed command returns JJResult with success=False."""
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"error message")

        with patch("subprocess.Popen", return_value=mock_process):
            result = self.cli._run_sync(["invalid-command"])

        assert result.success is False
        assert result.stderr == "error message"
        assert result.returncode == 1

    def test_timeout_returns_error(self):
        """Timed out command returns error with returncode -1."""
        mock_process = MagicMock()
        mock_process.communicate.side_effect = subprocess.TimeoutExpired(
            cmd="jj", timeout=30
        )

        with patch("subprocess.Popen", return_value=mock_process):
            result = self.cli._run_sync(["long-running"])

        assert result.success is False
        assert "timed out" in result.stderr.lower()
        assert result.returncode == -1
        mock_process.kill.assert_called_once()

    def test_missing_executable_returns_os_error(self):
        """Missing jj executable returns OSError result."""
        with patch("subprocess.Popen", side_effect=OSError("No such file")):
            result = self.cli._run_sync(["status"])

        assert result.success is False
        assert "not found" in result.stderr.lower()
        assert result.returncode == -1

    def test_environment_includes_no_color(self):
        """Environment passed to Popen includes NO_COLOR=1."""
        captured_env = None

        def capture_popen(*args, **kwargs):
            nonlocal captured_env
            captured_env = kwargs.get("env", {})
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b"", b"")
            return mock_process

        with patch("subprocess.Popen", side_effect=capture_popen):
            self.cli._run_sync(["status"])

        assert captured_env is not None
        assert captured_env.get("NO_COLOR") == "1"

    def test_unicode_output_decoded(self):
        """Unicode output is properly decoded."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        # UTF-8 encoded string with non-ASCII characters
        mock_process.communicate.return_value = (
            "Hello \u00e9\u00e8\u00ea".encode("utf-8"),
            b"",
        )

        with patch("subprocess.Popen", return_value=mock_process):
            result = self.cli._run_sync(["status"])

        assert result.success is True
        assert result.stdout == "Hello \u00e9\u00e8\u00ea"

    def test_invalid_unicode_handled_gracefully(self):
        """Invalid UTF-8 bytes are handled with replacement characters."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        # Invalid UTF-8 sequence
        mock_process.communicate.return_value = (b"Hello \xff\xfe World", b"")

        with patch("subprocess.Popen", return_value=mock_process):
            result = self.cli._run_sync(["status"])

        assert result.success is True
        # Should contain replacement characters, not raise an exception
        assert "Hello" in result.stdout
        assert "World" in result.stdout

    def test_generic_exception_returns_error(self):
        """Generic exceptions are caught and returned as errors."""
        with patch("subprocess.Popen", side_effect=RuntimeError("Unexpected error")):
            result = self.cli._run_sync(["status"])

        assert result.success is False
        assert "Unexpected error" in result.stderr
        assert result.returncode == -1

    def test_custom_cwd_passed_to_popen(self):
        """Custom cwd parameter is passed to Popen."""
        captured_cwd = None

        def capture_popen(*args, **kwargs):
            nonlocal captured_cwd
            captured_cwd = kwargs.get("cwd")
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b"", b"")
            return mock_process

        with patch("subprocess.Popen", side_effect=capture_popen):
            self.cli._run_sync(["status"], cwd="/custom/path")

        assert captured_cwd == "/custom/path"

    def test_default_cwd_uses_repo_root(self):
        """Default cwd uses the repository root."""
        captured_cwd = None

        def capture_popen(*args, **kwargs):
            nonlocal captured_cwd
            captured_cwd = kwargs.get("cwd")
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b"", b"")
            return mock_process

        with patch("subprocess.Popen", side_effect=capture_popen):
            self.cli._run_sync(["status"])

        assert captured_cwd == "/tmp/fake-repo"
