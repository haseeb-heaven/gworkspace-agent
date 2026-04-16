import pytest
from framework.task_runner import TaskRunner

@pytest.fixture
def runner():
    return TaskRunner()

@pytest.mark.live_integration
def test_calendar_creation(runner, default_email):
    success = runner.execute_and_validate(
        task=f"Create a calendar event called 'Testing Framework' for tomorrow, and email the details to {default_email}",
        expected_texts=["completed"]
    )
    assert success
