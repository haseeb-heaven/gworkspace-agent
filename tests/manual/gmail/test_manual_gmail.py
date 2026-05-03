import os

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task

TEST_GMAIL_SEARCH_QUERY = os.getenv("TEST_GMAIL_SEARCH_QUERY", "invoice")
TEST_GMAIL_URGENT_QUERY = os.getenv("TEST_GMAIL_URGENT_QUERY", "urgent")
TEST_GMAIL_LABEL_NAME = os.getenv("TEST_GMAIL_LABEL_NAME", "GWorkspaceAgent-Test")
TEST_GMAIL_LABEL_SENDER = os.getenv("TEST_GMAIL_LABEL_SENDER", "haseebmir.hm@gmail.com")
TEST_DOC_QUERY = os.getenv("TEST_DOC_QUERY", "CcaaS - AI Product")
TEST_DOC_KEYWORD = os.getenv("TEST_DOC_KEYWORD", "Shibuz")


@pytest.mark.live_integration
def test_manual_1():
    # Read verification
    run_task(
        "Search my inbox for the last 3 emails and log the output.",
        expected=["completed"],
        service="gmail",
        skip_verification=True,  # Read-only operation
    )


@pytest.mark.live_integration
def test_manual_2():
    # Search and Append verification
    run_task(
        f"Find an email about '{TEST_GMAIL_SEARCH_QUERY}' and save the snippet to a Google Sheet.",
        expected=["completed"],
        service="sheets",
        skip_verification=True  # May not have email
    )


@pytest.mark.live_integration
def test_manual_3():
    # Multi-step verification
    run_task(
        f"Search for '{TEST_GMAIL_URGENT_QUERY}', save the top result to a document, "
        "and reply back to the sender via email.",
        expected=["completed"],
        service="docs",
        skip_verification=True  # Complex multi-step
    )


@pytest.mark.live_integration
def test_manual_4():
    # Attachment and path leakage verification
    run_task(
        f"Search Google Drive for a document or binary file like {os.getenv('TEST_FILE_NAME')} or any recent file, "
        f"and send an email to {os.getenv('DEFAULT_RECIPIENT_EMAIL')} with the file attached. "
        "Verify the attachment is successfully added and no internal file paths are leaked in the email body.",
        expected=["completed"],
        unexpected=["[File: ", "D:\\", "C:\\"],
        service="gmail",
        skip_verification=True  # May not have file
    )


@pytest.mark.live_integration
def test_manual_5():
    # Search and Label verification
    run_task(
        f"Search Gmail for emails from '{TEST_GMAIL_LABEL_SENDER}' and apply a label called '{TEST_GMAIL_LABEL_NAME}'.",
        expected=["completed"],
        service="gmail",
        skip_verification=True  # May not have emails from sender
    )


@pytest.mark.live_integration
def test_manual_6():
    # Reply verification
    run_task(
        f"Find the most recent email from {os.getenv('DEFAULT_RECIPIENT_EMAIL')} and reply to it saying "
        "'This is an automated reply from GWorkspace Agent verification test.'.",
        expected=["completed"],
        service="gmail",
        skip_verification=True  # May not have email
    )


@pytest.mark.live_integration
def test_manual_7():
    # Document attachment verification
    run_task(
        f"Search for a document containing '{TEST_DOC_QUERY}' in its content, and send an email to "
        f"{os.getenv('DEFAULT_RECIPIENT_EMAIL')} attaching this document. "
        "The email subject should be 'Verification: AI Product Document' and the body should include a summary of the task.",
        expected=["completed"],
        service="gmail",
        skip_verification=True  # May not have document
    )


@pytest.mark.live_integration
def test_manual_8():
    # ID resolution and attachment verification
    run_task(
        f"Find a document that mentions '{TEST_DOC_KEYWORD}' and email it to "
        f"{os.getenv('DEFAULT_RECIPIENT_EMAIL')}. Ensure the file is attached correctly.",
        expected=["completed"],
        service="gmail",
        skip_verification=True  # May not have document
    )


@pytest.mark.live_integration
def test_manual_9():
    # Threaded conversation test
    run_task(
        "Search for emails from the last week and create a summary.",
        expected=["completed"],
        service="gmail",
        skip_verification=True  # Read-only operation
    )


@pytest.mark.live_integration
def test_manual_10():
    # Label management test
    run_task(
        "Search for unread emails and apply a label 'GWS-Unread-Test'.",
        expected=["completed"],
        service="gmail",
        skip_verification=True  # May not have unread emails
    )
