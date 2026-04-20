from __future__ import annotations

import logging
from typing import Any

from .memory_backend import get_memory_backend


class LongTermMemory:
    """Stable wrapper for unified memory backend (Mem0 + Local JSONL)."""

    def __init__(self, config: Any, logger: logging.Logger | None = None):
        self._backend = get_memory_backend(config, logger)

    def search(self, query: str, user_id: str | None = None, limit: int = 5):
        """Search long-term semantic memory (Mem0)."""
        return self._backend.search(query, user_id, limit)

    def add(self, data: str, user_id: str | None = None, metadata: dict | None = None):
        """Add fact to long-term semantic memory (Mem0)."""
        return self._backend.add(data, user_id, metadata)

    def recall_similar(self, goal: str, max_results: int = 3) -> list[dict]:
        """Recall similar past episodes from local memory."""
        return self._backend.recall_similar(goal, max_results)

    def save_episode(self, goal: str, tasks: list[dict], outcome: str):
        """Save a new episode to local memory."""
        self._backend.save_episode(goal, tasks, outcome)

# Module-level convenience functions for backward compatibility with simple callers
def recall_similar(goal: str, max_results: int = 3) -> list[dict]:
    from .config import AppConfig
    config = AppConfig.from_env()
    backend = get_memory_backend(config)
    return backend.recall_similar(goal, max_results)

def save_episode(goal: str, tasks: list[dict], outcome: str):
    from .config import AppConfig
    config = AppConfig.from_env()
    backend = get_memory_backend(config)
    backend.save_episode(goal, tasks, outcome)
