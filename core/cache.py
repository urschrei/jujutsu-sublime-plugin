"""TTL cache for expensive jj operations."""

import time
import threading


class TTLCache(object):
    """Simple TTL cache with thread-safe access."""

    def __init__(self, default_ttl=5.0):
        self._cache = {}
        self._lock = threading.Lock()
        self._default_ttl = default_ttl

    def get(self, key):
        """Get a cached value if it exists and hasn't expired."""
        with self._lock:
            if key in self._cache:
                expiry, value = self._cache[key]
                if time.time() < expiry:
                    return value
                else:
                    del self._cache[key]
        return None

    def set(self, key, value, ttl=None):
        """Set a cached value with optional custom TTL."""
        expiry = time.time() + (ttl if ttl is not None else self._default_ttl)
        with self._lock:
            self._cache[key] = (expiry, value)

    def invalidate(self, key):
        """Remove a specific key from the cache."""
        with self._lock:
            self._cache.pop(key, None)

    def invalidate_prefix(self, prefix):
        """Remove all keys starting with the given prefix."""
        with self._lock:
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for key in keys_to_remove:
                del self._cache[key]

    def clear(self):
        """Clear all cached values."""
        with self._lock:
            self._cache.clear()


# Global cache instance for repository data
repo_cache = TTLCache(default_ttl=5.0)
