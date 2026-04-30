import subprocess
import os
from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest


def run_task(task_string):
    import os

    load_dotenv()  # Ensure .env is loaded inside helper
    email = os.getenv("DEFAULT_RECIPIENT_EMAIL", os.getenv("DEFAULT_RECIPIENT_EMAIL"))
    task_string = task_string.replace(os.getenv("DEFAULT_RECIPIENT_EMAIL"), email)
    import os

    print(f'Running manual task: python gws_cli.py --task "{task_string}"')
    import os

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        ["python", "gws_cli.py", "--task", task_string], capture_output=True, text=True, encoding="utf-8", env=env
    )
    if "missing field `client_id`" in result.stderr or "Authentication failed" in result.stderr:
        pytest.skip("Auth not configured")
    assert result.returncode == 0, f"Task failed: {result.stderr}"


@pytest.mark.live_integration
def test_manual_1():
    run_task("Search my inbox for the last 3 emails and log the output.")


@pytest.mark.live_integration
def test_manual_2():
    run_task("Find an email about 'invoice' and save the snippet to a Google Sheet.")


@pytest.mark.live_integration
def test_manual_3():
    run_task(
        "Search for 'urgent', save the top result to a document, and reply back to the sender via email using user@example.com."
    )


@pytest.mark.live_integration
def test_manual_4():
    run_task(
        f"Search Google Drive for a document or binary file like {os.getenv('TEST_FILE_NAME')} or any recent file, and send an email to {os.getenv('DEFAULT_RECIPIENT_EMAIL')} with the file attached. Verify the attachment is successfully added and no internal file paths are leaked in the email body."
    )


@pytest.mark.live_integration
def test_manual_5():
    run_task(
        "Search Gmail for emails from 'haseebmir.hm@gmail.com' and apply a label called 'GWorkspaceAgent-Test'."
    )


@pytest.mark.live_integration
def test_manual_6():
    run_task(
        f"Find the most recent email from {os.getenv('DEFAULT_RECIPIENT_EMAIL')} and reply to it saying 'This is an automated reply from GWorkspace Agent verification test.'."
    )


@pytest.mark.live_integration
def test_manual_7():
    run_task(
        f"Search for a document containing 'CcaaS - AI Product' in its content, and send an email to {os.getenv('DEFAULT_RECIPIENT_EMAIL')} attaching this document. The email subject should be 'Verification: AI Product Document' and the body should include a summary of the task."
    )


@pytest.mark.live_integration
def test_manual_8():
    run_task(
        f"Find a document that mentions 'Shibuz' and email it to {os.getenv('DEFAULT_RECIPIENT_EMAIL')}. Ensure the file is attached correctly."
    )
