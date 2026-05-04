"""Unit tests for output_formatter.py — covers various GWS payload formatting."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from gws_assistant.models import ExecutionResult, PlanExecutionReport, PlannedTask
from gws_assistant.output_formatter import HumanReadableFormatter


@pytest.fixture
def formatter():
    return HumanReadableFormatter()


def test_format_execution_result_failure(formatter):
    res = ExecutionResult(success=False, stdout="", stderr="Error msg", error="Err", command=["gws"])
    assert "Error msg" in formatter.format_execution_result(res)


def test_format_execution_result_success_no_json(formatter):
    res = ExecutionResult(success=True, stdout="Plain text", stderr="", command=["gws"])
    assert "Command succeeded" in formatter.format_execution_result(res)
    assert "Plain text" in formatter.format_execution_result(res)


def test_format_gmail_list(formatter):
    payload = {"messages": [{"id": "1"}, {"id": "2"}], "resultSizeEstimate": 2}
    res = ExecutionResult(success=True, stdout=json.dumps(payload), stderr="", command=["gws"])
    out = formatter.format_execution_result(res)
    assert "Found an estimated 2 Gmail messages" in out


def test_format_gmail_message(formatter):
    payload = {
        "id": "m1",
        "snippet": "Hello snippet",
        "payload": {
            "headers": [
                {"name": "From", "value": "sender@test.com"},
                {"name": "Subject", "value": "Test Subject"}
            ]
        }
    }
    res = ExecutionResult(success=True, stdout=json.dumps(payload), stderr="", command=["gws"])
    out = formatter.format_execution_result(res)
    assert "From: sender@test.com" in out
    assert "Subject: Test Subject" in out
    assert "Snippet: Hello snippet" in out


def test_format_sheets_values(formatter):
    payload = {
        "values": [["Name", "Age"], ["Alice", "30"]],
        "range": "Sheet1!A1:B2"
    }
    res = ExecutionResult(success=True, stdout=json.dumps(payload), stderr="", command=["gws"])
    out = formatter.format_execution_result(res)
    assert "Read 2 rows and 4 cells" in out
    assert "Alice" in out


def test_format_drive_files(formatter):
    payload = {
        "files": [{"name": "Doc1", "mimeType": "text/plain", "webViewLink": "https://link"}]
    }
    res = ExecutionResult(success=True, stdout=json.dumps(payload), stderr="", command=["gws"])
    out = formatter.format_execution_result(res)
    assert "Found 1 Drive file" in out
    assert "Doc1" in out


def test_format_report(formatter):
    plan = MagicMock()
    plan.summary = "Plan summary"
    task = PlannedTask(id="1", service="gmail", action="send_message")
    res = ExecutionResult(success=True, stdout="{}", stderr="", command=["gws"])
    from gws_assistant.models import TaskExecution
    report = PlanExecutionReport(
        plan=plan,
        executions=[TaskExecution(task=task, result=res)],
        thought_trace=[]
    )
    out = formatter.format_report(report)
    assert "Plan summary" in out
    assert "1. gmail.send_message completed." in out


def test_format_contacts(formatter):
    payload = {
        "connections": [
            {"names": [{"displayName": "John Doe"}], "emailAddresses": [{"value": "john@example.com"}]}
        ]
    }
    res = ExecutionResult(success=True, stdout=json.dumps(payload), stderr="", command=["gws"])
    out = formatter.format_execution_result(res)
    assert "Found 1 contact" in out
    assert "John Doe" in out


def test_format_slides(formatter):
    payload = {"title": "Presentation 1", "slides": [{}, {}], "presentationId": "p123"}
    res = ExecutionResult(success=True, stdout=json.dumps(payload), stderr="", command=["gws"])
    out = formatter.format_execution_result(res)
    assert "Presentation: Presentation 1" in out
    assert "Slides: 2" in out


def test_format_docs(formatter):
    payload = {"title": "Doc 1", "documentId": "d123", "body": {"content": []}}
    res = ExecutionResult(success=True, stdout=json.dumps(payload), stderr="", command=["gws"])
    out = formatter.format_execution_result(res)
    assert "Document: Doc 1" in out
    assert "ID: d123" in out


def test_format_calendar_events(formatter):
    payload = {
        "items": [
            {
                "summary": "Meeting",
                "start": {"dateTime": "2023-01-01T10:00:00Z"},
                "end": {"dateTime": "2023-01-01T11:00:00Z"},
                "id": "e1"
            }
        ]
    }
    res = ExecutionResult(success=True, stdout=json.dumps(payload), stderr="", command=["gws"])
    out = formatter.format_execution_result(res)
    assert "Found 1 calendar event" in out
    assert "Meeting" in out
