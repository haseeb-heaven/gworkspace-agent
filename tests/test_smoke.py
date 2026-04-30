import json
import os
import urllib.request
from pathlib import Path

import pytest
from dotenv import dotenv_values

ROOT = Path(__file__).parent.parent


def test_cli_module_help_smoke():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "gws_assistant", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0
    stdout = result.stdout or ""
    assert "usage" in stdout.lower()
    assert "assistant" in stdout.lower()


def test_gws_binary_help_smoke():
    import subprocess
    import os

    gws_path = os.getenv("GWS_BINARY_PATH")
    if not gws_path or not os.path.exists(gws_path):
        pytest.skip(f"GWS_BINARY_PATH not found or invalid: {gws_path}")

    result = subprocess.run(
        [gws_path, "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()


def test_gradio_launcher_help_smoke():
    import subprocess
    import sys

    # Check if gradio_launcher.py exists
    launcher_path = ROOT / "gradio_launcher.py"
    if not launcher_path.exists():
        pytest.skip("gradio_launcher.py not found")

    result = subprocess.run(
        [sys.executable, str(launcher_path), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()


@pytest.mark.skipif(
    os.getenv("RUN_OPENROUTER_SMOKE") != "1" and dotenv_values(ROOT / ".env").get("RUN_OPENROUTER_SMOKE") != "1",
    reason="Set RUN_OPENROUTER_SMOKE=1 in .env to run API smoke test"
)
def test_llm_chat_completion_smoke():
    env_file = dotenv_values(ROOT / ".env")
    api_key = os.getenv("LLM_API_KEY") or env_file.get("LLM_API_KEY")
    if not api_key:
        pytest.skip("LLM_API_KEY is not configured")

    provider = os.getenv("LLM_PROVIDER") or env_file.get("LLM_PROVIDER") or "google"
    model = (
        os.getenv("LLM_MODEL")
        or env_file.get("LLM_MODEL")
        or "google/gemini-2.5-flash"
    )
    
    full_model = model
    if provider and provider != "openai" and not model.startswith(f"{provider}/"):
        full_model = f"{provider}/{model}"

    import litellm
    try:
        response = litellm.completion(
            model=full_model,
            messages=[{"role": "user", "content": "Reply with only: ok"}],
            max_tokens=8,
            api_key=api_key,
        )
        content = response.choices[0].message.content.lower()
        assert "ok" in content
    except Exception as e:
        pytest.fail(f"LLM smoke test failed for {full_model}: {str(e)}")


def _sanitize_openrouter_error(body: str) -> str:
    try:
        data = json.loads(body)
        if "error" in data:
            err = data["error"]
            if isinstance(err, dict):
                return err.get("message", body)
            return str(err)
    except Exception:
        pass
    return body
