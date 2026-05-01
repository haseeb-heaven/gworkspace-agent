
from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task


@pytest.mark.live_integration
def test_manual_1():
    # Web search verification
    run_task("Web search for 'Agentic AI Google Workspace' and email the top results.", expected=["Result", "Sent", "Search"], service="search")
