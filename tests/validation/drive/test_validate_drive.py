import pytest
from framework.task_runner import TaskRunner

@pytest.fixture
def runner():
    return TaskRunner()

@pytest.mark.live_integration
def test_drive_folder_creation(runner):
    """Test creating a folder in Drive."""
    success = runner.execute_and_validate(
        task="Create a folder named 'AutoTest Folder' in Google Drive",
        expected_texts=["completed"]
    )
    assert success

@pytest.mark.live_integration
def test_drive_list_files(runner):
    """Test listing files."""
    success = runner.execute_and_validate(
        task="List 2 files from my Google Drive",
        expected_texts=["completed"]
    )
    assert success
