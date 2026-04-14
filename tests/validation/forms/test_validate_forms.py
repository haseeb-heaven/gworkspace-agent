import pytest
from framework.task_runner import TaskRunner

@pytest.fixture
def runner():
    return TaskRunner()

@pytest.mark.live_integration
def test_forms_validation(runner):
    success = runner.execute_and_validate(
        task="Sync test data to Google Forms",
        expected_texts=["Command succeeded"]
    )
    assert success
