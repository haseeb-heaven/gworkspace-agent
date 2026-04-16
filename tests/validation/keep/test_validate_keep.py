import pytest

from framework.task_runner import TaskRunner


@pytest.fixture
def runner():
    return TaskRunner()

@pytest.mark.live_integration
def test_keep_creation_and_list(runner):
    """Test creating a Keep note and listing it."""
    success = runner.execute_and_validate(
        task="Create a Google Keep note with title 'Validation Note' and body 'This is a validation test content.', then list my notes",
        expected_texts=["Validation Note", "completed"]
    )
    assert success
