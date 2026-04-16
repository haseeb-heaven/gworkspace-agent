import pytest

from framework.task_runner import TaskRunner


@pytest.fixture
def runner():
    return TaskRunner()

@pytest.mark.live_integration
def test_code_execution_validation(runner, default_email):
    success = runner.execute_and_validate(
        task=f"Write a python script to calculate the first 10 fibonacci numbers, execute it, and email the results to {default_email}",
        expected_texts=["completed"]
    )
    assert success
