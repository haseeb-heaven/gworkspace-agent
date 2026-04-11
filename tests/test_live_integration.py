from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pytest

from gws_assistant.gws_runner import GWSRunner
from gws_assistant.models import AppConfigModel
from gws_assistant.planner import CommandPlanner


@pytest.mark.live_integration
def test_live_workspace_sheet_and_email_flow():
    if os.getenv("RUN_LIVE_INTEGRATION") != "true":
        pytest.skip("RUN_LIVE_INTEGRATION is not enabled.")

    recipient = (os.getenv("LIVE_TEST_RECIPIENT_EMAIL") or "").strip()
    if not recipient:
        pytest.skip("LIVE_TEST_RECIPIENT_EMAIL is required for live email verification.")

    gws_binary = Path((os.getenv("GWS_BINARY_PATH") or "gws.exe")).expanduser()
    if not gws_binary.exists():
        pytest.skip("GWS_BINARY_PATH does not exist for live integration run.")

    config = AppConfigModel(
        provider=(os.getenv("LLM_PROVIDER") or "openai"),
        model=(os.getenv("LLM_MODEL") or "gpt-4.1-mini"),
        api_key=(os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip() or None,
        base_url=None,
        timeout_seconds=60,
        gws_binary_path=gws_binary,
        log_file_path=Path("logs/live_integration.log"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        verbose=True,
        env_file_path=Path(".env").resolve(),
        setup_complete=True,
        max_retries=2,
        langchain_enabled=True,
        use_heuristic_fallback=False,
        code_execution_enabled=True,
    )
    planner = CommandPlanner()
    runner = GWSRunner(config.gws_binary_path, logging.getLogger("live-integration"))

    create_cmd = planner.build_command("sheets", "create_spreadsheet", {"title": "CI Live Integration Sheet"})
    create_result = runner.run(create_cmd, timeout_seconds=90)
    assert create_result.success, f"Failed to create spreadsheet: {create_result.stderr or create_result.error}"
    sheet_payload = json.loads(create_result.stdout or "{}")
    spreadsheet_id = sheet_payload.get("spreadsheetId")
    spreadsheet_url = sheet_payload.get("spreadsheetUrl")
    assert spreadsheet_id, f"Missing spreadsheetId in payload: {sheet_payload}"
    assert spreadsheet_url, f"Missing spreadsheetUrl in payload: {sheet_payload}"

    send_cmd = planner.build_command(
        "gmail",
        "send_message",
        {
            "to_email": recipient,
            "subject": "CI Live Integration Validation",
            "body": f"Created spreadsheet: {spreadsheet_url}",
        },
    )
    send_result = runner.run(send_cmd, timeout_seconds=90)
    assert send_result.success, f"Failed to send email: {send_result.stderr or send_result.error}"
    send_payload = json.loads(send_result.stdout or "{}")
    assert send_payload.get("id"), f"Missing sent message id in payload: {send_payload}"
