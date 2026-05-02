
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
    run_task(
        "Create a Google Form titled 'User Feedback Survey'.",
        expected=["Command succeeded", "User Feedback Survey"],
        service="forms",
        expected_fields={"info": {"title": "User Feedback Survey"}},
    )
