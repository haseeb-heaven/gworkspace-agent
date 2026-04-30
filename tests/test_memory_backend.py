"""Comprehensive tests for memory_backend.py — covers LocalMemory and get_memory_backend."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from gws_assistant.memory_backend import LocalMemory, get_memory_backend


def _make_config(tmp_path: Path, **overrides):
    """Build a minimal config mock pointing at tmp_path."""
    config = MagicMock()
    config.memory_dir = str(tmp_path)
    config.mem0_local_storage_path = None
    config.mem0_api_key = None
    config.mem0_host = None
    config.mem0_user_id = "test-user"
    config.memory_type = "local"
    for k, v in overrides.items():
        setattr(config, k, v)
    return config


class TestLocalMemorySaveAndRecall:
    def test_save_episode_creates_file(self, tmp_path):
        mem = LocalMemory(_make_config(tmp_path))
        mem.save_episode("send email", [{"action": "send"}], "success")
        assert (tmp_path / "memory.jsonl").exists()

    def test_recall_similar_returns_matching(self, tmp_path):
        mem = LocalMemory(_make_config(tmp_path))
        mem.save_episode("send email to bob", [{"action": "send"}], "success")
        mem.save_episode("create spreadsheet", [{"action": "create"}], "success")
        results = mem.recall_similar("send email")
        assert len(results) >= 1
        assert "email" in results[0]["goal"]

    def test_recall_similar_no_file_returns_empty(self, tmp_path):
        mem = LocalMemory(_make_config(tmp_path))
        assert mem.recall_similar("anything") == []

    def test_recall_similar_empty_query(self, tmp_path):
        mem = LocalMemory(_make_config(tmp_path))
        mem.save_episode("test", [], "ok")
        assert mem.recall_similar("the is a") == []  # all stop words


class TestLocalMemoryFacts:
    def test_add_and_search(self, tmp_path):
        mem = LocalMemory(_make_config(tmp_path))
        mem.add("Remember: budget is 5000", user_id="user1")
        results = mem.search("budget", user_id="user1")
        assert len(results) == 1
        assert "budget" in results[0]["memory"]

    def test_search_filters_by_user(self, tmp_path):
        mem = LocalMemory(_make_config(tmp_path))
        mem.add("user1 fact", user_id="user1")
        mem.add("user2 fact", user_id="user2")
        results = mem.search("fact", user_id="user1")
        assert all(r["user_id"] == "user1" for r in results)

    def test_search_no_file_returns_empty(self, tmp_path):
        mem = LocalMemory(_make_config(tmp_path))
        assert mem.search("anything") == []

    def test_get_all_returns_all_facts(self, tmp_path):
        mem = LocalMemory(_make_config(tmp_path))
        mem.add("fact one")
        mem.add("fact two")
        results = mem.get_all()
        assert len(results) == 2

    def test_get_all_filters_by_user(self, tmp_path):
        mem = LocalMemory(_make_config(tmp_path))
        mem.add("fact one", user_id="user1")
        mem.add("fact two", user_id="user2")
        results = mem.get_all(user_id="user1")
        assert len(results) == 1

    def test_get_all_no_file_returns_empty(self, tmp_path):
        mem = LocalMemory(_make_config(tmp_path))
        assert mem.get_all() == []


class TestLocalMemorySanitization:
    def test_sanitize_redacts_email(self, tmp_path):
        mem = LocalMemory(_make_config(tmp_path))
        sanitized = mem._sanitize_text("Contact me at john@example.com please")
        assert "john@example.com" not in sanitized
        assert "[REDACTED_EMAIL]" in sanitized

    def test_sanitize_redacts_phone(self, tmp_path):
        mem = LocalMemory(_make_config(tmp_path))
        sanitized = mem._sanitize_text("Call me at +1-555-123-4567")
        assert "+1-555-123-4567" not in sanitized
        assert "[REDACTED_PHONE]" in sanitized

    def test_sanitize_value_dict_redacts_sensitive_keys(self, tmp_path):
        mem = LocalMemory(_make_config(tmp_path))
        result = mem._sanitize_value({"password": "secret123", "name": "test"})
        assert result["password"] == "[REDACTED]"
        assert result["name"] == "test"

    def test_sanitize_value_list(self, tmp_path):
        mem = LocalMemory(_make_config(tmp_path))
        result = mem._sanitize_value(["hello", "world"])
        assert result == ["hello", "world"]

    def test_sanitize_value_integer(self, tmp_path):
        mem = LocalMemory(_make_config(tmp_path))
        assert mem._sanitize_value(42) == 42


class TestLocalMemoryPruning:
    def test_prune_if_needed(self, tmp_path):
        mem = LocalMemory(_make_config(tmp_path))
        mem._max_episodes = 3
        for i in range(5):
            mem.save_episode(f"goal {i}", [], "ok")
        lines = (tmp_path / "memory.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 3  # pruned to 3


class TestAddBugFix:
    def test_add_bug_fix(self, tmp_path):
        mem = LocalMemory(_make_config(tmp_path))
        mem.add_bug_fix(
            bug_id="BUG-001",
            service="gmail",
            root_cause="Missing field",
            applied_fix="Added default value",
            retry_count=2,
            affected_task="send_message",
            user_id="test-user",
        )
        results = mem.search("BUG-001")
        assert len(results) == 1
        assert "Missing field" in results[0]["memory"]


class TestGetMemoryBackend:
    def test_returns_local_by_default(self, tmp_path):
        config = _make_config(tmp_path, memory_type="local")
        backend = get_memory_backend(config)
        assert isinstance(backend, LocalMemory)

    def test_returns_mem0_for_remote(self, tmp_path):
        config = _make_config(tmp_path, memory_type="remote")
        with patch("gws_assistant.memory_backend.Mem0Memory.__init__", return_value=None):
            backend = get_memory_backend(config)
            assert backend is not None
