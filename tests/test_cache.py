"""Tests for TTLCache."""

from unittest.mock import patch

from core.cache import TTLCache


class TestTTLCache:
    """Tests for TTLCache class."""

    def test_set_and_get_returns_value(self):
        """Getting a set value returns the value."""
        cache = TTLCache(default_ttl=5.0)
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_get_nonexistent_key_returns_none(self):
        """Getting a non-existent key returns None."""
        cache = TTLCache(default_ttl=5.0)
        assert cache.get("nonexistent") is None

    def test_get_expired_value_returns_none(self):
        """Getting an expired value returns None."""
        cache = TTLCache(default_ttl=5.0)

        # Set value at time 0
        with patch("core.cache.time.time", return_value=0):
            cache.set("key", "value")

        # Try to get value at time 10 (after TTL of 5)
        with patch("core.cache.time.time", return_value=10):
            assert cache.get("key") is None

    def test_custom_ttl_overrides_default(self):
        """Custom TTL per-key overrides the default TTL."""
        cache = TTLCache(default_ttl=5.0)

        # Set value with custom TTL of 20 seconds
        with patch("core.cache.time.time", return_value=0):
            cache.set("key", "value", ttl=20)

        # At time 10, should still be valid (custom TTL is 20)
        with patch("core.cache.time.time", return_value=10):
            assert cache.get("key") == "value"

        # At time 25, should be expired
        with patch("core.cache.time.time", return_value=25):
            assert cache.get("key") is None

    def test_invalidate_removes_key(self):
        """Invalidate removes a specific key."""
        cache = TTLCache(default_ttl=5.0)
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.invalidate("key1")

        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_invalidate_nonexistent_key_does_not_raise(self):
        """Invalidating a non-existent key does not raise an error."""
        cache = TTLCache(default_ttl=5.0)
        cache.invalidate("nonexistent")  # Should not raise

    def test_invalidate_prefix_removes_matching_keys(self):
        """Invalidate prefix removes all keys starting with the prefix."""
        cache = TTLCache(default_ttl=5.0)
        cache.set("repo:a:status", "status_a")
        cache.set("repo:a:diff", "diff_a")
        cache.set("repo:b:status", "status_b")

        cache.invalidate_prefix("repo:a")

        assert cache.get("repo:a:status") is None
        assert cache.get("repo:a:diff") is None
        assert cache.get("repo:b:status") == "status_b"

    def test_invalidate_prefix_preserves_non_matching(self):
        """Invalidate prefix preserves keys that do not match the prefix."""
        cache = TTLCache(default_ttl=5.0)
        cache.set("status:repo1", "value1")
        cache.set("diff:repo1", "value2")
        cache.set("status:repo2", "value3")

        cache.invalidate_prefix("status:")

        assert cache.get("status:repo1") is None
        assert cache.get("status:repo2") is None
        assert cache.get("diff:repo1") == "value2"

    def test_clear_removes_all_entries(self):
        """Clear removes all cached entries."""
        cache = TTLCache(default_ttl=5.0)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") is None
