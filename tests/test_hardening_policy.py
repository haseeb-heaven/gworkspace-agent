from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from gws_assistant.config import AppConfig
from gws_assistant.models import ExecutionResult


def _set_required_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DEFAULT_RECIPIENT_EMAIL", "recipient@example.test")
    monkeypatch.setenv("GWS_BINARY_PATH", str(tmp_path / "gws"))
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/free")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("MEM0_API_KEY", "")
    monkeypatch.setenv("MEM0_USER_ID", "test-user")


def test_config_defaults_to_openrouter_free_model(monkeypatch, tmp_path):
    _set_required_env(monkeypatch, tmp_path)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

    config = AppConfig.from_env()

    assert config.provider == "openrouter"
    assert config.model.endswith(":free") or config.model == "openrouter/free"


def test_config_rejects_openai_provider(monkeypatch, tmp_path):
    _set_required_env(monkeypatch, tmp_path)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")

    with pytest.raises(ValueError, match="Only OpenRouter free models"):
        AppConfig.from_env()


def test_config_rejects_non_free_openrouter_model(monkeypatch, tmp_path):
    _set_required_env(monkeypatch, tmp_path)
    monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-4.1-mini")

    with pytest.raises(ValueError, match="OpenRouter model must be a free model"):
        AppConfig.from_env()


def test_artifact_content_validation_rejects_invalid_values():
    from gws_assistant.execution.verifier import validate_artifact_content

    invalid_values = ["", "   ", None, "null", "None", "$last_sheet", "{{task-1.id}}", "___UNRESOLVED_PLACEHOLDER___"]

    for value in invalid_values:
        with pytest.raises(ValueError):
            validate_artifact_content(value, "unit-test")


def test_triple_verifier_checks_calendar_event_with_expected_fields():
    from gws_assistant.execution.verifier import TripleVerifier

    class Runner:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def run(self, args: list[str], timeout_seconds: int | None = None) -> ExecutionResult:
            self.calls.append(args)
            return ExecutionResult(
                success=True,
                command=["gws", *args],
                stdout=json.dumps({"id": "evt-1", "summary": "Planning Review"}),
                output={"id": "evt-1", "summary": "Planning Review"},
            )

    runner = Runner()
    verifier = TripleVerifier(runner, sleep_seconds=0)

    assert verifier.verify_resource("calendar", "evt-1", {"summary": "Planning Review"}) is True
    assert len(runner.calls) == 3
    assert all(call[:3] == ["calendar", "events", "get"] for call in runner.calls)


def test_mem0_bug_summary_uses_configured_user_id(monkeypatch, tmp_path):
    from gws_assistant.memory_backend import get_memory_backend
    from gws_assistant.models import AppConfigModel

    config = AppConfigModel(
        provider="openrouter",
        model="openrouter/free",
        api_key="or-test",
        base_url="https://openrouter.ai/api/v1",
        timeout_seconds=30,
        gws_binary_path=tmp_path / "gws",
        log_file_path=tmp_path / "log.txt",
        log_level="INFO",
        verbose=True,
        env_file_path=tmp_path / ".env",
        setup_complete=True,
        max_retries=3,
        langchain_enabled=True,
        mem0_api_key="test-key",
        mem0_user_id="agent-user",
    )

    memory = get_memory_backend(config)
    calls: list[dict] = []
    memory.client = type("Client", (), {"add": lambda self, data, user_id, metadata=None: calls.append({"data": data, "user_id": user_id, "metadata": metadata})})()

    memory.add_bug_fix(
        bug_id="BUG-123",
        service="gmail",
        root_cause="recipient was not normalized",
        applied_fix="forced DEFAULT_RECIPIENT_EMAIL",
        retry_count=1,
        affected_task="send_message",
    )

    assert calls[0]["user_id"] == "agent-user"
    assert calls[0]["metadata"]["bug_id"] == "BUG-123"
    assert "recipient was not normalized" in calls[0]["data"]


def test_live_scenario_grouping_and_python_env(monkeypatch, tmp_path):
    import importlib

    _set_required_env(monkeypatch, tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456")
    monkeypatch.setenv("PYTHON_EXE", sys.executable)

    import run_live_scenarios

    runner = importlib.reload(run_live_scenarios)
    groups = runner.group_tasks_by_service(
        [
            "Create a Google Calendar event",
            "Search Gmail and send email",
            "Read Google Drive document and save to Sheets",
        ]
    )

    assert "calendar" in groups
    assert "email" in groups
    assert "drive" in groups
    assert "sheets" in groups
    assert runner.load_runtime_config().python_exe == sys.executable


def test_live_task_log_redacts_secrets_and_records_attempt(monkeypatch, tmp_path):
    import importlib

    _set_required_env(monkeypatch, tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456")
    monkeypatch.setenv("PYTHON_EXE", sys.executable)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-super-secret-key")

    import run_live_scenarios

    runner = importlib.reload(run_live_scenarios)
    calls: list[list[str]] = []

    def fake_run(command, capture_output, text, encoding, env):
        calls.append(command)
        return type(
            "Result",
            (),
            {
                "returncode": 0,
                "stdout": "created sheet without placeholders",
                "stderr": "used or-super-secret-key",
            },
        )()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    monkeypatch.setattr(runner, "send_status", lambda *args, **kwargs: None)

    config = runner.load_runtime_config()
    result = runner.run_task("agent-sheets", "sheets", 0, "Create a Sheet", config, tmp_path)

    assert result.success is True
    assert calls[0][0] == sys.executable
    log_text = next(tmp_path.glob("*.jsonl")).read_text(encoding="utf-8")
    assert "or-super-secret-key" not in log_text
    assert '"attempt": 1' in log_text
