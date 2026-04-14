import pytest
from framework.task_runner import TaskRunner

@pytest.fixture
def runner():
    return TaskRunner()

@pytest.mark.live_integration
def test_code_execution_validation(runner):
    success = runner.execute_and_validate(
        task="Write a python script to calculate the first 10 fibonacci numbers, execute it, and email the results to haseebmir.hm@gmail.com",
        expected_texts=["Command succeeded"]
    )
    assert success
