
from unittest.mock import MagicMock

import pytest

from gws_assistant.execution import SearchToSheetsWorkflow


class MockWebSearch:
    def web_search(self, query):
        return {
            "rows": [
                ["Framework A", "Description A", "1000", "Feature A1, A2"],
                ["Framework B", "Description B", "2000", "Feature B1, B2"],
                ["Framework C", "Description C", "3000", "Feature C1, C2"],
            ]
        }

class MockSheets:
    def create_spreadsheet(self, title):
        return {"spreadsheetId": "123", "title": title}

    def append_values(self, spreadsheet_id, range, values):
        return True

def test_search_to_sheets_workflow():
    mock_search = MockWebSearch()
    mock_sheets = MockSheets()
    workflow = SearchToSheetsWorkflow(web_search=mock_search, sheets=mock_sheets)

    success = workflow.execute(query="Top Agentic AI frameworks", title="Test Spreadsheet")
    assert success is True

def test_search_to_sheets_workflow_invalid_query():
    mock_search = MagicMock()
    mock_sheets = MagicMock()
    workflow = SearchToSheetsWorkflow(web_search=mock_search, sheets=mock_sheets)

    with pytest.raises(ValueError, match="Query must be a non-empty string."):
        workflow.execute(query="")

def test_search_to_sheets_workflow_no_results():
    mock_search = MagicMock()
    mock_search.web_search.return_value = {}
    mock_sheets = MagicMock()
    workflow = SearchToSheetsWorkflow(web_search=mock_search, sheets=mock_sheets)

    success = workflow.execute(query="Unknown Query")
    assert success is False
