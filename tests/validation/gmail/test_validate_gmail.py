import pytest
from framework.task_runner import TaskRunner

@pytest.fixture
def runner():
    return TaskRunner()

@pytest.mark.live_integration
def test_gmail_search_validation(runner):
    """Test searching Gmail for specific keywords."""
    success = runner.execute_and_validate(
        task="search my inbox for 'security alert' and list the results",
        expected_texts=["Command succeeded"]
    )
    assert success

@pytest.mark.live_integration
def test_gmail_to_sheets_pipeline(runner):
    """Test full pipeline: search email -> save to sheet."""
    success = runner.execute_and_validate(
        task="Find an email about 'DecoverAI' and save the details to a new Google Sheet",
        expected_texts=["Created", "in Google Sheets", "Command succeeded"]
    )
    assert success
