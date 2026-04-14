import pytest
from framework.task_runner import TaskRunner

@pytest.fixture
def runner():
    return TaskRunner()

@pytest.mark.live_integration
def test_admin_and_email(runner):
    success = runner.execute_and_validate(
        task="List 5 users in my workspace and email the list to haseebmir.hm@gmail.com",
        expected_texts=["Command succeeded"]
    )
    assert success
