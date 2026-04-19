import pytest

from framework.task_runner import TaskRunner


@pytest.fixture
def runner():
    return TaskRunner()

@pytest.mark.live_integration
def test_sheets_creation_and_append(runner):
    success = runner.execute_and_validate(
        task="Create a Google Sheet named 'Auto Validation Test' and append ['Test', 'Success'] to it.",
        expected_texts=["Created", "in Google Sheets"] # Assuming output formatter prints this
    )
    assert success

@pytest.mark.live_integration
def test_sheets_to_email(runner, default_email):
    success = runner.execute_and_validate(
        task=f"Read data from 'Auto Validation Test' Sheet and send it in an email to {default_email}",
        expected_texts=["completed"]
    )
    assert success
