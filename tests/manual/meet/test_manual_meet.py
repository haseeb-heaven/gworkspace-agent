"""Manual CRUD tests for Google Meet service."""

import os

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task

# Load test fixtures from environment variables
TEST_MEETING_NAME = os.getenv("TEST_MEETING_NAME", "GWS Agent Test Meeting")


@pytest.mark.live_integration

def test_manual_1():
    """Create meeting and email verification - Create operation."""
    run_task(
        f"Create a Google Meet conference named '{TEST_MEETING_NAME}' and email the link.",
        expected=["completed", "Meet", "Sent"],
        service="meet",
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_2():
    """List conferences verification - Read operation."""
    run_task(
        "List my Google Meet conferences.",
        expected=["completed", "conference", "meeting"],
        service="meet",
        skip_verification=True,  # Read-only operation
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_3():
    """Create standalone meeting verification - Create operation."""
    import time

    ts = int(time.time())
    meeting_name = f"{TEST_MEETING_NAME} {ts}"
    run_task(
        f"Create a new Google Meet space named '{meeting_name}'.",
        expected=["completed", "meeting"],
        service="meet",
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_4():
    """Schedule meeting with calendar event - Create/Integration operation."""
    import time

    ts = int(time.time())
    run_task(
        f"Create a calendar event for tomorrow at 2pm with a Google Meet link for '{TEST_MEETING_NAME} {ts}'.",
        expected=["completed", "meeting", "event"],
        service="meet",
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_5():
    """Cross-service: Share meeting via chat - Integration operation."""
    run_task(
        f"Create a Google Meet conference named '{TEST_MEETING_NAME}' and share the link in my primary chat space.",
        expected=["completed"],
        service="meet",
        skip_verification=True,  # Depends on chat space availability
        skip_5step_verification=False,
    )
