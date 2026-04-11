"""Web search tool for LangChain agent."""

from __future__ import annotations

import dataclasses
import os
from typing import Any

from langchain_core.tools import tool

try:
    from langchain_community.tools.ddg_search.tool import DuckDuckGoSearchResults
except ImportError:
    DuckDuckGoSearchResults = None

try:
    from langchain_community.tools.tavily_search.tool import TavilySearchResults
except ImportError:
    TavilySearchResults = None

from gws_assistant.models import WebSearchResult


@tool
def web_search_tool(query: str, max_results: int = 5) -> dict[str, str | list | None]:
    """
    Performs a web search using DuckDuckGo, with Tavily as a backup.

    Use this when you need external facts, news, documentation, or when the user
    asks a question that requires internet access.

    Args:
        query: The search terms to look for.
        max_results: Max number of snippets to return (default 5).

    Returns:
        Dictionary containing search query, resulting snippets and error message if any.
    """
    errors: list[str] = []

    result = _search_with_duckduckgo(query, max_results)
    if result is not None:
        return dataclasses.asdict(result)
    errors.append("DuckDuckGo search failed or returned no usable results.")

    result = _search_with_tavily(query, max_results)
    if result is not None:
        return dataclasses.asdict(result)
    if TavilySearchResults is None:
        errors.append("Tavily search isn't available. Ensure langchain-community is installed.")
    elif not os.getenv("TAVILY_API_KEY"):
        errors.append("TAVILY_API_KEY is not configured.")
    else:
        errors.append("Tavily search failed.")

    return dataclasses.asdict(WebSearchResult(query=query, error=" ".join(errors)))


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
    cleaned = " ".join((text or "").split()).strip()
    if not cleaned:
        return "No search results to summarize."
    if len(cleaned) <= 600:
        return cleaned
    return cleaned[:600].rstrip() + "... [truncated]"


def _search_with_duckduckgo(query: str, max_results: int) -> WebSearchResult | None:
    if DuckDuckGoSearchResults is None:
        return None

    try:
        search = DuckDuckGoSearchResults(num_results=max_results)
        raw_result = search.invoke({"query": query})
    except Exception:
        return None

    snippets = _normalize_search_results(raw_result)
    if not snippets:
        return None

    return WebSearchResult(query=query, results=snippets)


def _search_with_tavily(query: str, max_results: int) -> WebSearchResult | None:
    if TavilySearchResults is None or not os.getenv("TAVILY_API_KEY"):
        return None

    try:
        search = TavilySearchResults(max_results=max_results)
        raw_result = search.invoke({"query": query})
    except Exception:
        return None

    snippets = _normalize_search_results(raw_result)
    if not snippets:
        return None

    return WebSearchResult(query=query, results=snippets)


def _normalize_search_results(raw_result: Any) -> list[dict[str, str]]:
    snippets: list[dict[str, str]] = []

    if isinstance(raw_result, dict):
        results = raw_result.get("results")
        if isinstance(results, list):
            for item in results:
                if isinstance(item, dict):
                    snippets.append(_normalize_search_result_item(item))
        elif raw_result.get("answer") or raw_result.get("content") or raw_result.get("summary"):
            snippets.append(
                {
                    "title": str(raw_result.get("title") or "Search Result"),
                    "content": str(raw_result.get("answer") or raw_result.get("content") or raw_result.get("summary") or ""),
                    "link": str(raw_result.get("url") or raw_result.get("link") or ""),
                }
            )
    elif isinstance(raw_result, list):
        for item in raw_result:
            if isinstance(item, dict):
                snippets.append(_normalize_search_result_item(item))
            elif isinstance(item, str) and item.strip():
                snippets.append({"title": "Search Result", "content": item.strip(), "link": ""})
    elif isinstance(raw_result, str) and raw_result.strip():
        snippets.append({"title": "Search Result", "content": raw_result.strip(), "link": ""})

    return [snippet for snippet in snippets if snippet.get("content") or snippet.get("title") or snippet.get("link")]


def _normalize_search_result_item(item: dict[str, Any]) -> dict[str, str]:
    title = str(item.get("title") or item.get("name") or "Search Result").strip()
    content = str(item.get("content") or item.get("snippet") or item.get("raw_content") or item.get("answer") or "").strip()
    link = str(item.get("link") or item.get("url") or item.get("source") or "").strip()
    return {
        "title": title,
        "content": content,
        "link": link,
    }
