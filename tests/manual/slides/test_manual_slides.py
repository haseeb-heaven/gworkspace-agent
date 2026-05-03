"""Manual CRUD tests for Google Slides service."""

import os

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task

# Load test fixtures from environment variables
TEST_PRESENTATION_TITLE = os.getenv("TEST_PRESENTATION_TITLE", "GWS Agent Test Presentation")
TEST_UPDATE_SUFFIX = os.getenv("TEST_UPDATE_SUFFIX", "Updated")


@pytest.mark.live_integration
def test_manual_1():
    """Get presentation and email verification - Read operation."""
    run_task(
        "Fetch my latest presentation and email the link.",
        expected=["completed", "Sent"],
        service="slides",
    )


@pytest.mark.live_integration
def test_manual_2():
    """Create presentation verification - Create operation."""
    import time

    ts = int(time.time())
    title = f"{TEST_PRESENTATION_TITLE} {ts}"
    run_task(
        f"Create a new Google Slides presentation titled '{title}'.",
        expected=["completed", title],
        service="slides",
    )


@pytest.mark.live_integration
def test_manual_3():
    """List presentations verification - Read operation."""
    run_task(
        "List my Google Slides presentations.",
        expected=["completed", "presentation"],
        service="slides",
        skip_verification=True,  # Read-only operation
    )


@pytest.mark.live_integration
def test_manual_4():
    """Share presentation via email - Integration operation."""
    run_task(
        f"Find the presentation '{TEST_PRESENTATION_TITLE}' and email it to the default recipient.",
        expected=["completed", "email"],
        service="slides",
    )


@pytest.mark.live_integration
def test_manual_5():
    """Cross-service: Create presentation from document - Integration operation."""
    import time

    ts = int(time.time())
    title = f"{TEST_PRESENTATION_TITLE} from Doc {ts}"
    run_task(
        f"Search for a recent Google Doc and create a presentation '{title}' based on its content.",
        expected=["completed"],
        service="slides",
    )
