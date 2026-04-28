import pytest

from framework.task_runner import TaskRunner


@pytest.fixture
def runner():
    return TaskRunner()


@pytest.mark.live_integration
def test_admin_and_email(runner, default_email):
    success = runner.execute_and_validate(
        task=f"List 5 users in my workspace and email the list to {default_email}", expected_texts=["completed"]
    )
    assert success
