from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()
import base64
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from gws_assistant.execution import PlanExecutor
from gws_assistant.gws_runner import GWSRunner
from gws_assistant.models import ExecutionResult, PlannedTask, RequestPlan
from gws_assistant.planner import CommandPlanner


class FakeRunner(GWSRunner):
    def __init__(self) -> None:
        super().__init__(
            Path(os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws")), logging.getLogger("test")
        )
        self.commands: list[list[str]] = []

    def run(self, args: list[str], timeout_seconds: int = 90) -> ExecutionResult:
        self.commands.append(args)
        if args[:4] == ["gmail", "users", "messages", "list"]:
            return ExecutionResult(
                success=True,
                command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws"), *args],
                stdout='{"messages":[{"id":"m1","threadId":"t1","payload":{"headers":[{"name":"Subject","value":"Job offer m1"}]}}, {"id":"m2","threadId":"t2","payload":{"headers":[{"name":"Subject","value":"Job offer m2"}]}}],"resultSizeEstimate":2}',
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
                command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws"), *args],
                stdout=_json.dumps(
                    {
                        "spreadsheetId": "sheet-1",
                        "spreadsheetUrl": "https://example.test/sheet",
                        "properties": {"title": title},
                        "sheets": [{"properties": {"title": title}}],
                    }
                ),
            )
        if args[:4] == ["sheets", "spreadsheets", "values", "get"]:
            return ExecutionResult(
                success=True,
                command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws"), *args],
                stdout='{"range":"Sheet1!A1:B2","values":[["Name","Role"],["Alice","Engineer"]]}',
            )
        if args[:3] == ["docs", "documents", "create"]:
            import json as _json

            json_idx = args.index("--json") if "--json" in args else -1
            title = "Document"
            if json_idx >= 0:
                try:
                    body = _json.loads(args[json_idx + 1])
                    title = body.get("title", "Document")
                except Exception:
                    pass
            return ExecutionResult(
                success=True,
                command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws"), *args],
                stdout=_json.dumps({"documentId": "doc-1", "title": title}),
            )
        if args[:3] == ["docs", "documents", "batchUpdate"]:
            return ExecutionResult(
                success=True,
                command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws"), *args],
                stdout='{"documentId":"doc-1","replies":[]}',
            )
        if args[:4] == ["gmail", "users", "messages", "get"]:
            import json as _json

            msg_id = "m1"
            # Extract ID from params if possible
            for i, arg in enumerate(args):
                if arg == "--params":
                    try:
                        p_data = _json.loads(args[i + 1])
                        msg_id = p_data.get("id") or p_data.get("messageId") or msg_id
                    except (IndexError, _json.JSONDecodeError, ValueError):
                        pass

            subject = f"Job offer {msg_id}"
            return ExecutionResult(
                success=True,
                command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws"), *args],
                stdout=(
                    f'{{"id":"{msg_id}", "snippet": "Job from DecoverAI", "payload":{{"headers":['
                    f'{{"name":"From","value":"DecoverAI <jobs@decoverai.example>"}},'
                    f'{{"name":"Subject","value":"{subject}"}}]}}}}'
                ),
            )
        if args[:4] == ["gmail", "users", "messages", "send"]:
            return ExecutionResult(
                success=True,
                command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws"), *args],
                stdout='{"id":"sent-1","labelIds":["SENT"]}',
            )
        if args[:3] == ["drive", "files", "list"]:
            return ExecutionResult(
                success=True,
                command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws"), *args],
                stdout='{"files":[{"id":"d1","name":"Agentic AI - Builders","mimeType":"application/vnd.google-apps.document","webViewLink":"https://docs.google.com/document/d/test123/edit"},{"id":"d2","name":"weapon_244.qvm","mimeType":"application/octet-stream","webViewLink":"https://drive.google.com/file/d/xxx"}]}',
            )
        if args[:3] == ["drive", "files", "create"]:
            return ExecutionResult(
                success=True,
                command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws"), *args],
                stdout='{"id":"folder-1","name":"Test Folder","mimeType":"application/vnd.google-apps.folder","kind":"drive#file"}',
            )
        if args[:3] == ["calendar", "events", "insert"]:
            return ExecutionResult(
                success=True,
                command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws"), *args],
                stdout='{"id":"evt-1","created":"2026-04-11","summary":"Test Event","htmlLink":"https://calendar.google.com/event?id=evt-1"}',
            )
        if args[:3] == ["calendar", "events", "list"]:
            return ExecutionResult(
                success=True,
                command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws"), *args],
                stdout='{"items":[{"id":"evt-1","summary":"Review Data","start":{"date":"2026-04-15"},"end":{"date":"2026-04-15"}}]}',
            )
        return ExecutionResult(
            success=True,
            command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws"), *args],
            stdout='{"updates":{"updatedRows":2}}',
        )


@pytest.fixture(autouse=True)
def mock_react(mocker):
    """Mock ReACT thought/replan methods to keep tests fast and local."""
    mocker.patch("gws_assistant.execution.PlanExecutor._think", return_value="Thought: Proceeding with planned task.")
    mocker.patch("gws_assistant.execution.PlanExecutor._should_replan", return_value=False)
    mocker.patch("gws_assistant.execution.PlanExecutor._verify_artifact_content", return_value=None)
    mocker.patch("gws_assistant.execution.PlanExecutor.verify_resource", return_value=True)


def test_executor_resolves_gmail_to_sheet_placeholders():
    runner = FakeRunner()
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
    plan = RequestPlan(
        raw_text="tickets",
        tasks=[
            PlannedTask(
                id="task-1", service="gmail", action="list_messages", parameters={"q": "ticket", "max_results": 10}
            ),
            PlannedTask(id="task-2", service="sheets", action="create_spreadsheet", parameters={"title": "Tickets"}),
            PlannedTask(
                id="task-3",
                service="sheets",
                action="append_values",
                parameters={
                    "spreadsheet_id": "$last_spreadsheet_id",
                    "range": "Sheet1!A1",
                    "values": "$gmail_summary_rows",
                },
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
            PlannedTask(
                id="task-1", service="gmail", action="list_messages", parameters={"q": "jobs", "max_results": 10}
            ),
            PlannedTask(
                id="task-2",
                service="gmail",
                action="get_message",
                parameters={"message_id": "{{message_id_from_task_1}}"},
            ),
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

    # commands: 0:list, 1:get(m1), 2:get(m2), 3:create_sheet, 4:append_values
    # Check if get_message was called correctly
    get_cmds = [c for c in runner.commands if c[:4] == ["gmail", "users", "messages", "get"]]
    assert len(get_cmds) == 2
    assert '"id": "m1"' in get_cmds[0][get_cmds[0].index("--params") + 1]
    assert '"id": "m2"' in get_cmds[1][get_cmds[1].index("--params") + 1]

    # Check if append_values was called with resolved data
    append_cmds = [c for c in runner.commands if c[:3] == ["sheets", "spreadsheets", "values"]]
    assert len(append_cmds) == 1
    # Resolved company names from both messages should be present
    assert "DecoverAI" in append_cmds[0][append_cmds[0].index("--json") + 1]


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
                parameters={
                    "to_email": os.getenv("DEFAULT_RECIPIENT_EMAIL") or "test@example.com",
                    "subject": "Sheet data",
                    "body": "$sheet_email_body",
                },
            ),
        ],
    )
    report = executor.execute(plan)
    assert report.success is True
    assert runner.commands[1][:4] == ["gmail", "users", "messages", "send"]
    raw_json = runner.commands[1][runner.commands[1].index("--json") + 1]
    assert "raw" in raw_json


def test_executor_resolves_nested_gmail_message_placeholder_for_sheets():
    runner = FakeRunner()
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
    plan = RequestPlan(
        raw_text="save gmail body to sheet",
        tasks=[
            PlannedTask(
                id="task-1", service="gmail", action="list_messages", parameters={"q": "ticket", "max_results": 10}
            ),
            PlannedTask(id="task-2", service="sheets", action="create_spreadsheet", parameters={"title": "Tickets"}),
            PlannedTask(
                id="task-3",
                service="sheets",
                action="append_values",
                parameters={
                    "spreadsheet_id": "$last_spreadsheet_id",
                    "range": "Sheet1!A1",
                    "values": [["$gmail_message_body"]],
                },
            ),
        ],
    )
    report = executor.execute(plan)
    assert report.success is True
    assert "m1" in runner.commands[2][runner.commands[2].index("--json") + 1]


def test_execute_single_task(tmp_path):
    runner = FakeRunner()
    runner.commands = []
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger())

    task = PlannedTask(id="1", service="gmail", action="list_messages", parameters={"q": "foo"}, reason="Test")
    result = executor.execute_single_task(task, {})
    assert result.success is True
    assert len(runner.commands) == 1
    assert runner.commands[-1][:4] == ["gmail", "users", "messages", "list"]


