import pytest
from framework.task_runner import TaskRunner

@pytest.fixture
def runner():
    return TaskRunner()

@pytest.mark.live_integration
def test_search_and_email(runner):
    success = runner.execute_and_validate(
        task="Web search for 'Agentic AI Google Workspace' and email the top results to haseebmir.hm@gmail.com",
        expected_texts=["Command succeeded"]
    )
    assert success
