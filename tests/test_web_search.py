import pytest
from gws_assistant.tools.web_search import web_search_tool, summarize_results

def test_web_search_tool_no_ddg(mocker):
    # Mock community import failure
    import gws_assistant.tools.web_search as ws
    mocker.patch.object(ws, 'DuckDuckGoSearchResults', None)
    mocker.patch.object(ws, 'TavilySearchResults', None)
    
    result = ws.web_search_tool.invoke({"query": "test"})
    assert result["error"] is not None
    assert "DuckDuckGo search failed or returned no usable results." in result["error"]
    assert "Tavily search isn't available" in result["error"]

def test_web_search_tool_falls_back_to_tavily(mocker):
    import gws_assistant.tools.web_search as ws

    class FailingDuckDuckGo:
        def __init__(self, num_results: int) -> None:
            self.num_results = num_results

        def invoke(self, payload):
            raise RuntimeError("ddg unavailable")

    class FakeTavily:
        def __init__(self, max_results: int) -> None:
            self.max_results = max_results

        def invoke(self, payload):
            return {
                "results": [
                    {
                        "title": "Tavily Result",
                        "content": "Fallback content",
                        "url": "https://example.com/result",
                    }
                ]
            }

    mocker.patch.object(ws, "DuckDuckGoSearchResults", FailingDuckDuckGo)
    mocker.patch.object(ws, "TavilySearchResults", FakeTavily)
    mocker.patch.dict(ws.os.environ, {"TAVILY_API_KEY": "test-key"}, clear=False)

    result = ws.web_search_tool.invoke({"query": "test fallback"})
    assert result["error"] is None
    assert result["results"][0]["title"] == "Tavily Result"
    assert "Fallback content" in result["results"][0]["content"]

def test_summarize_results():
    result = summarize_results.invoke({"text": "long text here"})
    assert result == "long text here"
