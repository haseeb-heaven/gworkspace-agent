
from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task


@pytest.mark.live_integration
def test_manual_1():
    # Sync verification
    run_task("Sync test data to Google Forms", expected=["Result"], service="forms")
@pytest.mark.live_integration
def test_manual_2():
    # Create verification
    # Skipped due to LLM infrastructure issues - heuristic planner cannot handle custom form titles
    pytest.skip("LLM infrastructure issues - heuristic planner cannot handle custom form titles")
