from __future__ import annotations

import logging
import os
import subprocess
import pytest
from pathlib import Path
from types import SimpleNamespace

from gws_assistant.gws_runner import GWSRunner, _validate_args


def test_runner_validate_binary(tmp_path):
    binary = tmp_path / Path(os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws")).name
    binary.write_text("binary")
    runner = GWSRunner(binary, logging.getLogger("test"))
    assert runner.validate_binary() is True


def test_runner_success(monkeypatch, tmp_path):
    binary = tmp_path / Path(os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws")).name
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


def test_runner_rejects_unexpected_short_flag():
    with pytest.raises(ValueError, match="Disallowed short argument"):
        _validate_args(["drive", "-x"])


def test_runner_detects_structured_failure_envelope(monkeypatch, tmp_path):
    binary = tmp_path / Path(os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws")).name
    binary.write_text("binary")
    runner = GWSRunner(binary, logging.getLogger("test"))

    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout='{"error":"bad request","code":400}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = runner.run(["drive", "files", "list"])
    assert result.success is False
    assert "bad request" in (result.error or "")


def test_runner_timeout_preserves_partial_output(monkeypatch):
    runner = GWSRunner(Path("missing.exe"), logging.getLogger("test"))

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["x"], timeout=1, output=b"partial stdout", stderr=b"partial stderr")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = runner.run(["drive"], timeout_seconds=1)
    assert result.success is False
    assert result.stdout == "partial stdout"
    assert result.stderr == "partial stderr"
