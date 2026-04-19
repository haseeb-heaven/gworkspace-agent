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



import uuid

# Maximum number of local memories to keep
_MAX_LOCAL_MEMORIES = 1000

class LocalJSONMemory:
    """A purely offline, JSONL-based memory system to replace local Mem0 without transformers."""
    
    def __init__(self, storage_path: str = ".gemini/memories.jsonl"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        # Ensure file exists
        if not self.storage_path.exists():
            self.storage_path.write_text("", encoding="utf-8")
            
    def _read_all(self) -> list[dict]:
        memories = []
        if not self.storage_path.exists():
            return memories
        with open(self.storage_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        memories.append(json.loads(line))
                    except Exception:
                        pass
        return memories

    def _write_all(self, memories: list[dict]) -> None:
        memories = memories[-_MAX_LOCAL_MEMORIES:]
        with open(self.storage_path, "w", encoding="utf-8") as f:
            for mem in memories:
                f.write(json.dumps(mem) + "\n")

    def add(self, data, user_id: str = None, metadata: dict = None) -> dict:
        user_id = user_id or "default_user"
        memories = self._read_all()
        mem_id = str(uuid.uuid4())
        new_mem = {
            "id": mem_id,
            "memory": data if isinstance(data, str) else json.dumps(data),
            "user_id": user_id,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        memories.append(new_mem)
        self._write_all(memories)
        return {"id": mem_id, "memory": new_mem["memory"], "event": "added"}

    def get_all(self, filters: dict = None, user_id: str = None) -> list[dict]:
        memories = self._read_all()
        uid = user_id
        if filters and "user_id" in filters:
            uid = filters["user_id"]
        if uid:
            memories = [m for m in memories if m.get("user_id") == uid]
        return memories

    def get(self, memory_id: str) -> dict | None:
        memories = self._read_all()
        for m in memories:
            if m["id"] == memory_id:
                return m
        return None

    def search(self, query: str, filters: dict = None, limit: int = 5, user_id: str = None) -> list[dict]:
        uid = user_id
        if filters and "user_id" in filters:
            uid = filters["user_id"]
            
        memories = self.get_all(user_id=uid)
        query_words = _tokenize(query)
        if not query_words:
            return memories[-limit:]
            
        scored = []
        for mem in memories:
            mem_words = _tokenize(mem.get("memory", ""))
            intersection = len(query_words & mem_words)
            if intersection > 0:
                score = intersection / len(query_words | mem_words)
                scored.append((score, mem))
                
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:limit]]

    def update(self, memory_id: str, data: str) -> dict | None:
        memories = self._read_all()
        updated_mem = None
        for m in memories:
            if m["id"] == memory_id:
                m["memory"] = data if isinstance(data, str) else json.dumps(data)
                m["updated_at"] = datetime.now(timezone.utc).isoformat()
                updated_mem = m
                break
                
        if updated_mem:
            self._write_all(memories)
            return {"id": memory_id, "memory": updated_mem["memory"], "event": "updated"}
        return None

    def delete(self, memory_id: str) -> dict:
        memories = self._read_all()
        initial_len = len(memories)
        memories = [m for m in memories if m["id"] != memory_id]
        
        if len(memories) < initial_len:
            self._write_all(memories)
            return {"id": memory_id, "event": "deleted"}
        return {"id": memory_id, "event": "not_found"}

class LongTermMemory:
    """Long-term memory layer using Mem0 for semantic persistence."""

    def __init__(self, config: AppConfigModel, logger: logging.Logger | None = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.client = None
        if config.mem0_api_key or config.mem0_host:
            try:
                kwargs = {}
                if config.mem0_api_key:
                    kwargs["api_key"] = config.mem0_api_key
                if config.mem0_host:
                    kwargs["host"] = config.mem0_host
                self.client = MemoryClient(**kwargs)
                self.logger.info("Mem0 long-term memory client initialized (hosted).")
            except ImportError:
                self.logger.warning("mem0ai library not installed. Long-term memory disabled.")
            except Exception as e:
                self.logger.error(f"Failed to initialize Mem0 client: {e}")
        else:
            # Fallback to local custom offline JSON memory
            try:
                self.client = LocalJSONMemory(".gemini/memories.jsonl")
                self.logger.info("Custom offline JSON long-term memory initialized (local).")
            except Exception as e:
                self.logger.error(f"Failed to initialize custom local memory: {e}")

    def _default_user_id(self, user_id: str | None = None) -> str:
        return user_id or self.config.mem0_user_id or "default_user"

    def add(self, data: str | list[dict[str, str]], user_id: str | None = None, metadata: dict[str, Any] | None = None) -> None:
        """Add a memory to Mem0."""
        if not self.client:
            return

        resolved_user_id = self._default_user_id(user_id)
        try:
            self.client.add(data, user_id=resolved_user_id, metadata=metadata)
            self.logger.debug(f"Added memory to Mem0 for user {resolved_user_id}")
        except Exception as e:
            self.logger.error(f"Error adding memory to Mem0: {e}")

    def add_bug_fix(
        self,
        *,
        bug_id: str,
        service: str,
        root_cause: str,
        applied_fix: str,
        retry_count: int,
        affected_task: str,
        user_id: str | None = None,
    ) -> None:
        """Persist a bug-fix learning with traceable metadata."""
        timestamp = datetime.now(timezone.utc).isoformat()
        metadata = {
            "type": "bug_fix",
            "bug_id": bug_id,
            "service": service,
            "root_cause": root_cause,
            "applied_fix": applied_fix,
            "retry_count": retry_count,
            "affected_task": affected_task,
            "timestamp": timestamp,
        }
        text = (
            f"Bug {bug_id} in {service}: root cause: {root_cause}. "
            f"Resolution: {applied_fix}. Affected task: {affected_task}. "
            f"Retries before fix: {retry_count}."
        )
        self.add(text, user_id=user_id, metadata=metadata)

    @staticmethod
    def _build_filters(user_id: str) -> dict[str, Any]:
        """Build the Mem0 filter shape accepted by the hosted client."""
        return {"user_id": user_id}

    def search(self, query: str, user_id: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        """Search for relevant memories in Mem0."""
        if not self.client:
                return []

        resolved_user_id = self._default_user_id(user_id)
        try:
                if isinstance(self.client, MemoryClient):
                        # Hosted Mem0 expects direct filters with v2 for user-scoped reads.
                        filters = self._build_filters(resolved_user_id)
                        response = self.client.search(query=query, version="v2", filters=filters, limit=limit)
                        if isinstance(response, dict) and "results" in response:
                                return response["results"]
                        return response
                else:
                        # Local/OSS client uses filters instead of direct user_id for some versions
                        try:
                            return self.client.search(query, filters={"user_id": resolved_user_id}, limit=limit)
                        except Exception:
                            # Fallback to filters if direct user_id not supported
                            return self.client.search(query, filters={"user_id": resolved_user_id}, limit=limit)
        except Exception as e:
                msg = str(e)
                if "429" in msg or "quota" in msg.lower():
                    self.logger.warning("Mem0 rate limit or quota exceeded. Skipping long-term memory search.")
                else:
                    self.logger.error(f"Error searching Mem0: {e}")
                return []

    def get_all(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """Retrieve all memories for a user."""
        if not self.client:
            return []

        resolved_user_id = self._default_user_id(user_id)
        try:
            from mem0 import MemoryClient
            if isinstance(self.client, MemoryClient):
                # Hosted Mem0 expects direct filters with v2 for user-scoped reads.
                filters = self._build_filters(resolved_user_id)
                response = self.client.get_all(version="v2", filters=filters)
                if isinstance(response, dict) and "results" in response:
                    return response["results"]
                return response
            else:
                # Local client: try filters first, fallback to user_id="..."
                try:
                    return self.client.get_all(filters={"user_id": resolved_user_id})
                except Exception:
                    return self.client.get_all(user_id=resolved_user_id)
        except Exception as e:
            msg = str(e)
            if "429" in msg or "quota" in msg.lower():
                self.logger.warning("Mem0 rate limit or quota exceeded. Skipping long-term memory retrieval.")
            else:
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
