import pytest
from framework.task_runner import TaskRunner

@pytest.fixture
def runner():
    return TaskRunner()

@pytest.mark.live_integration
def test_docs_creation_and_email(runner):
    success = runner.execute_and_validate(
        task="Create a doc called 'Release Notes', write 'Version 1.0 is out', and email the content to haseebmir.hm@gmail.com",
        expected_texts=["Command succeeded"]
    )
    assert success
