from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

from gws_assistant.gws_runner import GWSRunner


def test_runner_validate_binary(tmp_path):
    binary = tmp_path / os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws")
    binary.write_text("binary")
    runner = GWSRunner(binary, logging.getLogger("test"))
    assert runner.validate_binary() is True


def test_runner_success(monkeypatch, tmp_path):
    binary = tmp_path / os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws")
    binary.write_text("binary")
    runner = GWSRunner(binary, logging.getLogger("test"))

    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = runner.run(["drive", "files", "list"])
    assert result.success is True
    assert result.stdout == "ok"


def test_runner_timeout(monkeypatch):
    runner = GWSRunner(Path("missing.exe"), logging.getLogger("test"))

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["x"], timeout=1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = runner.run(["drive"], timeout_seconds=1)
    assert result.success is False
    assert "timed out" in (result.error or "").lower()

