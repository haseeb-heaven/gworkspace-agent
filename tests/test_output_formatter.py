from __future__ import annotations

from gws_assistant.models import ExecutionResult
from gws_assistant.output_formatter import HumanReadableFormatter


def test_formatter_treats_sheets_append_as_save_not_create():
    formatter = HumanReadableFormatter()
    result = ExecutionResult(
        success=True,
        command=["gws.exe"],
        stdout='{"spreadsheetId":"sheet-1","updates":{"updatedRows":2,"updatedCells":6,"updatedRange":"Sheet1!A1:C2"}}',
    )
    output = formatter.format_execution_result(result)
    assert output == "Saved 2 rows and 6 cells to Sheet1!A1:C2."


def test_formatter_reports_sheet_values_read():
    formatter = HumanReadableFormatter()
    result = ExecutionResult(
        success=True,
        command=["gws.exe"],
        stdout='{"range":"Sheet1!A1:B2","values":[["Name","Role"],["Alice","Engineer"]]}',
    )
    output = formatter.format_execution_result(result)
    assert output == "Read 2 rows and 4 cells from Sheet1!A1:B2."


def test_formatter_reports_email_sent():
    formatter = HumanReadableFormatter()
    result = ExecutionResult(
        success=True,
        command=["gws.exe"],
        stdout='{"id":"abc123","labelIds":["SENT"]}',
    )
    output = formatter.format_execution_result(result)
    assert output == "Email sent successfully. Message ID: abc123"
