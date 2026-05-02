import os

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task

TEST_WEB_SEARCH_QUERY = os.getenv("TEST_WEB_SEARCH_QUERY", "Agentic AI Google Workspace")


@pytest.mark.live_integration
def test_manual_1():
    # Web search verification
    # Skipped due to LLM infrastructure issues - requires LLM planning for search execution
    pytest.skip("LLM infrastructure issues - requires LLM planning for search execution")
