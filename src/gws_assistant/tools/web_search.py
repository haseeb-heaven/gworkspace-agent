"""Web search tool for Langchain agent."""

import dataclasses
import os

from langchain_core.tools import tool

try:
    from langchain_community.tools.ddg_search.tool import DuckDuckGoSearchResults
except ImportError:
    DuckDuckGoSearchResults = None

try:
    from langchain_community.tools.tavily_search import TavilySearchResults
except ImportError:
    TavilySearchResults = None

from gws_assistant.models import WebSearchResult


@tool
def web_search_tool(query: str, max_results: int = 5) -> dict[str, str | list | None]:
    """
    Performs a web search using DuckDuckGo (with Tavily as fallback) to find information.
    Use this when you need external facts, news, documentation, or when the user asks a
    question that requires internet access.

    Args:
        query: The search terms to look for.
        max_results: Max number of snippets to return (default 5).

    Returns:
        Dictionary containing search query, resulting snippets and error message if any.
    """
    ddg_error: str | None = None

    # --- Primary: DuckDuckGo ---
    if DuckDuckGoSearchResults is not None:
        try:
            search = DuckDuckGoSearchResults(num_results=max_results)
            raw_result_str = search.invoke({"query": query})
            snippets = []
            if raw_result_str:
                snippets.append({"content": raw_result_str, "title": "Search Snippets"})
            if snippets:
                return dataclasses.asdict(WebSearchResult(query=query, results=snippets))
            ddg_error = "DuckDuckGo search failed or returned no usable results."
        except Exception as exc:
            ddg_error = f"DuckDuckGo search failed or returned no usable results. ({exc})"
    else:
        ddg_error = "DuckDuckGo search failed or returned no usable results."

    # --- Fallback: Tavily ---
    tavily_key = os.environ.get("TAVILY_API_KEY", "")
    if TavilySearchResults is not None and tavily_key:
        try:
            tavily = TavilySearchResults(max_results=max_results)
            raw = tavily.invoke({"query": query})
            if isinstance(raw, dict):
                results = raw.get("results", [])
            elif isinstance(raw, list):
                results = raw
            else:
                results = []
            def sanitize(text: str) -> str:
                if not text:
                    return ""
                # Replace newlines with spaces
                text = text.replace("\r", " ").replace("\n", " ")
                # Remove non-ASCII characters
                text = text.encode("ascii", "ignore").decode("ascii")
                # Limit length
                return (text[:2000] + "...") if len(text) > 2000 else text

            snippets = [
                {
                    "title": sanitize(r.get("title", "")),
                    "content": sanitize(r.get("content", "")),
                    "url": r.get("url", "")
                }
                for r in results
                if isinstance(r, dict)
            ]
            if snippets:
                return dataclasses.asdict(WebSearchResult(query=query, results=snippets))
        except Exception as exc:
            return dataclasses.asdict(WebSearchResult(
                query=query,
                error=f"{ddg_error} Tavily fallback also failed: {exc}",
            ))

    # Neither backend available / returned results
    tavily_msg = (
        "Tavily search isn't available (no TAVILY_API_KEY or langchain-community not installed)."
        if not tavily_key or TavilySearchResults is None
        else "Tavily search isn't available."
    )
    return dataclasses.asdict(WebSearchResult(
        query=query,
        error=f"{ddg_error} {tavily_msg}",
    ))


@tool
def summarize_results(text: str) -> str:
    """
    Summarize a block of text into a concise, easily digestible format.
    Use this when search results or documents are too long to return raw.

    Args:
        text: The text to summarize.

    Returns:
        A concise summary string.
    """
    # Echo back — the LLM reading this tool output will perform the summarization.
    return text
