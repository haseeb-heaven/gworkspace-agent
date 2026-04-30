from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import AppConfigModel


class MemoryBackend(ABC):
    @abstractmethod
    def save_episode(self, goal: str, tasks: list[dict], outcome: str) -> None:
        pass

    @abstractmethod
    def recall_similar(self, goal: str, max_results: int = 3) -> list[dict]:
        pass

    @abstractmethod
    def add(
        self, data: str | list[dict[str, str]], user_id: str | None = None, metadata: dict[str, Any] | None = None
    ) -> None:
        pass

    @abstractmethod
    def search(self, query: str, user_id: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def get_all(self, user_id: str | None = None) -> list[dict[str, Any]]:
        pass

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


class LocalMemory(MemoryBackend):
    def __init__(self, config: AppConfigModel, logger: logging.Logger | None = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.logger.info("Local episodic memory initialized (JSONL).")

        # Load from config, fallback to home directory
        mem_dir = getattr(self.config, "memory_dir", None)
        if mem_dir:
            self.memory_file = Path(mem_dir) / "memory.jsonl"
        else:
            self.memory_file = Path.home() / ".gws_agent" / "memory.jsonl"

        # Semantic facts file (from config or default)
        if hasattr(self.config, "mem0_local_storage_path") and self.config.mem0_local_storage_path:
            self.facts_file = Path(self.config.mem0_local_storage_path)
        else:
            self.facts_file = self.memory_file.parent / "facts.jsonl"


        self._max_episodes = 500
        self._stop_words = frozenset(
            {
                "a",
                "an",
                "the",
                "is",
                "it",
                "its",
                "in",
                "on",
                "at",
                "to",
                "for",
                "of",
                "and",
                "or",
                "but",
                "my",
                "me",
                "i",
                "you",
                "we",
                "they",
                "this",
                "that",
                "with",
                "from",
                "by",
                "as",
                "be",
                "do",
                "get",
                "all",
                "some",
                "any",
                "can",
                "into",
                "up",
                "out",
                "use",
                "have",
                "has",
                "not",
                "no",
                "so",
                "if",
                "then",
                "about",
                "also",
            }
        )

    def _tokenize(self, text: str) -> set[str]:
        return {w for w in text.lower().split() if w not in self._stop_words and len(w) > 1}

    def save_episode(self, goal: str, tasks: list[dict], outcome: str) -> None:
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        episode = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "goal": goal,
            "tasks": tasks,
            "outcome": outcome,
        }

        with open(self.memory_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(episode) + "\n")
        self._prune_if_needed()

    def recall_similar(self, goal: str, max_results: int = 5) -> list[dict]:
        if not self.memory_file.exists():
            return []
        goal_words = self._tokenize(goal)
        if not goal_words:
            return []
        scored: list[tuple[int, dict]] = []
        with open(self.memory_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ep = json.loads(line)
                    past_words = self._tokenize(ep.get("goal", ""))
                    score = len(goal_words & past_words)
                    if score > 0:
                        scored.append((score, ep))
                except Exception:
                    continue
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:max_results]]

    def _prune_if_needed(self) -> None:
        if not self.memory_file.exists():
            return
        try:
            lines = self.memory_file.read_text(encoding="utf-8").splitlines(keepends=True)
            if len(lines) > self._max_episodes:
                self.memory_file.write_text("".join(lines[-self._max_episodes :]), encoding="utf-8")
        except Exception:
            pass

    def add(
        self, data: str | list[dict[str, str]], user_id: str | None = None, metadata: dict[str, Any] | None = None
    ) -> None:
        """Store a fact in local semantic memory."""
        self.facts_file.parent.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).isoformat()
        fact = {
            "id": str(datetime.now().timestamp()),
            "memory": str(data),
            "user_id": user_id or "default_user",
            "metadata": metadata or {},
            "created_at": timestamp,
            "updated_at": timestamp,
        }

        with open(self.facts_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(fact) + "\n")
        self.logger.debug(f"Saved fact to local memory: {self.facts_file}")

    def search(self, query: str, user_id: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        """Simple keyword search in local facts."""
        if not self.facts_file.exists():
            return []

        query_words = self._tokenize(query)
        if not query_words:
            return []

        scored: list[tuple[int, dict]] = []
        with open(self.facts_file, encoding="utf-8") as f:
            for line in f:
                try:
                    fact = json.loads(line.strip())
                    if user_id and fact.get("user_id") != user_id:
                        continue
                    content = fact.get("memory", "")
                    fact_words = self._tokenize(content)
                    score = len(query_words & fact_words)
                    if score > 0:
                        scored.append((score, fact))
                except Exception:
                    continue

        scored.sort(key=lambda x: x[0], reverse=True)
        return [f for _, f in scored[:limit]]

    def get_all(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """Retrieve all local facts."""
        if not self.facts_file.exists():
            return []

        results = []
        with open(self.facts_file, encoding="utf-8") as f:
            for line in f:
                try:
                    fact = json.loads(line.strip())
                    if user_id and fact.get("user_id") != user_id:
                        continue
                    results.append(fact)
                except Exception:
                    continue
        return results


class Mem0Memory(LocalMemory):
    def __init__(self, config: AppConfigModel, logger: logging.Logger | None = None):
        super().__init__(config, logger)
        self.client = None
        if config.mem0_api_key or config.mem0_host:
            try:
                from mem0 import MemoryClient

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
                self.logger.error("Failed to initialize Mem0 client: %s", e)
        else:
            try:
                from mem0 import Memory

                self.client = Memory()
                self.logger.info("Mem0 long-term memory client initialized (local).")
            except ImportError:
                self.logger.warning("mem0ai library not installed. Long-term memory disabled.")
            except Exception as e:
                self.logger.error("Failed to initialize local Mem0 memory: %s", e)

    def _default_user_id(self, user_id: str | None = None) -> str:
        return user_id or self.config.mem0_user_id or "default_user"

    def add(
        self, data: str | list[dict[str, str]], user_id: str | None = None, metadata: dict[str, Any] | None = None
    ) -> None:
        # 1. Save locally first (backup/offline)
        super().add(data, user_id, metadata)

        # 2. Save to Mem0 (remote/semantic)
        if not self.client:
            return

        resolved_user_id = self._default_user_id(user_id)
        try:
            self.client.add(data, user_id=resolved_user_id, metadata=metadata)
            self.logger.debug("Added memory to Mem0 for user %s", resolved_user_id)
        except Exception as e:
            self.logger.error("Error adding memory to Mem0: %s", e)

    def _build_filters(self, user_id: str) -> dict[str, Any]:
        return {"AND": [{"user_id": user_id}]}

    def search(self, query: str, user_id: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        if not self.client:
            return []

        resolved_user_id = self._default_user_id(user_id)
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                import contextlib
                import io

                from mem0 import MemoryClient

                # Suppress httpx stderr noise ("HTTP error occurred: ...")
                with contextlib.redirect_stderr(io.StringIO()):
                    if isinstance(self.client, MemoryClient):
                        filters = self._build_filters(resolved_user_id)
                        return self.client.search(query=query, version="v2", filters=filters, limit=limit)

                    return self.client.search(query, filters={"user_id": resolved_user_id}, limit=limit)
            except Exception as e:
                msg = str(e)
                if "429" in msg or "quota" in msg.lower():
                    if attempt < max_attempts - 1:
                        import time

                        delay = 1.0 * (attempt + 1)
                        self.logger.info("Mem0 rate-limited, retrying in %.0fs...", delay)
                        time.sleep(delay)
                        continue
                    self.logger.warning("Mem0 rate limit or quota exceeded. Continuing without long-term memory.")
                else:
                    self.logger.error("Error searching Mem0: %s", e)
                return []
        return []

    def get_all(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """Retrieve all memories for a user."""
        if not self.client:
            return []

        resolved_user_id = self._default_user_id(user_id)
        try:
            from mem0 import MemoryClient

            if isinstance(self.client, MemoryClient):
                filters = self._build_filters(resolved_user_id)
                response = self.client.get_all(version="v2", filters=filters)
                if isinstance(response, dict) and "results" in response:
                    return response["results"]
                return response

            try:
                return self.client.get_all(filters={"user_id": resolved_user_id})
            except Exception:
                return self.client.get_all(user_id=resolved_user_id)
        except Exception as e:
            msg = str(e)
            if "429" in msg or "quota" in msg.lower():
                self.logger.warning("Mem0 rate limit or quota exceeded. Skipping long-term memory retrieval.")
            else:
                self.logger.error("Error getting all memories from Mem0: %s", e)
            return []


def get_memory_backend(config: AppConfigModel, logger: logging.Logger | None = None) -> MemoryBackend:
    if config.memory_type in ("remote", "mem0"):
        return Mem0Memory(config, logger)
    return LocalMemory(config, logger)
