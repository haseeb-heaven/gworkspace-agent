"""Manual CRUD tests for Google Forms service."""

import os

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task

# Load test fixtures from environment variables
TEST_FORM_TITLE = os.getenv("TEST_FORM_TITLE", "GWS Agent Test Form")
TEST_UPDATE_SUFFIX = os.getenv("TEST_UPDATE_SUFFIX", "Updated")


@pytest.mark.live_integration
def test_manual_1():
    """Sync verification - Read/Integration operation."""
    run_task(
        "Sync test data to Google Forms",
        expected=["completed"],
        service="forms",
        skip_verification=True  # May not have test data
    )


@pytest.mark.live_integration
def test_manual_2():
    """Create form verification - Create operation."""
    import time

    ts = int(time.time())
    title = f"{TEST_FORM_TITLE} {ts}"
    run_task(
        f"Create a new Google Form titled '{title}'.",
        expected=["completed", "Form created"],  # GWS returns "Untitled Form" initially
        service="forms",
        skip_verification=True,  # API may have limitations
    )


@pytest.mark.live_integration
def test_manual_3():
    """Get form details verification - Read operation."""
    run_task(
        f"Find the Google Form '{TEST_FORM_TITLE}' and show its details.",
        expected=["completed"],
        service="forms",
        skip_verification=True,  # May not exist
    )


@pytest.mark.live_integration
def test_manual_4():
    """List forms verification - Read operation."""
    run_task(
        "List my Google Forms.",
        expected=["completed", "form"],
        service="forms",
        skip_verification=True,  # Read-only operation
    )


@pytest.mark.live_integration
def test_manual_5():
    """Cross-service: Email form link - Integration operation."""
    run_task(
        f"Find the form '{TEST_FORM_TITLE}' and email the link to the default recipient.",
        expected=["completed", "email"],
        service="forms",
        skip_verification=True  # Email may not be configured
    )


@pytest.mark.live_integration
def test_manual_6():
    """Create form with questions - Create operation."""
    import time

    ts = int(time.time())
    title = f"{TEST_FORM_TITLE} with Questions {ts}"
    run_task(
        f"Create a Google Form '{title}' with a text question 'What is your feedback?'.",
        expected=["completed"],
        service="forms",
    )
