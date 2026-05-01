import os

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task


@pytest.mark.live_integration
def test_manual_1():
    # Read verification
    run_task("Search my inbox for the last 3 emails and log the output.", expected=["completed"], service="gmail")


@pytest.mark.live_integration
def test_manual_2():
    # Search and Append verification
    run_task("Find an email about 'invoice' and save the snippet to a Google Sheet.", expected=["completed"], service="sheets")


@pytest.mark.live_integration
def test_manual_3():
    # Multi-step verification
    run_task(
        "Search for 'urgent', save the top result to a document, and reply back to the sender via email.",
        expected=["completed"],
        service="docs"
    )


@pytest.mark.live_integration
def test_manual_4():
    # Attachment and path leakage verification
    run_task(
        f"Search Google Drive for a document or binary file like {os.getenv('TEST_FILE_NAME')} or any recent file, and send an email to {os.getenv('DEFAULT_RECIPIENT_EMAIL')} with the file attached. Verify the attachment is successfully added and no internal file paths are leaked in the email body.",
        expected=["completed"],
        unexpected=["[File: ", "D:\\", "C:\\"],
        service="gmail"
    )


@pytest.mark.live_integration
def test_manual_5():
    # Search and Label verification
    run_task(
        "Search Gmail for emails from 'haseebmir.hm@gmail.com' and apply a label called 'GWorkspaceAgent-Test'.",
        expected=["completed"],
        service="gmail"
    )


@pytest.mark.live_integration
def test_manual_6():
    # Reply verification
    run_task(
        f"Find the most recent email from {os.getenv('DEFAULT_RECIPIENT_EMAIL')} and reply to it saying 'This is an automated reply from GWorkspace Agent verification test.'.",
        expected=["completed"],
        service="gmail"
    )


@pytest.mark.live_integration
def test_manual_7():
    # Document attachment verification
    run_task(
        f"Search for a document containing 'CcaaS - AI Product' in its content, and send an email to {os.getenv('DEFAULT_RECIPIENT_EMAIL')} attaching this document. The email subject should be 'Verification: AI Product Document' and the body should include a summary of the task.",
        expected=["completed"],
        service="gmail"
    )


@pytest.mark.live_integration
def test_manual_8():
    # ID resolution and attachment verification
    run_task(
        f"Find a document that mentions 'Shibuz' and email it to {os.getenv('DEFAULT_RECIPIENT_EMAIL')}. Ensure the file is attached correctly.",
        expected=["completed"],
        service="gmail"
    )
