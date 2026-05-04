"""Manual tests for web search functionality."""

import os

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task

TEST_WEB_SEARCH_QUERY = os.getenv("TEST_WEB_SEARCH_QUERY", "Agentic AI Google Workspace")


@pytest.mark.live_integration
def test_manual_1():
    """Web search verification - Search operation."""
    run_task(
        f"Search the web for '{TEST_WEB_SEARCH_QUERY}' and summarize the top 3 results.",
        expected=["completed"],
        service="search",
    )
