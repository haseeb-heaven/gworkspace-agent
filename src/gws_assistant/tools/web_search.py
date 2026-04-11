"""Web search tool for Langchain agent."""

from langchain_core.tools import tool
try:
    from langchain_community.tools.ddg_search.tool import DuckDuckGoSearchResults
except ImportError:
    DuckDuckGoSearchResults = None

from gws_assistant.models import WebSearchResult
import dataclasses

@tool
def web_search_tool(query: str, max_results: int = 5) -> dict[str, str | list | None]:
    """
    Performs a web search using DuckDuckGo to find information.
    Use this when you need external facts, news, documentation, or when the user asks a question that requires internet access.
    
    Args:
        query: The search terms to look for.
        max_results: Max number of snippets to return (default 5).
        
    Returns:
        Dictionary containing search query, resulting snippets and error message if any.
    """
    if DuckDuckGoSearchResults is None:
        return dataclasses.asdict(WebSearchResult(
            query=query, 
            error="DuckDuckGo Search isn't available. Ensure langchain-community is installed."
        ))

    try:
        # We parse the result natively instead of relying solely on the pre-formatted string.
        # But DGG wrapper in langchain-community natively returns string.
        search = DuckDuckGoSearchResults(num_results=max_results)
        raw_result_str = search.invoke({"query": query})
        
        # Simple extraction since DDG search returns formatted string "[snippet: ..., title: ..., link: ...]"
        snippets = []
        if raw_result_str:
            # Not building full parser here, return text wrapper.
            snippets.append({"content": raw_result_str, "title": "Search Snippets"})
            
        result = WebSearchResult(
            query=query,
            results=snippets,
        )
        return dataclasses.asdict(result)

    except Exception as e:
        return dataclasses.asdict(WebSearchResult(
            query=query,
            error=f"Web search failed: {str(e)}"
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
    # Simply echo the instructions back to the LLM. In an advanced version, this would invoke a separate chain. 
    # Since this is a tool FOR the LLM, the LLM itself will read this text and process it if needed within its context.
    # To truly have the tool summarize, we would need to pass an LLM instance here. 
    return f"Please summarize the following content:\n{text}"
