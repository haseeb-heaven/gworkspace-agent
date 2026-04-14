import pytest
from framework.task_runner import TaskRunner

@pytest.fixture
def runner():
    return TaskRunner()

@pytest.mark.live_integration
def test_contacts_and_email(runner):
    success = runner.execute_and_validate(
        task="List my top 5 contacts and email them to haseebmir.hm@gmail.com",
        expected_texts=["Command succeeded"]
    )
    assert success
