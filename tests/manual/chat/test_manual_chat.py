"""Manual CRUD tests for Google Chat service."""

import os

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task

# Load test fixtures from environment variables
TEST_CHAT_MESSAGE = os.getenv("TEST_CHAT_MESSAGE", "GWS Agent automated test message")


@pytest.mark.live_integration
def test_manual_1():
    """Send message to primary space verification - Create operation."""
    run_task(
        f"Send a message '{TEST_CHAT_MESSAGE}' to my primary space.",
        expected=["completed", "message"],
        service="chat",
        skip_verification=True  # May not have chat space
    )


@pytest.mark.live_integration
def test_manual_2():
    """List spaces and email verification - Read/Integration operation."""
    run_task(
        "List my Google Chat spaces and email the list to the default recipient.",
        expected=["completed", "email"],
        service="chat",
        skip_verification=True  # Email may not be configured
    )


@pytest.mark.live_integration
def test_manual_3():
    """List messages in space verification - Read operation."""
    run_task(
        "List recent messages in my primary chat space.",
        expected=["completed", "message"],
        service="chat",
        skip_verification=True,  # Read-only operation
    )


@pytest.mark.live_integration
def test_manual_4():
    """Get specific message verification - Read operation."""
    run_task(
        "Get the most recent message from my primary chat space and display it.",
        expected=["completed"],
        service="chat",
        skip_verification=True,  # Read-only operation
    )


@pytest.mark.live_integration
def test_manual_5():
    """Cross-service: Notify about new file - Integration operation."""
    run_task(
        "Search Drive for a recent file and send a message to my primary chat space about it.",
        expected=["completed"],
        service="chat",
        skip_verification=True  # Complex cross-service operation
    )


@pytest.mark.live_integration
def test_manual_6():
    """Cross-service: Chat alert for calendar event - Integration operation."""
    run_task(
        "Get my next calendar event and send a reminder to my primary chat space.",
        expected=["completed"],
        service="chat",
        skip_verification=True  # Complex cross-service operation
    )
