import pytest
from framework.task_runner import TaskRunner

@pytest.fixture
def runner():
    return TaskRunner()

@pytest.mark.live_integration
def test_calendar_creation(runner):
    success = runner.execute_and_validate(
        task="Create a calendar event called 'Testing Framework' for tomorrow, and email the details to haseebmir.hm@gmail.com",
        expected_texts=["Command succeeded"]
    )
    assert success
