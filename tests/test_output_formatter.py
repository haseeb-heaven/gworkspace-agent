from __future__ import annotations

import os

from gws_assistant.models import ExecutionResult
from gws_assistant.output_formatter import HumanReadableFormatter


def test_formatter_treats_sheets_append_as_save_not_create():
    formatter = HumanReadableFormatter()
    result = ExecutionResult(
        success=True,
        command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws")],
        stdout='{"spreadsheetId":"sheet-1","updates":{"updatedRows":2,"updatedCells":6,"updatedRange":"Sheet1!A1:C2"}}',
    )
    output = formatter.format_execution_result(result)
    assert output == "Command succeeded.\nSaved 2 rows and 6 cells to Sheet1!A1:C2."


def test_formatter_reports_sheet_values_read():
    formatter = HumanReadableFormatter()
    result = ExecutionResult(
        success=True,
        command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws")],
        stdout='{"range":"Sheet1!A1:B2","values":[["Name","Role"],["Alice","Engineer"]]}',
    )
    output = formatter.format_execution_result(result)
    assert output.startswith("Command succeeded.\nRead 2 rows and 4 cells from Sheet1!A1:B2.")
    assert "Name" in output
    assert "Alice" in output


def test_formatter_reports_email_sent():
    formatter = HumanReadableFormatter()
    result = ExecutionResult(
        success=True,
        command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws")],
        stdout='{"id":"abc123","labelIds":["SENT"]}',
    )
    output = formatter.format_execution_result(result)
    assert output == "Command succeeded.\nEmail sent successfully. Message ID: abc123"


def test_formatter_previews_drive_files_as_table():
    formatter = HumanReadableFormatter()
    result = ExecutionResult(
        success=True,
        command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws")],
        stdout=(
            '{"files":[{"id":"f1","name":"Resume.pdf","mimeType":"application/pdf","modifiedTime":"2026-04-10T10:00:00Z"},'
            '{"id":"f2","name":"Notes.txt","mimeType":"text/plain","modifiedTime":"2026-04-10T11:00:00Z"}]}'
        ),
    )
    output = formatter.format_execution_result(result)
    assert "Found 2 Drive files." in output
    assert "Resume.pdf" in output
    assert "PDF" in output


def test_formatter_previews_gmail_message():
    formatter = HumanReadableFormatter()
    result = ExecutionResult(
        success=True,
        command=[os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws")],
        stdout=(
            '{"id":"m1","snippet":"Thanks for your interest","payload":{"headers":['
            '{"name":"From","value":"HR <jobs@example.com>"},'
            '{"name":"Subject","value":"Interview Update"},'
            '{"name":"Date","value":"Fri, 11 Apr 2026 10:00:00 +0000"}]}}'
        ),
    )
    output = formatter.format_execution_result(result)
    assert "From: HR <jobs@example.com>" in output
    assert "Subject: Interview Update" in output
    assert "From: HR <jobs@example.com>" in output
