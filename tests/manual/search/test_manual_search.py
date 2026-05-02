import os

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task

TEST_WEB_SEARCH_QUERY = os.getenv("TEST_WEB_SEARCH_QUERY", "Agentic AI Google Workspace")


@pytest.mark.live_integration
def test_manual_1(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run a live web-search task and verify expected output markers."""
    monkeypatch.delenv("CI", raising=False)
    # Web search verification
    run_task(
        f"Web search for '{TEST_WEB_SEARCH_QUERY}' and email the top results.",
        expected=["Result", "Sent", "Search"],
        service="search",
    )
