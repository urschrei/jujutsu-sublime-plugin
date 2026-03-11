"""Repository detection and state management."""

import os
import threading

from .cache import repo_cache
from .jj_cli import JJCli


class RepoInfo:
    """Information about a jj repository."""

    def __init__(self, root):
        self.root = root


class RepoManager:
    """Manages repository detection and caching."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = object.__new__(cls)
                cls._instance._repos = {}
                cls._instance._repo_lock = threading.Lock()
        return cls._instance

    def find_repo_root(self, file_path):
        """Find the jj repository root for a given file path.

        Returns None if not in a jj repository.
        """
        if not file_path:
            return None

        # Check cache first
        cache_key = f"repo_root:{file_path}"
        cached = repo_cache.get(cache_key)
        if cached is not None:
            return cached if cached != "none" else None

        # Walk up the directory tree looking for .jj
        if os.path.isfile(file_path):
            current = os.path.dirname(file_path)
        else:
            current = file_path

        while current and current != os.path.dirname(current):
            jj_dir = os.path.join(current, ".jj")
            if os.path.isdir(jj_dir):
                info = RepoInfo(root=current)
                repo_cache.set(cache_key, info, ttl=60.0)  # Cache for 1 minute
                return info
            current = os.path.dirname(current)

        # Cache negative result too
        repo_cache.set(cache_key, "none", ttl=30.0)
        return None

    def get_cli(self, file_path):
        """Get a JJCli instance for the repository containing the file.

        Returns None if the file is not in a jj repository.
        """
        repo_info = self.find_repo_root(file_path)
        if repo_info is None:
            return None

        with self._repo_lock:
            if repo_info.root not in self._repos:
                self._repos[repo_info.root] = JJCli(repo_info.root)
            return self._repos[repo_info.root]

    def get_cli_for_root(self, repo_root):
        """Get a JJCli instance for a known repository root."""
        with self._repo_lock:
            if repo_root not in self._repos:
                self._repos[repo_root] = JJCli(repo_root)
            return self._repos[repo_root]

    def invalidate_file(self, file_path):
        """Invalidate cache for a file (call after modifications)."""
        repo_info = self.find_repo_root(file_path)
        if repo_info:
            repo_cache.invalidate_prefix(f"diff:{repo_info.root}")
            repo_cache.invalidate_prefix(f"status:{repo_info.root}")

    def clear_caches(self):
        """Clear all caches."""
        repo_cache.clear()


def get_repo_manager():
    """Get the singleton RepoManager instance."""
    return RepoManager()
