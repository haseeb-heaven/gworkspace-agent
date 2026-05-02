
from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task


@pytest.mark.live_integration
def test_manual_1():
    # Read and email verification
    run_task("Fetch my latest presentation and email the link.", expected=["Result", "Sent"], service="slides")
@pytest.mark.live_integration
def test_manual_2():
    # Create verification
    # Skipped due to LLM infrastructure issues - verification engine fails with missing ID error
    pytest.skip("LLM infrastructure issues - verification engine fails with missing ID error")
