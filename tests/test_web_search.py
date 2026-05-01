from unittest.mock import MagicMock, patch

from gws_assistant.tools.web_search import web_search_tool


@patch("gws_assistant.tools.web_search.DuckDuckGoSearchResults")
def test_web_search_tool_ddg_list(mock_ddg):
    mock_inst = mock_ddg.return_value
    mock_inst.invoke.return_value = [
        MagicMock(page_content="Content 1", metadata={"title": "Title 1", "link": "http1"}),
        {"snippet": "Content 2", "title": "Title 2", "link": "http2"}
    ]

    with patch("gws_assistant.tools.web_search.HAS_DDG", True):
        # web_search_tool is a StructuredTool, call .invoke()
        result = web_search_tool.invoke({"query": "test query"})
        assert len(result["results"]) == 2
        assert result["results"][0]["content"] == "Content 1"
        assert result["results"][1]["content"] == "Content 2"

@patch("gws_assistant.tools.web_search.DuckDuckGoSearchResults")
def test_web_search_tool_ddg_string(mock_ddg):
    mock_inst = mock_ddg.return_value
    mock_inst.invoke.return_value = "snippet: Hello, title: World, link: http://test.com"

    with patch("gws_assistant.tools.web_search.HAS_DDG", True):
        result = web_search_tool.invoke({"query": "test query"})
        assert len(result["results"]) == 1
        assert result["results"][0]["content"] == "Hello"

@patch("gws_assistant.tools.web_search.DuckDuckGoSearchResults")
def test_web_search_tool_fallback_tavily(mock_ddg):
    # Mock DDG failure
    mock_ddg_inst = mock_ddg.return_value
    mock_ddg_inst.invoke.side_effect = Exception("DDG failed")

    # Mock Tavily success
    with patch("gws_assistant.tools.web_search.TavilySearchResults", create=True) as mock_tavily:
        mock_tavily_inst = mock_tavily.return_value
        mock_tavily_inst.invoke.return_value = [{"content": "Tavily content", "title": "Tavily title", "url": "http_tavily"}]

        with patch("gws_assistant.tools.web_search.HAS_DDG", True):
            with patch("gws_assistant.tools.web_search.HAS_TAVILY", True):
                with patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}):
                    result = web_search_tool.invoke({"query": "test query"})
                    assert result["results"][0]["content"] == "Tavily content"

def test_web_search_tool_no_results():
    with patch("gws_assistant.tools.web_search.HAS_DDG", False):
        with patch("gws_assistant.tools.web_search.HAS_TAVILY", False):
            result = web_search_tool.invoke({"query": "test query"})
            assert result["results"] == []
            assert "failed" in result["error"].lower()