def test_executor_runs_research_to_docs_sheets_and_email_pipeline(mocker):
    runner = FakeRunner()
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
    mocker.patch(
        "gws_assistant.tools.web_search.web_search_tool",
        SimpleNamespace(
            invoke=lambda payload: {
                "query": "top 3 agentic ai frameworks",
                "results": [
                    {
                        "title": "LangGraph",
                        "content": "Graph-based agent orchestration",
                        "link": "https://example.com/langgraph",
                    },
                    {
                        "title": "CrewAI",
                        "content": "Multi-agent workflow framework",
                        "link": "https://example.com/crewai",
                    },
                    {
                        "title": "AutoGen",
                        "content": "Conversational multi-agent framework",
                        "link": "https://example.com/autogen",
                    },
                ],
                "error": None,
            }
        ),
    )

    plan = RequestPlan(
        raw_text="Find top 3 Agentic AI frameworks, save the data to Google Docs and Google Sheets, and send an email to user@example.com",
        tasks=[
            PlannedTask(
                id="task-1", service="search", action="web_search", parameters={"query": "top 3 agentic ai frameworks"}
            ),
            PlannedTask(
                id="task-2", service="docs", action="create_document", parameters={"title": "Agentic Ai Frameworks"}
            ),
            PlannedTask(
                id="task-3",
                service="docs",
                action="batch_update",
                parameters={"document_id": "$last_document_id", "text": "$web_search_markdown"},
            ),
            PlannedTask(
                id="task-4",
                service="sheets",
                action="create_spreadsheet",
                parameters={"title": "Agentic Ai Frameworks"},
            ),
            PlannedTask(
                id="task-5",
                service="sheets",
                action="append_values",
                parameters={
                    "spreadsheet_id": "$last_spreadsheet_id",
                    "range": "Sheet1!A1",
                    "values": "$web_search_table_values",
                },
            ),
            PlannedTask(
                id="task-6",
                service="gmail",
                action="send_message",
                parameters={
                    "to_email": os.getenv("DEFAULT_RECIPIENT_EMAIL") or "test@example.com",
                    "subject": "Agentic Ai Frameworks summary",
                    "body": "The requested research has been saved to the generated Google Doc and Google Sheet. Please share the links.",
                },
            ),
        ],
    )

    report = executor.execute(plan)
    assert report.success is True

    docs_update_cmd = runner.commands[1]
    idx = docs_update_cmd.index("--json")
    docs_payload = json.loads(docs_update_cmd[idx + 1])
    inserted_text = docs_payload["requests"][0]["insertText"]["text"]
    assert "LangGraph" in inserted_text
    assert "CrewAI" in inserted_text

    append_cmd = runner.commands[3]
    sheet_payload = json.loads(append_cmd[append_cmd.index("--json") + 1])
    assert sheet_payload["values"][0][0] == "LangGraph"
    assert sheet_payload["values"][1][0] == "CrewAI"

    send_cmd = runner.commands[4]
    raw_json = json.loads(send_cmd[send_cmd.index("--json") + 1])
    decoded = base64.urlsafe_b64decode(raw_json["raw"]).decode("utf-8")
    assert "https://docs.google.com/document/d/doc-1/edit" in decoded
    assert "https://example.test/sheet" in decoded


