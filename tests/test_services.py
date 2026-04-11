"""Comprehensive service CRUD and multi-service workflow tests.

Tests cover real-world user scenarios across all supported services:
- Gmail: search, read, send
- Drive: list with filters, create folder
- Sheets: create, append, read
- Calendar: create event, list events
- Multi-service pipelines: Gmail→Sheets, Drive→Sheets→Email, etc.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from gws_assistant.agent_system import NO_SERVICE_MESSAGE, WorkspaceAgentSystem, _drive_query_from_text
from gws_assistant.exceptions import ValidationError
from gws_assistant.execution import PlanExecutor
from gws_assistant.gws_runner import GWSRunner
from gws_assistant.models import AppConfigModel, ExecutionResult, PlannedTask, RequestPlan
from gws_assistant.output_formatter import HumanReadableFormatter
from gws_assistant.planner import CommandPlanner
from gws_assistant.relevance import extract_keywords, filter_drive_files, score_item


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _config(tmp_path: Path) -> AppConfigModel:
    return AppConfigModel(
        provider="openai",
        model="gpt-4.1-mini",
        api_key=None,
        base_url=None,
        timeout_seconds=30,
        gws_binary_path=tmp_path / "gws.exe",
        log_file_path=tmp_path / "assistant.log",
        log_level="INFO",
        verbose=True,
        env_file_path=tmp_path / ".env",
        setup_complete=True,
        max_retries=3,
        langchain_enabled=True,
    )


class FakeRunner(GWSRunner):
    """Mock runner that returns realistic API payloads for all services."""

    def __init__(self) -> None:
        super().__init__(Path("gws.exe"), logging.getLogger("test"))
        self.commands: list[list[str]] = []

    def run(self, args: list[str], timeout_seconds: int = 90) -> ExecutionResult:
        self.commands.append(args)
        if args[:4] == ["gmail", "users", "messages", "list"]:
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout='{"messages":[{"id":"m1","threadId":"t1"},{"id":"m2","threadId":"t2"}],"resultSizeEstimate":2}',
            )
        if args[:4] == ["gmail", "users", "messages", "get"]:
            msg_id = json.loads(args[args.index("--params") + 1]).get("id", "m1")
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout=json.dumps({
                    "id": msg_id,
                    "snippet": "We are hiring for a senior role",
                    "payload": {"headers": [
                        {"name": "From", "value": f"HR <hr@company-{msg_id}.com>"},
                        {"name": "Subject", "value": f"Job Offer from Company {msg_id}"},
                        {"name": "Date", "value": "Fri, 11 Apr 2026 10:00:00 +0000"},
                    ]},
                }),
            )
        if args[:4] == ["gmail", "users", "messages", "send"]:
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout='{"id":"sent-1","labelIds":["SENT"]}',
            )
        if args[:3] == ["sheets", "spreadsheets", "create"]:
            json_idx = args.index("--json") if "--json" in args else -1
            title = "Sheet"
            if json_idx >= 0:
                try:
                    body = json.loads(args[json_idx + 1])
                    title = body.get("properties", {}).get("title", "Sheet")
                except Exception:
                    pass
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout=json.dumps({
                    "spreadsheetId": "sheet-1",
                    "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/sheet-1/edit",
                    "properties": {"title": title},
                    "sheets": [{"properties": {"title": title}}],
                }),
            )
        if args[:4] == ["sheets", "spreadsheets", "values", "append"]:
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout='{"updates":{"updatedRows":2,"updatedCells":6,"updatedRange":"TestTab!A1:C2"}}',
            )
        if args[:4] == ["sheets", "spreadsheets", "values", "get"]:
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout='{"range":"Sheet1!A1:B2","values":[["Name","Role"],["Alice","Engineer"]]}',
            )
        if args[:3] == ["drive", "files", "list"]:
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout=json.dumps({"files": [
                    {"id": "d1", "name": "Agentic AI - Builders", "mimeType": "application/vnd.google-apps.document", "webViewLink": "https://docs.google.com/document/d/test123/edit"},
                    {"id": "d2", "name": "weapon_244.qvm", "mimeType": "application/octet-stream", "webViewLink": "https://drive.google.com/file/d/xxx"},
                ]}),
            )
        if args[:3] == ["drive", "files", "create"]:
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout='{"id":"folder-1","name":"Test Folder","mimeType":"application/vnd.google-apps.folder"}',
            )
        if args[:3] == ["calendar", "events", "insert"]:
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout='{"id":"evt-1","created":"2026-04-11","summary":"Test","htmlLink":"https://calendar.google.com/event?id=evt-1"}',
            )
        if args[:3] == ["calendar", "events", "list"]:
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout='{"items":[{"id":"evt-1","summary":"Review","start":{"date":"2026-04-15"},"end":{"date":"2026-04-15"}}]}',
            )
        return ExecutionResult(success=True, command=["gws.exe", *args], stdout='{}')


# =====================================================================
# 1. PLANNER CRUD TESTS — Validate command building for every service
# =====================================================================

class TestPlannerGmail:
    planner = CommandPlanner()

    def test_list_messages_with_query(self):
        args = self.planner.build_command("gmail", "list_messages", {"q": "from:boss@company.com", "max_results": 5})
        assert args[:4] == ["gmail", "users", "messages", "list"]
        params = json.loads(args[args.index("--params") + 1])
        assert params["q"] == "from:boss@company.com"
        assert params["maxResults"] == 5

    def test_get_message(self):
        args = self.planner.build_command("gmail", "get_message", {"message_id": "abc123"})
        assert args[:4] == ["gmail", "users", "messages", "get"]
        params = json.loads(args[args.index("--params") + 1])
        assert params["id"] == "abc123"

    def test_send_message_builds_raw_email(self):
        args = self.planner.build_command("gmail", "send_message", {
            "to_email": "user@example.com",
            "subject": "Test Subject",
            "body": "Hello World",
        })
        assert args[:4] == ["gmail", "users", "messages", "send"]
        body = json.loads(args[args.index("--json") + 1])
        assert "raw" in body
        # The raw field should be base64-encoded
        import base64
        decoded = base64.urlsafe_b64decode(body["raw"]).decode("utf-8")
        assert "To: user@example.com" in decoded
        assert "Subject: Test Subject" in decoded
        assert "Hello World" in decoded

    def test_send_rejects_missing_to_email(self):
        with pytest.raises(ValidationError):
            self.planner.build_command("gmail", "send_message", {"subject": "X", "body": "Y"})


class TestPlannerDrive:
    planner = CommandPlanner()

    def test_list_files_with_query(self):
        args = self.planner.build_command("drive", "list_files", {"q": "name contains 'Budget'", "page_size": 20})
        params = json.loads(args[args.index("--params") + 1])
        assert params["q"] == "name contains 'Budget'"
        assert params["pageSize"] == 20

    def test_list_files_without_query_has_no_q(self):
        args = self.planner.build_command("drive", "list_files", {})
        params = json.loads(args[args.index("--params") + 1])
        assert "q" not in params

    def test_create_folder(self):
        args = self.planner.build_command("drive", "create_folder", {"folder_name": "My Folder"})
        assert args[:3] == ["drive", "files", "create"]
        body = json.loads(args[args.index("--json") + 1])
        assert body["name"] == "My Folder"
        assert body["mimeType"] == "application/vnd.google-apps.folder"

    def test_create_folder_rejects_empty_name(self):
        with pytest.raises(ValidationError):
            self.planner.build_command("drive", "create_folder", {"folder_name": ""})


class TestPlannerSheets:
    planner = CommandPlanner()

    def test_create_spreadsheet_includes_tab(self):
        args = self.planner.build_command("sheets", "create_spreadsheet", {"title": "Job Offers"})
        body = json.loads(args[args.index("--json") + 1])
        assert body["properties"]["title"] == "Job Offers"
        assert body["sheets"][0]["properties"]["title"] == "Job Offers"

    def test_append_values_quotes_spaces_in_range(self):
        args = self.planner.build_command("sheets", "append_values", {
            "spreadsheet_id": "s1",
            "range": "Job Offers!A1",
            "values": [["a", "b"]],
        })
        params = json.loads(args[args.index("--params") + 1])
        assert params["range"] == "'Job Offers'!A1"

    def test_get_values(self):
        args = self.planner.build_command("sheets", "get_values", {
            "spreadsheet_id": "s1",
            "range": "Sheet1!A1:Z500",
        })
        params = json.loads(args[args.index("--params") + 1])
        assert params["spreadsheetId"] == "s1"
        assert params["range"] == "Sheet1!A1:Z500"


class TestPlannerCalendar:
    planner = CommandPlanner()

    def test_create_event_includes_end_date(self):
        args = self.planner.build_command("calendar", "create_event", {
            "summary": "Team Sync",
            "start_date": "2026-04-15",
        })
        body = json.loads(args[args.index("--json") + 1])
        assert body["start"]["date"] == "2026-04-15"
        assert body["end"]["date"] == "2026-04-15"

    def test_create_event_strips_time_portion(self):
        """Calendar API rejects timestamps in date-only fields."""
        args = self.planner.build_command("calendar", "create_event", {
            "summary": "Meeting",
            "start_date": "2026-04-15T10:00:00",
        })
        body = json.loads(args[args.index("--json") + 1])
        assert body["start"]["date"] == "2026-04-15"
        assert "T" not in body["start"]["date"]

    def test_list_events(self):
        args = self.planner.build_command("calendar", "list_events", {})
        params = json.loads(args[args.index("--params") + 1])
        assert params["calendarId"] == "primary"


# =====================================================================
# 2. AGENT PLANNING TESTS — Real user prompts → correct task plans
# =====================================================================

class TestAgentPlanning:

    def test_search_emails_save_to_sheets(self, tmp_path):
        """User: 'Search my email about Jobs offers from last week and save all company names into Google sheets.'"""
        agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
        plan = agent.plan("Search my email about Jobs offers from last week and save all those company names into Google sheets")
        services = [(t.service, t.action) for t in plan.tasks]
        assert ("gmail", "list_messages") in services
        assert ("sheets", "create_spreadsheet") in services
        assert ("sheets", "append_values") in services
        assert plan.no_service_detected is False

    def test_sheets_to_email_with_id(self, tmp_path):
        """User: 'Search Google Sheets with ID: ... create email with this data to ... and send it.'"""
        agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
        plan = agent.plan(
            "Search Google Sheets with ID: '1bZbV_Wf9EqMKD4QSVaON3UT2l_orD7BEsvHCXGe4lBo' "
            "create email with this data to 'haseebmahr.hm@gmail.com' and send it"
        )
        services = [(t.service, t.action) for t in plan.tasks]
        assert ("sheets", "get_values") in services
        assert ("gmail", "send_message") in services
        assert plan.tasks[-1].parameters.get("to_email") == "haseebmahr.hm@gmail.com"

    def test_list_emails_from_specific_person(self, tmp_path):
        """User: 'List all emails i received from amrita.priyadarshini@rockstarindia.com person'"""
        agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
        plan = agent.plan("List all emails i received from 'amrita.priyadarshini@rockstarindia.com' person")
        services = [(t.service, t.action) for t in plan.tasks]
        assert ("gmail", "list_messages") in services
        assert ("gmail", "get_message") in services

    def test_no_service_detected(self, tmp_path):
        """Unrelated prompts should return no_service_detected."""
        agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
        plan = agent.plan("What is the meaning of life?")
        assert plan.no_service_detected is True
        assert plan.summary == NO_SERVICE_MESSAGE

    def test_drive_search_extracts_query(self, tmp_path):
        """Drive search should extract quoted terms into a q filter."""
        query = _drive_query_from_text('search google documents for "agentic ai - builders" and convert data')
        assert "fullText contains" in query
        assert "agentic ai - builders" in query.lower()


# =====================================================================
# 3. EXECUTION PIPELINE TESTS — End-to-end with FakeRunner
# =====================================================================

class TestExecutionPipelines:

    def test_gmail_to_sheets_pipeline(self):
        """Gmail search → create spreadsheet → append data. Verifies range auto-fix."""
        runner = FakeRunner()
        executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
        plan = RequestPlan(
            raw_text="Find emails about job offers and save to sheets",
            tasks=[
                PlannedTask("task-1", "gmail", "list_messages", {"q": "job offer", "max_results": 10}),
                PlannedTask("task-2", "sheets", "create_spreadsheet", {"title": "Job Offers"}),
                PlannedTask("task-3", "sheets", "append_values", {
                    "spreadsheet_id": "$last_spreadsheet_id",
                    "range": "Sheet1!A1",
                    "values": "$gmail_summary_values",
                }),
            ],
        )
        report = executor.execute(plan)
        assert report.success is True
        # Verify range was auto-fixed from Sheet1!A1 to 'Job Offers'!A1
        append_cmd = runner.commands[2]
        params_str = append_cmd[append_cmd.index("--params") + 1]
        assert "'Job Offers'!A1" in params_str

    def test_drive_to_sheets_pipeline(self):
        """Drive search → create sheet → append drive data."""
        runner = FakeRunner()
        executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
        plan = RequestPlan(
            raw_text='Search Google Documents for "Agentic AI - Builders" and create a Sheet',
            tasks=[
                PlannedTask("task-1", "drive", "list_files", {"q": "fullText contains 'Agentic AI'", "page_size": 100}),
                PlannedTask("task-2", "sheets", "create_spreadsheet", {"title": "AI Builders Data"}),
                PlannedTask("task-3", "sheets", "append_values", {
                    "spreadsheet_id": "$last_spreadsheet_id",
                    "range": "Sheet1!A1",
                    "values": "$drive_summary_values",
                }),
            ],
        )
        report = executor.execute(plan)
        assert report.success is True
        # The drive data should contain the Agentic AI file (relevance-filtered)
        append_cmd = runner.commands[2]
        json_str = append_cmd[append_cmd.index("--json") + 1]
        assert "Agentic AI - Builders" in json_str

    def test_sheets_to_email_pipeline(self):
        """Read spreadsheet → send email with body."""
        runner = FakeRunner()
        executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
        plan = RequestPlan(
            raw_text="Send sheet data via email",
            tasks=[
                PlannedTask("task-1", "sheets", "get_values", {"spreadsheet_id": "s1", "range": "Sheet1!A1:B2"}),
                PlannedTask("task-2", "gmail", "send_message", {
                    "to_email": "user@example.com",
                    "subject": "Data Export",
                    "body": "$sheet_email_body",
                }),
            ],
        )
        report = executor.execute(plan)
        assert report.success is True
        send_cmd = runner.commands[1]
        assert send_cmd[:4] == ["gmail", "users", "messages", "send"]
        raw_json = send_cmd[send_cmd.index("--json") + 1]
        assert "raw" in raw_json

    def test_full_pipeline_drive_sheets_email_calendar(self):
        """Drive → Sheets → Email → Calendar — full 4-service workflow."""
        runner = FakeRunner()
        executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
        plan = RequestPlan(
            raw_text='Search "Agentic AI - Builders" create sheet, email, and calendar event',
            tasks=[
                PlannedTask("task-1", "drive", "list_files", {"q": "fullText contains 'Agentic AI'"}),
                PlannedTask("task-2", "sheets", "create_spreadsheet", {"title": "AI Data"}),
                PlannedTask("task-3", "sheets", "append_values", {
                    "spreadsheet_id": "$last_spreadsheet_id", "range": "Sheet1!A1", "values": "$drive_summary_values",
                }),
                PlannedTask("task-4", "gmail", "send_message", {
                    "to_email": "haseebmir.hm@gmail.com", "subject": "AI Data Sheet", "body": "Sheet is ready",
                }),
                PlannedTask("task-5", "calendar", "create_event", {
                    "summary": "Review AI Data", "start_date": "2026-04-20",
                }),
            ],
        )
        report = executor.execute(plan)
        assert report.success is True
        assert len(report.executions) == 5
        # Check correct services were called
        services_called = [cmd[:3] for cmd in runner.commands]
        assert ["drive", "files", "list"] in services_called
        assert ["sheets", "spreadsheets", "create"] in services_called
        assert ["calendar", "events", "insert"] in services_called

    def test_unresolved_placeholder_fails_gracefully(self):
        """Tasks with invalid placeholders should fail, not crash."""
        runner = FakeRunner()
        executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
        plan = RequestPlan(
            raw_text="test",
            tasks=[
                PlannedTask("task-1", "sheets", "append_values", {
                    "spreadsheet_id": "{{invalid_id}}",
                    "range": "A1",
                    "values": [["data"]],
                }),
            ],
        )
        report = executor.execute(plan)
        assert report.success is False
        assert "unresolved placeholder" in report.executions[0].result.error.lower()

    def test_range_auto_fix_with_space_in_tab_name(self):
        """Verify Sheet1!A1 is auto-replaced with the actual tab name when tab has spaces."""
        runner = FakeRunner()
        executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
        plan = RequestPlan(
            raw_text="save to RockstarIndia Emails sheet",
            tasks=[
                PlannedTask("task-1", "sheets", "create_spreadsheet", {"title": "RockstarIndia Emails"}),
                PlannedTask("task-2", "sheets", "append_values", {
                    "spreadsheet_id": "$last_spreadsheet_id",
                    "range": "Sheet1!A1",
                    "values": [["Name", "Email"]],
                }),
            ],
        )
        report = executor.execute(plan)
        assert report.success is True
        append_cmd = runner.commands[1]
        params_str = append_cmd[append_cmd.index("--params") + 1]
        assert "'RockstarIndia Emails'!A1" in params_str


# =====================================================================
# 4. RELEVANCE FILTER TESTS
# =====================================================================

class TestRelevanceFilter:

    def test_extract_keywords_from_quoted_phrase(self):
        keywords = extract_keywords('''Search Google Documents for "Agentic AI - Builders"''')
        assert any("agentic ai" in k for k in keywords)

    def test_score_matching_item_high(self):
        score = score_item("Agentic AI - Builders Project", ["agentic ai - builders"])
        assert score > 0.5

    def test_score_unrelated_item_zero(self):
        score = score_item("weapon_244.qvm", ["agentic ai - builders"])
        assert score == 0.0

    def test_filter_drive_files_removes_irrelevant(self):
        files = [
            {"name": "Agentic AI - Builders", "mimeType": "application/vnd.google-apps.document"},
            {"name": "weapon_244.qvm", "mimeType": "application/octet-stream"},
            {"name": "weapon_146.qvm", "mimeType": "application/octet-stream"},
        ]
        keywords = ["agentic ai - builders"]
        filtered = filter_drive_files(files, keywords)
        assert len(filtered) == 1
        assert filtered[0]["name"] == "Agentic AI - Builders"

    def test_filter_preserves_all_when_no_keywords(self):
        files = [{"name": "a"}, {"name": "b"}]
        assert filter_drive_files(files, []) == files

    def test_filter_preserves_all_when_nothing_matches(self):
        """If nothing matches, return all files (don't silently drop everything)."""
        files = [{"name": "random.txt"}]
        filtered = filter_drive_files(files, ["completely unrelated phrase xyz123"])
        assert len(filtered) == 1


# =====================================================================
# 5. OUTPUT FORMATTER TESTS — Human-readable output for all services
# =====================================================================

class TestOutputFormatter:
    formatter = HumanReadableFormatter()

    def test_drive_folder_creation(self):
        result = ExecutionResult(
            success=True, command=["gws.exe"],
            stdout='{"id":"f1","kind":"drive#file","mimeType":"application/vnd.google-apps.folder","name":"Test"}',
        )
        output = self.formatter.format_execution_result(result)
        assert "Command succeeded" in output

    def test_calendar_event_list(self):
        result = ExecutionResult(
            success=True, command=["gws.exe"],
            stdout='{"items":[{"id":"e1","summary":"Team Sync","start":{"date":"2026-04-15"},"end":{"date":"2026-04-15"}}]}',
        )
        output = self.formatter.format_execution_result(result)
        assert "1 calendar event" in output
        assert "Team Sync" in output

    def test_spreadsheet_creation_shows_url(self):
        result = ExecutionResult(
            success=True, command=["gws.exe"],
            stdout='{"spreadsheetId":"s1","spreadsheetUrl":"https://docs.google.com/spreadsheets/d/s1/edit","properties":{"title":"Budget"}}',
        )
        output = self.formatter.format_execution_result(result)
        assert "Created Budget in Google Sheets" in output
        assert "https://docs.google.com/spreadsheets" in output

    def test_gmail_list_shows_count(self):
        result = ExecutionResult(
            success=True, command=["gws.exe"],
            stdout='{"messages":[{"id":"m1"},{"id":"m2"}],"resultSizeEstimate":201}',
        )
        output = self.formatter.format_execution_result(result)
        assert "201" in output

    def test_error_result_shows_stderr(self):
        result = ExecutionResult(
            success=False, command=["gws.exe"],
            stderr="error[api]: Unable to parse range: Sheet1!A1",
        )
        output = self.formatter.format_execution_result(result)
        assert "Unable to parse range" in output

    def test_chat_send_message(self):
        planner = CommandPlanner()
        args = planner.build_command("chat", "send_message", {"space": "SPACE_ID", "text": "hello"})
        assert args == [
            "chat",
            "spaces",
            "messages",
            "create",
            "--params",
            '{"parent": "SPACE_ID"}',
            "--json",
            '{"text": "hello"}'
        ]

    def test_meet_create_meeting(self):
        planner = CommandPlanner()
        args = planner.build_command("meet", "create_meeting", {})
        assert args == ["meet", "spaces", "create"]
