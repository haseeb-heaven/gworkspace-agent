"""Manual CRUD tests for Google Calendar service."""

import os

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task

# Load test fixtures from environment variables
TEST_EVENT_NAME = os.getenv("TEST_EVENT_NAME", "GWS Agent Test Event")
TEST_EVENT_DESCRIPTION = os.getenv("TEST_EVENT_DESCRIPTION", "Test event created by GWorkspace Agent")
TEST_UPDATE_SUFFIX = os.getenv("TEST_UPDATE_SUFFIX", "Updated")


@pytest.mark.live_integration

def test_manual_1():
    """List events verification - Read operation."""
    run_task(
        "List my upcoming calendar events for the next week.",
        expected=["completed", "event"],
        service="calendar",
        skip_verification=True,  # Read-only operation
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_2():
    """Create event verification - Create operation."""
    import time

    ts = int(time.time())
    event_name = f"{TEST_EVENT_NAME} {ts}"
    run_task(
        f"Create a calendar event for tomorrow at 10am with the subject '{event_name}' and description '{TEST_EVENT_DESCRIPTION}'.",
        expected=["completed", event_name],
        service="calendar",
        expected_fields={"summary": event_name},
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_3():
    """Get event verification - Read operation."""
    run_task(
        f"Find the calendar event '{TEST_EVENT_NAME}' and show its details.",
        expected=["completed"],
        service="calendar",
        skip_verification=True,  # May not exist
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_4():
    """Update event verification - Update operation."""
    import time

    ts = int(time.time())
    original_name = f"{TEST_EVENT_NAME} {ts}"
    updated_name = f"{original_name} {TEST_UPDATE_SUFFIX}"
    run_task(
        f"Create a calendar event '{original_name}', then update it to '{updated_name}' with a new description.",
        expected=["completed", updated_name],
        service="calendar",
        skip_verification=True,  # May not find exact event
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_5():
    """Delete event verification - Delete operation."""
    run_task(
        f"Find and delete the calendar event titled '{TEST_EVENT_NAME}'.",
        expected=["completed"],
        service="calendar",
        skip_verification=True,  # Destructive operation
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_6():
    """Full CRUD workflow - Create, Read, Update, Delete sequence."""
    import time

    ts = int(time.time())
    temp_name = f"{TEST_EVENT_NAME} CRUD {ts}"
    updated_name = f"{temp_name} {TEST_UPDATE_SUFFIX}"

    run_task(
        f"Create a calendar event '{temp_name}' for tomorrow at 3pm, "
        f"then get its details, "
        f"update it to '{updated_name}', "
        f"and finally delete it.",
        expected=["completed"],
        service="calendar",
        skip_verification=True,  # Complex multi-step, skip verification
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_7():
    """Cross-service: Create event with Meet link - Integration operation."""
    import time

    ts = int(time.time())
    event_name = f"{TEST_EVENT_NAME} with Meet {ts}"
    run_task(
        f"Create a calendar event '{event_name}' for tomorrow at 4pm with a Google Meet link included.",
        expected=["completed", "meeting", "event"],
        service="calendar",
        skip_verification=True,  # Cross-service operation
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_8():
    """Email event details - Integration operation."""
    run_task(
        "Find the next calendar event and email the details to the default recipient.",
        expected=["completed", "email"],
        service="calendar",
        skip_verification=True,  # Email may not be configured
        skip_5step_verification=False,
    )