def test_gmail_details_accumulation():
    runner = FakeRunner()
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
    plan = RequestPlan(
        raw_text="extract jobs",
        tasks=[
            PlannedTask(
                id="task-1", service="gmail", action="list_messages", parameters={"q": "jobs", "max_results": 2}
            ),
            # task-1 will expand into task-1-1 and task-1-2 in some future logic,
            # but currently expand_task handles specific actions.
            # Let's simulate expansion by providing get_message with a list.
            PlannedTask(
                id="task-2",
                service="gmail",
                action="get_message",
                parameters={"message_id": "{{message_id_from_task_1}}"},
            ),
            PlannedTask(
                id="task-3",
                service="sheets",
                action="append_values",
                parameters={
                    "spreadsheet_id": "s1",
                    "range": "Sheet1!A1",
                    "values": "$gmail_summary_rows",
                },
            ),
        ],
    )
    report = executor.execute(plan)
    assert report.success is True

    # Task 1: list_messages
    # Task 2 expanded into 2-1 and 2-2
    # Task 3: append_values

    # Check that gmail_summary_rows in task-3 contains TWO rows
    append_task = report.executions[-1].task
    values = append_task.parameters["values"]
    assert isinstance(values, list)
    # We expect 2 rows from the 2 get_message tasks
    assert len(values) == 2
    assert values[0][1] == "Job offer m1"
    assert values[1][1] == "Job offer m2"


