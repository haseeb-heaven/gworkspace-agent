"""Tests for setup_wizard module — covers discover_gws_binary and helper functions."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from gws_assistant.setup_wizard import discover_gws_binary, _quote, _render_env


class TestDiscoverGwsBinary:
    """Covers discover_gws_binary helper."""

    def test_returns_none_when_nothing_found(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("GWS_BINARY_PATH", raising=False)
        monkeypatch.chdir(tmp_path)
        with patch("shutil.which", return_value=None):
            assert discover_gws_binary() is None

    def test_finds_binary_in_cwd(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("GWS_BINARY_PATH", raising=False)
        monkeypatch.chdir(tmp_path)
        binary = tmp_path / "gws"
        binary.write_text("#!/bin/sh\necho ok", encoding="utf-8")
        with patch("shutil.which", return_value=None):
            result = discover_gws_binary()
            assert result is not None
            assert result.name == "gws"

    def test_finds_binary_from_env(self, tmp_path: Path, monkeypatch):
        binary = tmp_path / "my_gws"
        binary.write_text("#!/bin/sh\necho ok", encoding="utf-8")
        monkeypatch.setenv("GWS_BINARY_PATH", str(binary))
        monkeypatch.chdir(tmp_path)
        with patch("shutil.which", return_value=None):
            result = discover_gws_binary()
            assert result is not None
            assert "my_gws" in result.name


class TestQuote:
    """Covers the _quote helper."""

    def test_empty_string(self):
        assert _quote("") == ""

    def test_simple_value(self):
        assert _quote("hello") == "'hello'"

    def test_escapes_single_quote(self):
        assert _quote("it's") == "'it\\'s'"


class TestRenderEnv:
    """Covers _render_env output structure."""

    def test_render_env_contains_all_keys(self):
        values = {
            "LLM_PROVIDER": "openrouter",
            "OPENROUTER_API_KEY": "sk-123",
            "OPENROUTER_MODEL": "free",
            "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
            "TAVILY_API_KEY": "",
            "LANGCHAIN_ENABLED": "true",
            "CODE_EXECUTION_ENABLED": "true",
            "CODE_EXECUTION_BACKEND": "restricted_subprocess",
            "CODE_EXECUTION_TIMEOUT_SECONDS": "10",
            "CODE_EXECUTION_MEMORY_MB": "64",
            "CODE_EXECUTION_MAX_OUTPUT": "8192",
            "CODE_EXECUTION_DOCKER_IMAGE": "gws-sandbox:latest",
            "CODE_EXECUTION_DOCKER_BINARY": "docker",
            "E2B_API_KEY": "",
            "DEFAULT_RECIPIENT_EMAIL": "test@example.com",
            "MAX_RETRIES": "3",
            "GWS_BINARY_PATH": "/usr/bin/gws",
            "APP_LOG_LEVEL": "INFO",
            "APP_VERBOSE": "true",
            "APP_LOG_DIR": "logs",
            "LLM_TIMEOUT_SECONDS": "30",
        }
        rendered = _render_env(values)
        assert "LLM_PROVIDER" in rendered
        assert "OPENROUTER_API_KEY" in rendered
        assert "GWS_BINARY_PATH" in rendered
        assert "'openrouter'" in rendered
