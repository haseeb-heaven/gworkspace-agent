"""Episodic memory store for the agent — persists task executions to disk."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from mem0 import MemoryClient
from .models import AppConfigModel

MEMORY_FILE = Path.home() / ".gws_agent" / "memory.jsonl"

# Maximum number of episodes kept on disk. Oldest are pruned when exceeded.
_MAX_EPISODES = 500

# Common English stop-words that carry no semantic weight for recall matching.
_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "is", "it", "its", "in", "on", "at", "to", "for",
    "of", "and", "or", "but", "my", "me", "i", "you", "we", "they",
    "this", "that", "with", "from", "by", "as", "be", "do", "get",
    "all", "some", "any", "can", "into", "up", "out", "use", "have",
    "has", "not", "no", "so", "if", "then", "about", "also",
})


class LongTermMemory:
    """Long-term memory layer using Mem0 for semantic persistence."""

    def __init__(self, config: AppConfigModel, logger: logging.Logger | None = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.client = None
        if config.mem0_api_key:
            try:
                self.client = MemoryClient(api_key=config.mem0_api_key)
                self.logger.info("Mem0 long-term memory client initialized (hosted).")
            except ImportError:
                self.logger.warning("mem0ai library not installed. Long-term memory disabled.")
            except Exception as e:
                self.logger.error(f"Failed to initialize Mem0 client: {e}")
        else:
            # Fallback to local Memory if no API key is provided
            try:
                from mem0 import Memory
                self.client = Memory()
                self.logger.info("Mem0 long-term memory client initialized (local).")
            except ImportError:
                self.logger.warning("mem0ai library not installed. Long-term memory disabled.")
            except Exception as e:
                self.logger.error(f"Failed to initialize local Mem0 memory: {e}")

    def add(self, data: str | list[dict[str, str]], user_id: str = "default_user", metadata: dict[str, Any] | None = None) -> None:
        """Add a memory to Mem0."""
        if not self.client:
            return

        try:
            self.client.add(data, user_id=user_id, metadata=metadata)
            self.logger.debug(f"Added memory to Mem0 for user {user_id}")
        except Exception as e:
            self.logger.error(f"Error adding memory to Mem0: {e}")

    def search(self, query: str, user_id: str = "mem0-mcp-user", limit: int = 5) -> list[dict[str, Any]]:
        """Search for relevant memories in Mem0."""
        if not self.client:
                return []

        try:
                if isinstance(self.client, MemoryClient):
                        # Use documented v2 filter structure
                        filters = {"AND": [{"user_id": user_id}]}
                        return self.client.search(query=query, version="v2", filters=filters, limit=limit)
                else:
                        # Local/OSS client uses direct user_id
                        return self.client.search(query, user_id=user_id, limit=limit)
        except Exception as e:
                self.logger.error(f"Error searching Mem0: {e}")
                return []

    def get_all(self, user_id: str = "default_user") -> list[dict[str, Any]]:
        """Retrieve all memories for a user."""
        if not self.client:
            return []

        try:
            from mem0 import MemoryClient
            if isinstance(self.client, MemoryClient):
                # Use exact filter structure from documentation
                filters = {"AND": [{"user_id": user_id}]}
                response = self.client.get_all(filters=filters)
                if isinstance(response, dict) and "results" in response:
                    return response["results"]
                return response
            else:
                # Local client uses user_id="..."
                return self.client.get_all(user_id=user_id)
        except Exception as e:
            self.logger.error(f"Error getting all memories from Mem0: {e}")
            return []


def _tokenize(text: str) -> set[str]:
    """Lowercase-split and strip stop-words for meaningful keyword overlap."""
    return {w for w in text.lower().split() if w not in _STOP_WORDS and len(w) > 1}


def save_episode(goal: str, tasks: list[dict], outcome: str) -> None:
    """Append a completed task episode to the memory file and prune if needed."""
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    episode = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "goal": goal,
        "tasks": tasks,
        "outcome": outcome,
    }
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(episode) + "\n")
    _prune_if_needed()


def recall_similar(goal: str, max_results: int = 3) -> list[dict]:
    """Keyword-based recall from past episodes with stop-word filtering."""
    if not MEMORY_FILE.exists():
        return []
    goal_words = _tokenize(goal)
    if not goal_words:
        return []
    scored: list[tuple[int, dict]] = []
    with open(MEMORY_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ep = json.loads(line)
                past_words = _tokenize(ep.get("goal", ""))
                score = len(goal_words & past_words)
                if score > 0:
                    scored.append((score, ep))
            except Exception:
                continue
    scored.sort(key=lambda x: x[0], reverse=True)
    return [ep for _, ep in scored[:max_results]]


def _prune_if_needed() -> None:
    """Keep only the most recent _MAX_EPISODES lines in the memory file."""
    if not MEMORY_FILE.exists():
        return
    try:
        lines = MEMORY_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
        if len(lines) > _MAX_EPISODES:
            MEMORY_FILE.write_text("".join(lines[-_MAX_EPISODES:]), encoding="utf-8")
    except Exception:
        pass  # Never crash the agent due to memory housekeeping
