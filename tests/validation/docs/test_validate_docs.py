import pytest

from framework.task_runner import TaskRunner


@pytest.fixture
def runner():
    return TaskRunner()

@pytest.mark.live_integration
def test_docs_creation_and_email(runner, default_email):
    success = runner.execute_and_validate(
        task=f"Create a doc called 'Release Notes', write 'Version 1.0 is out', and email the content to {default_email}",
        expected_texts=["completed"]
    )
    assert success
