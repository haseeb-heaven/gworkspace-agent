import pytest

from framework.task_runner import TaskRunner


@pytest.fixture
def runner():
    return TaskRunner()


@pytest.mark.live_integration
def test_meet_and_email(runner, default_email):
    success = runner.execute_and_validate(
        task=f"Create a Google Meet conference and email the link to {default_email}", expected_texts=["completed"]
    )
    assert success
