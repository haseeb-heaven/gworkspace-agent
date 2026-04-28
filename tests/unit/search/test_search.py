import json
import os
from unittest.mock import MagicMock

import pytest

from gws_assistant.execution import SearchToSheetsWorkflow
from gws_assistant.planner import CommandPlanner
from gws_assistant.tools.web_search import summarize_results, web_search_tool


class TestSearchUnit:
    planner = CommandPlanner()

    def test_web_search_command_building(self):
        args = self.planner.build_command("search", "web_search", {"query": "Latest Agentic AI news"})
        params = json.loads(args[args.index("--params") + 1])
        assert params["query"] == "Latest Agentic AI news"

    def test_web_search_tool_no_ddg(self, mocker):
        # Mock community import failure
        import gws_assistant.tools.web_search as ws

        mocker.patch.object(ws, "HAS_DDG", False)
        mocker.patch.object(ws, "HAS_TAVILY", False)

        result = web_search_tool.invoke({"query": "test"})
        assert result["error"] is not None
        assert "DuckDuckGo search failed or returned no usable results." in result["error"]
        assert "Tavily search isn't available" in result["error"]

    def test_web_search_tool_falls_back_to_tavily(self, mocker):
        import gws_assistant.tools.web_search as ws

        class FailingDuckDuckGo:
            def __init__(self, num_results: int) -> None:
                self.num_results = num_results

            def run(self, payload):
                raise RuntimeError("ddg unavailable")

            def invoke(self, payload):
                return self.run(payload)

        class FakeTavily:
            def __init__(self, max_results: int) -> None:
                self.max_results = max_results

            def run(self, payload):
                return {
                    "results": [
                        {
                            "title": "Tavily Result",
                            "content": "Fallback content",
                            "url": "https://example.com/result",
                        }
                    ]
                }

            def invoke(self, payload):
                return self.run(payload)

        mocker.patch.object(ws, "HAS_DDG", True)
        mocker.patch.object(ws, "HAS_TAVILY", True)
        mocker.patch.object(ws, "DuckDuckGoSearchResults", FailingDuckDuckGo, create=True)
        mocker.patch.object(ws, "TavilySearchResults", FakeTavily, create=True)
        mocker.patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}, clear=False)

        result = web_search_tool.invoke({"query": "test fallback"})
        assert result.get("error") is None
        assert result["results"][0]["title"] == "Tavily Result"
        assert "Fallback content" in result["results"][0]["content"]

    def test_summarize_results(self):
        result = summarize_results.invoke({"text": "long text here"})
        assert result == "long text here"


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
