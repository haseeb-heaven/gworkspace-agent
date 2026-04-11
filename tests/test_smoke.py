from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]


def _run_command(args: list[str], env: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
        env=env,
    )


@pytest.mark.skipif(importlib.util.find_spec("rich") is None, reason="CLI runtime dependencies are not installed")
def test_cli_module_help_smoke():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path("src").resolve())
    result = _run_command([sys.executable, "-m", "gws_assistant.cli_app", "--help"], env=env)
    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0
    assert "Google Workspace Assistant CLI" in output
    assert "--setup" in output


@pytest.mark.skipif(importlib.util.find_spec("rich") is None, reason="CLI runtime dependencies are not installed")
def test_cli_launcher_help_smoke():
    result = _run_command([sys.executable, "cli.py", "--help"])
    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0
    assert "Google Workspace Assistant CLI" in output
    assert "--save-output" in output


@pytest.mark.skipif(importlib.util.find_spec("rich") is None, reason="CLI runtime dependencies are not installed")
def test_gws_cli_launcher_help_smoke():
    result = _run_command([sys.executable, "gws_cli.py", "--help"])
    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0
    assert "Google Workspace Assistant CLI" in output
    assert "--task" in output


@pytest.mark.skipif(not (ROOT / "gws.exe").exists(), reason="Bundled gws.exe is not present")
def test_gws_binary_help_smoke():
    result = _run_command([str(ROOT / "gws.exe"), "--help"])
    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0
    assert "Google Workspace CLI" in output
    assert "SERVICES:" in output


def test_gradio_launcher_help_smoke():
    result = _run_command([sys.executable, "gws_gradio.py", "--help"])
    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0
    assert "Run Google Workspace Assistant in Gradio" in output
    assert "--port" in output


@pytest.mark.skipif(os.getenv("RUN_OPENROUTER_SMOKE") != "1", reason="Set RUN_OPENROUTER_SMOKE=1 to run API smoke test")
def test_openrouter_chat_completion_smoke():
    env_file = dotenv_values(ROOT / ".env")
    api_key = os.getenv("OPENROUTER_API_KEY") or env_file.get("OPENROUTER_API_KEY")
    if not api_key:
        pytest.skip("OPENROUTER_API_KEY is not configured")

    model = (
        os.getenv("OPENROUTER_SMOKE_MODEL")
        or env_file.get("OPENROUTER_SMOKE_MODEL")
        or os.getenv("OPENROUTER_MODEL")
        or env_file.get("OPENROUTER_MODEL")
        or "openai/gpt-4.1-mini"
    )
    base_url = (
        os.getenv("OPENROUTER_BASE_URL")
        or env_file.get("OPENROUTER_BASE_URL")
        or "https://openrouter.ai/api/v1"
    ).rstrip("/")

    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": "Reply with only: ok"}],
            "max_tokens": 8,
            "temperature": 0,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost/google-workspace-cli",
            "X-Title": "google-workspace-cli smoke test",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = response.read().decode("utf-8")
            status = response.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        pytest.fail(f"OpenRouter smoke test failed with HTTP {exc.code}: {_sanitize_openrouter_error(body)}")
    except urllib.error.URLError as exc:
        pytest.fail(f"OpenRouter smoke test failed to connect: {exc.reason}")

    assert status == 200
    data = json.loads(body)
    assert data.get("choices"), f"OpenRouter response had no choices: {_sanitize_openrouter_error(body)}"


def _sanitize_openrouter_error(body: str) -> str:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body[:500]
    payload.pop("user_id", None)
    if isinstance(payload.get("error"), dict):
        metadata = payload["error"].get("metadata")
        if isinstance(metadata, dict):
            metadata.pop("raw", None)
    return json.dumps(payload, ensure_ascii=True)[:500]
