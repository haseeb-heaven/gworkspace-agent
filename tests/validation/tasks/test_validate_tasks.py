import pytest
from framework.task_runner import TaskRunner

@pytest.fixture
def runner():
    return TaskRunner()

@pytest.mark.live_integration
def test_tasks_crud(runner, default_email):
    # We use a unique title to avoid collisions
    import time
    task_title = f"Test Task {int(time.time())}"
    
    # 1. Create a task
    success = runner.execute_and_validate(
        task=f"Create a new task titled '{task_title}' in my todo list",
        expected_texts=["created", task_title]
    )
    assert success
    
    # 2. List tasks
    success = runner.execute_and_validate(
        task="List all my tasks and check if the one I just created exists",
        expected_texts=[task_title]
    )
    assert success
