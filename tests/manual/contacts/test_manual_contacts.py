"""Manual CRUD tests for Google Contacts service."""

import os

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task

# Load test fixtures from environment variables
TEST_CONTACT_NAME = os.getenv("TEST_CONTACT_NAME", "GWS Test Contact")
TEST_CONTACT_EMAIL = os.getenv("TEST_CONTACT_EMAIL", "gws-test@example.com")


@pytest.mark.live_integration
def test_manual_1():
    """List contacts and email verification - Read/Integration operation."""
    run_task(
        "List my top 5 contacts and email them to the default recipient.",
        expected=["completed", "email"],
        service="contacts",
        skip_verification=True  # Email may not be configured
    )


@pytest.mark.live_integration
def test_manual_2():
    """List directory users verification - Read operation."""
    run_task(
        "List 5 users in my workspace directory and email the list.",
        expected=["completed", "email"],
        service="contacts",
        skip_verification=True  # Email may not be configured
    )


@pytest.mark.live_integration
def test_manual_3():
    """Get person by resource name verification - Read operation."""
    run_task(
        "List my contacts and get detailed information for the first one.",
        expected=["completed"],
        service="contacts",
        skip_verification=True,  # Read-only operation
    )


@pytest.mark.live_integration
def test_manual_4():
    """Search contacts verification - Read operation."""
    run_task(
        f"Search my contacts for '{TEST_CONTACT_NAME}' and show the results.",
        expected=["completed"],
        service="contacts",
        skip_verification=True,  # Read-only operation
    )


@pytest.mark.live_integration
def test_manual_5():
    """Cross-service: Save contact to sheet - Integration operation."""
    run_task(
        "List my top 3 contacts and save their names and emails to a Google Sheet.",
        expected=["completed"],
        service="contacts",
        skip_verification=True  # Cross-service operation
    )


@pytest.mark.live_integration
def test_manual_6():
    """Export contacts to document - Integration operation."""
    run_task(
        "List my contacts and create a Google Doc with their information.",
        expected=["completed"],
        service="contacts",
        skip_verification=True  # Cross-service operation
    )
