from __future__ import annotations

import logging
from pathlib import Path

from gws_assistant.execution import PlanExecutor
from gws_assistant.gws_runner import GWSRunner
from gws_assistant.models import ExecutionResult, PlannedTask, RequestPlan
from gws_assistant.planner import CommandPlanner


class FakeRunner(GWSRunner):
    def __init__(self) -> None:
        super().__init__(Path("gws.exe"), logging.getLogger("test"))
        self.commands: list[list[str]] = []

    def run(self, args: list[str], timeout_seconds: int = 90) -> ExecutionResult:
        self.commands.append(args)
        if args[:4] == ["gmail", "users", "messages", "list"]:
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout='{"messages":[{"id":"m1","threadId":"t1"}],"resultSizeEstimate":1}',
            )
        if args[:3] == ["sheets", "spreadsheets", "create"]:
            import json as _json
            json_idx = args.index("--json") if "--json" in args else -1
            title = "Sheet"
            if json_idx >= 0:
                try:
                    body = _json.loads(args[json_idx + 1])
                    title = body.get("properties", {}).get("title", "Sheet")
                except Exception:
                    pass
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout=_json.dumps({
                    "spreadsheetId": "sheet-1",
                    "spreadsheetUrl": "https://example.test/sheet",
                    "properties": {"title": title},
                    "sheets": [{"properties": {"title": title}}],
                }),
            )
        if args[:4] == ["sheets", "spreadsheets", "values", "get"]:
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout='{"range":"Sheet1!A1:B2","values":[["Name","Role"],["Alice","Engineer"]]}',
            )
        if args[:4] == ["gmail", "users", "messages", "get"]:
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout=(
                    '{"id":"m1","payload":{"headers":['
                    '{"name":"From","value":"DecoverAI <jobs@decoverai.example>"},'
                    '{"name":"Subject","value":"Job offer"}]}}'
                ),
            )
        if args[:4] == ["gmail", "users", "messages", "send"]:
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout='{"id":"sent-1","labelIds":["SENT"]}',
            )
        if args[:3] == ["drive", "files", "list"]:
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout='{"files":[{"id":"d1","name":"Agentic AI - Builders","mimeType":"application/vnd.google-apps.document","webViewLink":"https://docs.google.com/document/d/test123/edit"},{"id":"d2","name":"weapon_244.qvm","mimeType":"application/octet-stream","webViewLink":"https://drive.google.com/file/d/xxx"}]}',
            )
        if args[:3] == ["drive", "files", "create"]:
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout='{"id":"folder-1","name":"Test Folder","mimeType":"application/vnd.google-apps.folder","kind":"drive#file"}',
            )
        if args[:3] == ["calendar", "events", "insert"]:
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout='{"id":"evt-1","created":"2026-04-11","summary":"Test Event","htmlLink":"https://calendar.google.com/event?id=evt-1"}',
            )
        if args[:3] == ["calendar", "events", "list"]:
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout='{"items":[{"id":"evt-1","summary":"Review Data","start":{"date":"2026-04-15"},"end":{"date":"2026-04-15"}}]}',
            )
        return ExecutionResult(success=True, command=["gws.exe", *args], stdout='{"updates":{"updatedRows":2}}')


def test_executor_resolves_gmail_to_sheet_placeholders():
    runner = FakeRunner()
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
    plan = RequestPlan(
        raw_text="tickets",
        tasks=[
            PlannedTask(id="task-1", service="gmail", action="list_messages", parameters={"q": "ticket", "max_results": 10}),
            PlannedTask(id="task-2", service="sheets", action="create_spreadsheet", parameters={"title": "Tickets"}),
            PlannedTask(
                id="task-3",
                service="sheets",
                action="append_values",
                parameters={"spreadsheet_id": "$last_spreadsheet_id", "range": "Sheet1!A1", "values": "$gmail_summary_values"},
            ),
        ],
    )
    report = executor.execute(plan)
    assert report.success is True
    assert "sheet-1" in runner.commands[2][runner.commands[2].index("--params") + 1]
    assert "m1" in runner.commands[2][runner.commands[2].index("--json") + 1]


def test_executor_expands_gmail_message_placeholder_before_get_message():
    runner = FakeRunner()
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
    plan = RequestPlan(
        raw_text="jobs",
        tasks=[
            PlannedTask(id="task-1", service="gmail", action="list_messages", parameters={"q": "jobs", "max_results": 10}),
            PlannedTask(id="task-2", service="gmail", action="get_message", parameters={"message_id": "{{message_id_from_task_1}}"}),
            PlannedTask(id="task-3", service="sheets", action="create_spreadsheet", parameters={"title": "Jobs"}),
            PlannedTask(
                id="task-4",
                service="sheets",
                action="append_values",
                parameters={
                    "spreadsheet_id": "$last_spreadsheet_id",
                    "range": "Sheet1!A1",
                    "values": "{{company_names_from_task_2}}",
                },
            ),
        ],
    )
    report = executor.execute(plan)
    assert report.success is True
    assert runner.commands[1][:4] == ["gmail", "users", "messages", "get"]
    assert '"id": "m1"' in runner.commands[1][runner.commands[1].index("--params") + 1]
    assert "DecoverAI" in runner.commands[3][runner.commands[3].index("--json") + 1]


def test_executor_builds_email_body_from_sheet_values():
    runner = FakeRunner()
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
    plan = RequestPlan(
        raw_text="send sheet by email",
        tasks=[
            PlannedTask(
                id="task-1",
                service="sheets",
                action="get_values",
                parameters={"spreadsheet_id": "sheet-123", "range": "Sheet1!A1:B2"},
            ),
            PlannedTask(
                id="task-2",
                service="gmail",
                action="send_message",
                parameters={"to_email": "user@example.com", "subject": "Sheet data", "body": "$sheet_email_body"},
            ),
        ],
    )
    report = executor.execute(plan)
    assert report.success is True
    assert runner.commands[1][:4] == ["gmail", "users", "messages", "send"]
    raw_json = runner.commands[1][runner.commands[1].index("--json") + 1]
    assert "raw" in raw_json

def test_execute_single_task(tmp_path):
    runner = FakeRunner()
    runner.commands = []
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger())
    
    task = PlannedTask(id="1", service="gmail", action="list_messages", parameters={"q": "foo"}, reason="Test")
    result = executor.execute_single_task(task, {})
    assert result.success is True
    assert len(runner.commands) == 1
    assert runner.commands[-1][:4] == ["gmail", "users", "messages", "list"]
