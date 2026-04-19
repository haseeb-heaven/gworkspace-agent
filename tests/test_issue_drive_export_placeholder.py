from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pytest

from gws_assistant.execution import PlanExecutor
from gws_assistant.gws_runner import GWSRunner
from gws_assistant.models import ExecutionResult, PlannedTask, RequestPlan
from gws_assistant.planner import CommandPlanner


class FakeRunner(GWSRunner):
    def __init__(self) -> None:
        super().__init__(Path(os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws")), logging.getLogger("test"))
        self.commands: list[list[str]] = []

    def run(self, args: list[str], timeout_seconds: int = 90) -> ExecutionResult:
        self.commands.append(args)
        if args[:3] == ["drive", "files", "export"]:
            # Mock a successful export with text content
            return ExecutionResult(
                success=True,
                command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws"), *args],
                stdout=json.dumps({"saved_file": "scratch/exports/download_f1", "mimeType": "text/plain"}),
            )
        if args[:3] == ["drive", "files", "get"]:
            return ExecutionResult(
                success=True,
                command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws"), *args],
                stdout=json.dumps({"saved_file": "scratch/exports/download_f1", "mimeType": "text/plain"}),
            )
        if args[:4] == ["gmail", "users", "messages", "send"]:
            return ExecutionResult(
                success=True,
                command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws"), *args],
                stdout='{"id":"sent-1"}',
            )
        return ExecutionResult(success=True, command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws"), *args], stdout='{}')

@pytest.fixture
def mock_export_file(tmp_path, mocker):
    # Mock the file reading logic in execution.py
    # We need to make sure the "exported" file exists and has content
    export_path = tmp_path / "download_d1"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text("Exported Content", encoding="utf-8")

    # Mock open() to return our fake content when reading the exported file
    original_open = open
    def special_open(file, mode="r", *args, **kwargs):
        if "download_f1" in str(file):
            return original_open(export_path, mode, *args, **kwargs)
        return original_open(file, mode, *args, **kwargs)

    mocker.patch("builtins.open", side_effect=special_open)
    return export_path

def test_drive_export_placeholder_resolution(mock_export_file, mocker):
    runner = FakeRunner()
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))

    # 1. Drive export task
    # 2. Gmail task using $drive_export_file
    plan = RequestPlan(
        raw_text="export and email",
        tasks=[
            PlannedTask(id="task-1", service="drive", action="export_file", parameters={"file_id": "f1", "mime_type": "text/plain"}),
            PlannedTask(
                id="task-2",
                service="gmail",
                action="send_message",
                parameters={"to_email": os.getenv("DEFAULT_RECIPIENT_EMAIL") or "test@example.com", "subject": "Export", "body": "Content: $drive_export_file"}
            ),
        ],
    )

    # Set sequence index manually since we are using execute which will set it anyway
    # but maybe something went wrong
    report = executor.execute(plan)

    # Debug: see if the context had what we wanted
    # We can't easily see context from here unless we mock more

    assert report.success is True

    # Check if the Gmail body was resolved
    gmail_cmd = runner.commands[1]
    raw_json = json.loads(gmail_cmd[gmail_cmd.index("--json") + 1])
    import base64
    decoded = base64.urlsafe_b64decode(raw_json["raw"]).decode("utf-8")

    # This is expected to FAIL before the fix because $drive_export_file is not in legacy_map
    assert "Content: Exported Content" in decoded

def test_drive_export_folders_raises_validation_error():
    runner = FakeRunner()
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))

    # A folder MIME type
    params = {"file_id": "f1", "source_mime": "application/vnd.google-apps.folder"}

    # Building the command for a folder should now raise a ValidationError
    from gws_assistant.exceptions import ValidationError
    with pytest.raises(ValidationError) as excinfo:
        executor.planner.build_command("drive", "export_file", params)

    assert "is a folder" in str(excinfo.value)
    assert "cannot be read" in str(excinfo.value)
