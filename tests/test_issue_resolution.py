import logging
import os
from pathlib import Path

import pytest

from gws_assistant.execution import PlanExecutor
from gws_assistant.gws_runner import GWSRunner
from gws_assistant.models import ExecutionResult, PlannedTask, RequestPlan
from gws_assistant.planner import CommandPlanner


class MockRunner(GWSRunner):
    def __init__(self):
        super().__init__(
            Path(os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws")), logging.getLogger("test")
        )
        self.commands = []
        self.responses = {}

    def run(self, args, timeout_seconds=90):
        self.commands.append(args)
        cmd_key = tuple(args[:3])
        if cmd_key in self.responses:
            return self.responses[cmd_key]
        return ExecutionResult(success=True, command=args, stdout="{}")


@pytest.fixture
def executor():
    runner = MockRunner()
    return PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test")), runner


def test_resolve_document_not_folder(executor):
    """Bug 1: drive.export_file should resolve to a document, not a folder."""
    exec_instance, runner = executor

    # Mock drive.list_files to return a folder and a document
    runner.responses[("drive", "files", "list")] = ExecutionResult(
        success=True,
        command=["drive", "files", "list"],
        stdout='{"files": ['
        '{"id": "folder_id", "name": "My Folder", "mimeType": "application/vnd.google-apps.folder"},'
        '{"id": "doc_id", "name": "My Doc", "mimeType": "application/vnd.google-apps.document"}'
        "]}",
    )

    plan = RequestPlan(
        raw_text="export doc",
        tasks=[
            PlannedTask(id="task-1", service="drive", action="list_files", parameters={"q": "name = 'My Doc'"}),
            PlannedTask(
                id="task-2",
                service="drive",
                action="export_file",
                parameters={
                    "file_id": "{{task-1.id}}",
                    "source_mime": "application/vnd.google-apps.document",
                    "mime_type": "text/plain",
                },
            ),
        ],
    )

    report = exec_instance.execute(plan)
    assert report.success is True

    # Check task-2 parameters after resolution
    export_task = report.executions[1].task
    # EXPECTATION: It should pick 'doc_id', not 'folder_id'
    assert export_task.parameters["file_id"] == "doc_id"


def test_resolve_folder_then_file(executor):
    """Ensure source_mime resolves to the document's MIME type when a folder is listed first."""
    exec_instance, runner = executor

    # Mock drive.list_files to return a folder FIRST, then a document
    runner.responses[("drive", "files", "list")] = ExecutionResult(
        success=True,
        command=["drive", "files", "list"],
        stdout='{"files": ['
        '{"id": "folder_id", "name": "My Folder", "mimeType": "application/vnd.google-apps.folder"},'
        '{"id": "doc_id", "name": "My Doc", "mimeType": "application/vnd.google-apps.document"}'
        "]}",
    )

    plan = RequestPlan(
        raw_text="export doc",
        tasks=[
            PlannedTask(id="task-1", service="drive", action="list_files", parameters={"q": "name = 'My Doc'"}),
            PlannedTask(
                id="task-2",
                service="drive",
                action="export_file",
                parameters={
                    "file_id": "{{task-1.id}}",
                    "source_mime": "{{last_file_mime}}",
                    "mime_type": "text/plain",
                },
            ),
        ],
    )

    report = exec_instance.execute(plan)
    assert report.success is True

    # Check task-2 parameters after resolution
    export_task = report.executions[1].task
    assert export_task.parameters["source_mime"] == "application/vnd.google-apps.document"


def test_expand_task_graceful_failure(executor):
    """Bug 2: _expand_task should handle missing parameters gracefully."""
    exec_instance, runner = executor

    # Task that usually expands but missing parameter
    task = PlannedTask(id="task-1", service="gmail", action="get_message", parameters={})

    # Should not crash, should return [task] or handle it
    expanded = exec_instance._expand_task(task, {})
    assert len(expanded) == 1
    assert expanded[0] == task


def test_resolve_placeholders_smart_pick(executor):
    """Bug 3: _resolve_placeholders should pick the correct item from a list when a single value is expected."""
    exec_instance, _ = executor

    context = {
        "task_results": {
            "task-1": {
                "files": [
                    {"id": "f1", "name": "file1", "mimeType": "text/plain"},
                    {"id": "f2", "name": "file2", "mimeType": "image/png"},
                ]
            }
        }
    }

    # If we want an ID for a text operation, and we have multiple files
    # maybe we should be smarter if the context allows.
    # NEW BEHAVIOR: It should pick the first item's ID if we ask for .id on a list of files
    val = "{{task-1.id}}"
    resolved = exec_instance._resolve_placeholders(val, context)
    assert resolved == "f1"


if __name__ == "__main__":
    pytest.main([__file__])
