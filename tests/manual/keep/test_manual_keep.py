"""Manual CRUD tests for Google Keep service."""

import os

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task

# Load test fixtures from environment variables
TEST_NOTE_TITLE = os.getenv("TEST_NOTE_TITLE", "GWS Agent Test Note")
TEST_NOTE_BODY = os.getenv("TEST_NOTE_BODY", "Test note content from GWorkspace Agent")
TEST_UPDATE_SUFFIX = os.getenv("TEST_UPDATE_SUFFIX", "Updated")


@pytest.mark.live_integration
def test_manual_1():
    """Create note verification - Create operation."""
    run_task(
        f"Create a Keep note titled '{TEST_NOTE_TITLE}' with the body '{TEST_NOTE_BODY}'.",
        expected=["completed", TEST_NOTE_TITLE],
        service="keep",
        expected_fields={"title": TEST_NOTE_TITLE},
    )


@pytest.mark.live_integration
def test_manual_2():
    """List notes verification - Read operation."""
    run_task(
        "List my Keep notes.",
        expected=["completed", "note"],
        service="keep",
        skip_verification=True,  # Read-only operation
    )


@pytest.mark.live_integration
def test_manual_3():
    """Get note verification - Read operation."""
    run_task(
        f"Find and display the Keep note titled '{TEST_NOTE_TITLE}'.",
        expected=["completed", TEST_NOTE_TITLE],
        service="keep",
        skip_verification=True,  # May not exist
    )


@pytest.mark.live_integration
def test_manual_4():
    """Update note verification - Update operation."""
    updated_title = f"{TEST_NOTE_TITLE} {TEST_UPDATE_SUFFIX}"
    run_task(
        f"Update the Keep note '{TEST_NOTE_TITLE}' with the new title '{updated_title}'.",
        expected=["completed", updated_title],
        service="keep",
        skip_verification=True,  # May not find exact note
    )


@pytest.mark.live_integration
def test_manual_5():
    """Delete note verification - Delete operation."""
    run_task(
        f"Delete the Keep note titled '{TEST_NOTE_TITLE}'.",
        expected=["completed", "deleted"],
        service="keep",
        skip_verification=True,  # Destructive operation
    )


@pytest.mark.live_integration
def test_manual_6():
    """Full CRUD workflow - Create, Read, Update, Delete sequence."""
    import time

    ts = int(time.time())
    temp_title = f"{TEST_NOTE_TITLE} CRUD {ts}"
    temp_body = f"{TEST_NOTE_BODY} {ts}"

    run_task(
        f"Create a Keep note '{temp_title}' with body '{temp_body}', "
        f"then read it back, "
        f"update it to '{temp_title} {TEST_UPDATE_SUFFIX}', "
        f"and finally delete it.",
        expected=["completed"],
        service="keep",
        skip_verification=True,  # Complex multi-step workflow
    )
