
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
    run_task("Create a new Google Slides presentation titled 'Project Proposal'.", expected=["Created", "Project Proposal"], service="slides", expected_fields={"title": "Project Proposal"})