def test_code_output_resolution():
    runner = FakeRunner()
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))

    # Fake runner for code execute doesn't natively exist, we can stub it or test logic via direct handle.
    plan = RequestPlan(
        raw_text="run code and send",
        tasks=[
            PlannedTask(id="task-1", service="code", action="execute", parameters={"code": "print('hello world')"}),
            PlannedTask(
                id="task-2",
                service="gmail",
                action="send_message",
                parameters={"to_email": "test@example.com", "subject": "Code", "body": "Result: $code_output"},
            ),
        ],
    )

    # We need to mock _handle_code_execution_task to simulate the updated code outputs
    # since FakeRunner might not intercept code.execute natively (it goes through _handle_code_execution_task)
    original_handle = getattr(executor, "_handle_code_execution_task", None)

    def fake_code_execute(task, context):
        from gws_assistant.models import ExecutionResult

        # Mimic context updater directly since the real handler calls runner
        result_data = {"stdout": "hello world\n", "parsed_value": "hello world"}
        context["code_output"] = result_data["parsed_value"]
        # Add tasks results structure for compatibility if needed
        context.setdefault("task_results", {})["task-1"] = result_data

        return ExecutionResult(success=True, command=["code", "execute"], output=result_data, stdout="hello world\n")

    executor._handle_code_execution_task = fake_code_execute

    try:
        report = executor.execute(plan)
        assert report.success is True
    finally:
        if original_handle:
            executor._handle_code_execution_task = original_handle

    # The second task is send_message, verify it resolved $code_output
    send_cmds = [c for c in runner.commands if c[:4] == ["gmail", "users", "messages", "send"]]
    assert len(send_cmds) == 1

    # Check payload
    payload_str = send_cmds[0][send_cmds[0].index("--json") + 1]
    payload = json.loads(payload_str)
    decoded_body = base64.urlsafe_b64decode(payload["raw"]).decode("ascii")
    assert "Result: hello world" in decoded_body


def test_legacy_placeholder_resolution():
    import logging

    from gws_assistant.execution.executor import PlanExecutor
    from gws_assistant.planner import CommandPlanner

    runner = FakeRunner()
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))

    context = {
        "drive_metadata_rows": [["file1.txt", "text/plain", "link1"]],
        "code_output": "test_output_123",
        "sheet_summary_table": "| Col1 | Col2 |\n|---|---|\n| A | B |",
    }

    # Should resolve correctly mapping from legacy to new
    resolved_drive = executor._resolve_placeholders("$drive_summary_values", context)
    assert resolved_drive == [["file1.txt", "text/plain", "link1"]]

    resolved_code = executor._resolve_placeholders("$last_code_stdout", context)
    assert resolved_code == "test_output_123"

    resolved_code_result = executor._resolve_placeholders("$last_code_result", context)
    assert resolved_code_result == "test_output_123"

    resolved_sheet = executor._resolve_placeholders("$sheet_email_body", context)
    assert resolved_sheet == "| Col1 | Col2 |\n|---|---|\n| A | B |"
