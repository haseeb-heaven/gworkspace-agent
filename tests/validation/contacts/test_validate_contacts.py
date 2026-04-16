import pytest

from framework.task_runner import TaskRunner


@pytest.fixture
def runner():
    return TaskRunner()

@pytest.mark.live_integration
def test_contacts_and_email(runner, default_email):
    success = runner.execute_and_validate(
        task=f"List my top 5 contacts and email them to {default_email}",
        expected_texts=["completed"]
    )
    assert success
