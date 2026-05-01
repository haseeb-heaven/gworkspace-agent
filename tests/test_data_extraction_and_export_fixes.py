"""Regression tests for the data-extraction and Drive-export fixes.

These tests cover three scenarios that previously failed in production:

1. **Web search → Sheets** — verifying that the body resolved into a follow-up
   email comes from the search task and that ``$search_summary_table`` /
   ``$search_summary_rows`` are populated independently of any Gmail context.
2. **Google Doc extraction → Email** — verifying that exporting a Doc and
   piping the content into an email body uses the document text rather than
   any unrelated Gmail snippet.
3. **Drive file export** — verifying that the path-traversal validator
   accepts the export sandbox even when the export path is a Windows
   extended-length / UNC path (``\\\\?\\D:\\...``).

The tests intentionally avoid touching the live ``gws`` binary or the public
internet — they substitute a :class:`FakeRunner` for the GWS subprocess and
``mocker.patch`` the web-search tool. They are therefore CI-safe and do not
require :envvar:`GWS_BINARY_PATH`.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from dotenv import load_dotenv

load_dotenv()

from gws_assistant.execution import PlanExecutor
from gws_assistant.execution.path_safety import (
    get_allowed_export_dirs,
    is_within_allowed_dir,
)
from gws_assistant.gws_runner import GWSRunner
from gws_assistant.models import ExecutionResult, PlannedTask, RequestPlan
from gws_assistant.planner import CommandPlanner

# ---------------------------------------------------------------------------
# Test fixture: FakeRunner identical in spirit to the one in test_execution.py
# but trimmed to the subset of GWS endpoints exercised here.
# ---------------------------------------------------------------------------

_BIN = os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws")


class FakeRunner(GWSRunner):
    """A GWSRunner that records every invocation and returns canned JSON."""

    def __init__(self) -> None:
        super().__init__(Path(_BIN), logging.getLogger("test"))
        self.commands: list[list[str]] = []

    def run(self, args: list[str], timeout_seconds: int = 90) -> ExecutionResult:
        self.commands.append(args)

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
                command=[_BIN, *args],
                stdout=json.dumps(
                    {
                        "spreadsheetId": "sheet-1",
                        "spreadsheetUrl": "https://example.test/sheet",
                        "properties": {"title": title},
                        "sheets": [{"properties": {"title": title}}],
                    }
                ),
            )

        if args[:4] == ["sheets", "spreadsheets", "values", "append"]:
            return ExecutionResult(
                success=True,
                command=[_BIN, *args],
                stdout='{"updates":{"updatedRows":2,"updatedCells":6,"updatedRange":"Sheet1!A1:C2"}}',
            )

        if args[:3] == ["drive", "files", "export"]:
            return ExecutionResult(
                success=True,
                command=[_BIN, *args],
                stdout=json.dumps(
                    {"saved_file": "scratch/exports/download_d1", "mimeType": "text/plain"}
                ),
            )

        if args[:3] == ["drive", "files", "list"]:
            return ExecutionResult(
                success=True,
                command=[_BIN, *args],
                stdout=json.dumps(
                    {
                        "files": [
                            {
                                "id": "d1",
                                "name": os.getenv("TEST_DOC_QUERY", "CcaaS - AI Product"),
                                "mimeType": "application/vnd.google-apps.document",
                            }
                        ]
                    }
                ),
            )

        if args[:4] == ["gmail", "users", "messages", "list"]:
            # Only a single sparse message — exercises the "no payload" branch
            # where the historical bug substituted snippet for subject.
            return ExecutionResult(
                success=True,
                command=[_BIN, *args],
                stdout=json.dumps(
                    {
                        "messages": [
                            {
                                "id": "m1",
                                "threadId": "t1",
                                "snippet": "Unrelated gmail snippet body",
                            }
                        ],
                        "resultSizeEstimate": 1,
                    }
                ),
            )

        if args[:4] == ["gmail", "users", "messages", "send"]:
            return ExecutionResult(
                success=True,
                command=[_BIN, *args],
                stdout='{"id":"sent-1","labelIds":["SENT"]}',
            )

        return ExecutionResult(success=True, command=[_BIN, *args], stdout="{}")


@pytest.fixture(autouse=True)
def _mock_react(mocker):
    """Disable the ReACT loops so the executor runs deterministically."""
    mocker.patch(
        "gws_assistant.execution.PlanExecutor._think",
        return_value="Thought: Proceeding with planned task.",
    )
    mocker.patch("gws_assistant.execution.PlanExecutor._should_replan", return_value=False)
    mocker.patch("gws_assistant.execution.PlanExecutor._verify_artifact_content", return_value=None)
    mocker.patch("gws_assistant.execution.PlanExecutor.verify_resource", return_value=True)


def _decode_email_body(args: list[str]) -> str:
    raw = json.loads(args[args.index("--json") + 1])["raw"]
    return base64.urlsafe_b64decode(raw).decode("utf-8")


# ---------------------------------------------------------------------------
# 1. Path safety helper
# ---------------------------------------------------------------------------


class TestPathSafety:
    """Unit tests for the standalone ``path_safety`` helper."""

    def test_relative_path_inside_scratch_is_allowed(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "scratch" / "exports").mkdir(parents=True)
        target = tmp_path / "scratch" / "exports" / "download_d1"
        target.write_text("payload")
        assert is_within_allowed_dir(str(target)) is True

    def test_relative_path_inside_downloads_is_allowed(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "downloads").mkdir()
        target = tmp_path / "downloads" / "x.txt"
        target.write_text("payload")
        assert is_within_allowed_dir(str(target)) is True

    def test_path_outside_sandbox_is_rejected(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        outside = tmp_path / "etc" / "passwd"
        outside.parent.mkdir(parents=True)
        outside.write_text("nope")
        assert is_within_allowed_dir(str(outside)) is False

    def test_windows_extended_length_prefix_is_normalised(self, tmp_path, monkeypatch):
        """``\\\\?\\D:\\...\\scratch\\exports`` must compare equal to ``scratch/exports``.

        The actual filesystem on the CI runner is POSIX, but the validator
        must still strip the Windows extended-length prefix before comparing
        — otherwise a runner that produced such a path on Windows would be
        rejected even when it points inside the sandbox.
        """
        monkeypatch.chdir(tmp_path)
        (tmp_path / "scratch" / "exports").mkdir(parents=True)
        # Build the equivalent of ``\\?\<abs>/scratch/exports/download``.
        absolute_target = tmp_path / "scratch" / "exports" / "download_d1"
        absolute_target.write_text("payload")
        candidate_with_prefix = "\\\\?\\" + str(absolute_target)
        assert is_within_allowed_dir(candidate_with_prefix) is True

    def test_env_overrides_sandbox_directories(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        custom = tmp_path / "custom_export_root"
        custom.mkdir()
        target = custom / "file.txt"
        target.write_text("ok")
        monkeypatch.setenv("DOWNLOADS_DIR", str(custom))
        monkeypatch.setenv("SCRATCH_DIR", str(custom))
        allowed = get_allowed_export_dirs()
        assert any(str(custom).lower().rstrip("/\\") in entry.lower() for entry in allowed)
        assert is_within_allowed_dir(str(target)) is True

    def test_empty_path_is_rejected(self):
        assert is_within_allowed_dir("") is False
        assert is_within_allowed_dir(None) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 2. Web search → Sheets workflow
# ---------------------------------------------------------------------------


class TestWebSearchToSheets:
    """Web search results must populate sheets and outgoing email bodies."""

    @pytest.fixture
    def search_results(self):
        return {
            "query": os.getenv("TEST_WEB_SEARCH_QUERY", "Agentic AI Google Workspace"),
            "results": [
                {
                    "title": "LangGraph",
                    "snippet": "Graph-based agent orchestration",
                    "url": "https://example.com/langgraph",
                },
                {
                    "title": "AutoGen",
                    "snippet": "Multi-agent conversations",
                    "url": "https://example.com/autogen",
                },
            ],
            "error": None,
        }

    def test_search_results_appended_to_sheet(self, mocker, search_results):
        mocker.patch(
            "gws_assistant.tools.web_search.web_search_tool",
            SimpleNamespace(invoke=lambda payload: search_results),
        )
        runner = FakeRunner()
        executor = PlanExecutor(
            planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test")
        )
        sheet_title = os.getenv("TEST_SHEET_NAME", "Systematic Testing Data")
        plan = RequestPlan(
            raw_text="search and save",
            tasks=[
                PlannedTask(
                    id="task-1",
                    service="search",
                    action="web_search",
                    parameters={"query": search_results["query"]},
                ),
                PlannedTask(
                    id="task-2",
                    service="sheets",
                    action="create_spreadsheet",
                    parameters={"title": sheet_title},
                ),
                PlannedTask(
                    id="task-3",
                    service="sheets",
                    action="append_values",
                    parameters={
                        "spreadsheet_id": "$last_spreadsheet_id",
                        "range": "Sheet1!A1",
                        "values": "$search_summary_rows",
                    },
                ),
            ],
        )
        report = executor.execute(plan)
        assert report.success is True

        append_cmd = next(c for c in runner.commands if c[:4] == ["sheets", "spreadsheets", "values", "append"])
        json_payload = append_cmd[append_cmd.index("--json") + 1]
        # Search results must reach the sheet — no Gmail snippet leakage.
        assert "LangGraph" in json_payload
        assert "https://example.com/langgraph" in json_payload
        assert "Unrelated gmail snippet" not in json_payload

    def test_search_then_email_uses_search_body_not_gmail(self, mocker, search_results):
        """Regression test for the ``_derive_email_body_placeholder`` priority bug.

        The previous implementation favoured ``gmail`` when the plan contained
        a ``gmail.send_message`` step, which made every search-and-email plan
        substitute Gmail snippets for the actual search body. The fix re-ranks
        the placeholder selection so search/docs/drive win over gmail.
        """
        from gws_assistant.langchain_agent import _derive_email_body_placeholder

        plan_tasks = [
            {"service": "search", "action": "web_search"},
            {"service": "gmail", "action": "send_message"},
        ]
        assert _derive_email_body_placeholder(plan_tasks) == "$search_summary_table"

        # End-to-end: the resolver must substitute the search summary, not the
        # Gmail snippet, into the email body when both context values exist.
        mocker.patch(
            "gws_assistant.tools.web_search.web_search_tool",
            SimpleNamespace(invoke=lambda payload: search_results),
        )
        runner = FakeRunner()
        executor = PlanExecutor(
            planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test")
        )
        plan = RequestPlan(
            raw_text="search and email",
            tasks=[
                PlannedTask(
                    id="task-0",
                    service="gmail",
                    action="list_messages",
                    parameters={"q": "anything", "max_results": 1},
                ),
                PlannedTask(
                    id="task-1",
                    service="search",
                    action="web_search",
                    parameters={"query": search_results["query"]},
                ),
                PlannedTask(
                    id="task-2",
                    service="gmail",
                    action="send_message",
                    parameters={
                        "to_email": os.getenv("DEFAULT_RECIPIENT_EMAIL") or "test@example.com",
                        "subject": "Top results",
                        "body": "$search_summary_table",
                    },
                ),
            ],
        )
        report = executor.execute(plan)
        assert report.success is True

        send_cmd = next(c for c in runner.commands if c[:4] == ["gmail", "users", "messages", "send"])
        body = _decode_email_body(send_cmd)
        assert "LangGraph" in body
        assert "Unrelated gmail snippet" not in body


# ---------------------------------------------------------------------------
# 3. Google Doc / Drive export → Email
# ---------------------------------------------------------------------------


class TestDriveExportToEmail:
    """Exported Doc content must be the body of any follow-up email."""

    @pytest.fixture
    def export_file(self, tmp_path, monkeypatch):
        """Materialise the exported file under ``scratch/exports`` so the
        path-traversal validator can resolve it.

        The fixture also points the sandbox env vars at the temporary
        directory so the validator accepts the absolute path that
        ``FakeRunner`` will surface.
        """
        export_root = tmp_path / "scratch" / "exports"
        export_root.mkdir(parents=True)
        export_path = export_root / "download_d1"
        export_path.write_text("Doc content from Drive export", encoding="utf-8")

        monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path / "downloads"))
        monkeypatch.setenv("SCRATCH_DIR", str(tmp_path / "scratch"))
        return export_path

    def test_export_file_is_read_and_email_body_resolved(self, export_file, mocker):
        """End-to-end: drive.export_file → gmail.send_message with body
        ``$drive_export_file`` must place the exported Doc content into the
        outgoing email — not a Gmail snippet."""
        runner = FakeRunner()

        def runner_with_real_path(args, timeout_seconds=90):
            res = FakeRunner.run(runner, args, timeout_seconds)
            if args[:3] == ["drive", "files", "export"]:
                payload = json.loads(res.stdout)
                payload["saved_file"] = str(export_file)
                res.stdout = json.dumps(payload)
            return res

        mocker.patch.object(runner, "run", side_effect=runner_with_real_path)

        executor = PlanExecutor(
            planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test")
        )
        plan = RequestPlan(
            raw_text="export and email",
            tasks=[
                PlannedTask(
                    id="task-1",
                    service="drive",
                    action="export_file",
                    parameters={"file_id": "f1", "mime_type": "text/plain"},
                ),
                PlannedTask(
                    id="task-2",
                    service="gmail",
                    action="send_message",
                    parameters={
                        "to_email": os.getenv("DEFAULT_RECIPIENT_EMAIL") or "test@example.com",
                        "subject": "Exported doc",
                        "body": "Content: $drive_export_file",
                    },
                ),
            ],
        )
        report = executor.execute(plan)
        assert report.success is True

        send_cmd = next(c for c in runner.commands if c[:4] == ["gmail", "users", "messages", "send"])
        body = _decode_email_body(send_cmd)
        assert "Doc content from Drive export" in body

    def test_export_file_outside_sandbox_is_blocked(self, tmp_path, mocker, monkeypatch):
        """A response that points outside the sandbox must be rejected with
        the canonical "Path traversal blocked" error (defence-in-depth)."""
        monkeypatch.chdir(tmp_path)
        # File exists but lives outside both downloads/ and scratch/.
        outside = tmp_path / "etc" / "secret"
        outside.parent.mkdir(parents=True)
        outside.write_text("secret")

        runner = FakeRunner()

        def runner_returns_outside(args, timeout_seconds=90):
            if args[:3] == ["drive", "files", "export"]:
                return ExecutionResult(
                    success=True,
                    command=[_BIN, *args],
                    stdout=json.dumps({"saved_file": str(outside), "mimeType": "text/plain"}),
                )
            return FakeRunner.run(runner, args, timeout_seconds)

        mocker.patch.object(runner, "run", side_effect=runner_returns_outside)
        executor = PlanExecutor(
            planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test")
        )
        plan = RequestPlan(
            raw_text="export evil",
            tasks=[
                PlannedTask(
                    id="task-1",
                    service="drive",
                    action="export_file",
                    parameters={"file_id": "f1", "mime_type": "text/plain"},
                )
            ],
        )
        report = executor.execute(plan)
        # The single export task should fail with a path-traversal message.
        last = report.executions[-1]
        assert last.result.success is False
        assert "Path traversal blocked" in (last.result.error or "")


# ---------------------------------------------------------------------------
# 4. Gmail context isolation
# ---------------------------------------------------------------------------


class TestGmailContextIsolation:
    """Gmail snippets and subjects must live in distinct context keys."""

    def test_subject_and_snippet_are_kept_separate(self):
        from gws_assistant.execution.context_updater import ContextUpdaterMixin

        updater = ContextUpdaterMixin()
        context: dict = {}
        data = {
            "messages": [
                {"id": "m1", "threadId": "t1", "snippet": "preview text"},
            ]
        }
        updater._update_context_from_result(data, context)

        # ``gmail_summary_rows`` reflects subject (or default), NOT the snippet.
        assert context["gmail_summary_rows"][0][1] == "No Subject"
        # The snippet now has its own key set.
        assert context["gmail_snippets_rows"][0][1] == "preview text"
        assert "preview text" in context["gmail_snippets_table"]
