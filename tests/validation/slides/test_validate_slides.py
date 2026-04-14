import pytest
from framework.task_runner import TaskRunner

@pytest.fixture
def runner():
    return TaskRunner()

@pytest.mark.live_integration
def test_slides_fetch_and_email(runner):
    success = runner.execute_and_validate(
        task="Fetch my latest presentation and email the link to haseebmir.hm@gmail.com",
        expected_texts=["Command succeeded"]
    )
    assert success
