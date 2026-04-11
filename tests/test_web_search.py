import pytest
from gws_assistant.tools.web_search import web_search_tool, summarize_results

def test_web_search_tool_no_ddg(mocker):
    # Mock community import failure
    import gws_assistant.tools.web_search as ws
    mocker.patch.object(ws, 'DuckDuckGoSearchResults', None)
    
    result = ws.web_search_tool.invoke({"query": "test"})
    assert result["error"] is not None
    assert "DuckDuckGo Search isn't available" in result["error"]

def test_summarize_results():
    result = summarize_results.invoke({"text": "long text here"})
    assert "Please summarize" in result
    assert "long text here" in result
