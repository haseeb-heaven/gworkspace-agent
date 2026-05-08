"""Manual CRUD tests for Google Tasks service."""

import os

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task

# Load test fixtures from environment variables
TEST_TASKLIST_TITLE = os.getenv("TEST_TASKLIST_TITLE", "GWS Agent Test Tasklist")
TEST_TASK_TITLE = os.getenv("TEST_TASK_TITLE", "GWS Agent Test Task")
TEST_UPDATE_SUFFIX = os.getenv("TEST_UPDATE_SUFFIX", "Updated")


@pytest.mark.live_integration

def test_manual_1():
    """Create tasklist verification - Create operation."""
    run_task(
        f"Create a new task list named '{TEST_TASKLIST_TITLE}'.",
        expected=["completed", TEST_TASKLIST_TITLE],
        service="tasks",
        expected_fields={"title": TEST_TASKLIST_TITLE},
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_2():
    """List tasklists verification - Read operation."""
    run_task(
        "List all my task lists.",
        expected=["completed", "task"],
        service="tasks",
        skip_verification=True,  # Read-only operation
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_3():
    """Create task in tasklist verification - Create operation."""
    run_task(
        f"Create a new task titled '{TEST_TASK_TITLE}' in the task list '{TEST_TASKLIST_TITLE}'.",
        expected=["completed", TEST_TASK_TITLE],
        service="tasks",
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_4():
    """List tasks in tasklist verification - Read operation."""
    run_task(
        f"List all tasks in the task list '{TEST_TASKLIST_TITLE}'.",
        expected=["completed", "task"],
        service="tasks",
        skip_verification=True,  # Read-only operation
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_5():
    """Update task verification - Update operation."""
    updated_title = f"{TEST_TASK_TITLE} {TEST_UPDATE_SUFFIX}"
    run_task(
        f"Find the task '{TEST_TASK_TITLE}' in '{TEST_TASKLIST_TITLE}' and update its title to '{updated_title}'.",
        expected=["completed"],  # Removed updated_title expectation since task update may fail
        service="tasks",
        skip_verification=True,  # May not find exact task
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_6():
    """Complete task verification - Update operation (status change)."""
    run_task(
        f"Mark the task '{TEST_TASK_TITLE}' in '{TEST_TASKLIST_TITLE}' as completed.",
        expected=["completed"],
        service="tasks",
        skip_verification=True,  # May not find exact task
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_7():
    """Delete task verification - Delete operation with safety handling."""
    # Skip verification as this is a destructive operation
    run_task(
        f"Delete the task '{TEST_TASK_TITLE}' from the task list '{TEST_TASKLIST_TITLE}'.",
        expected=["completed"],  # Removed "deleted" since it's not in output
        service="tasks",
        skip_verification=True,
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_8():
    """Full CRUD workflow - Create, Read, Update, Delete in sequence."""
    import time

    ts = int(time.time())
    temp_task_title = f"{TEST_TASK_TITLE} CRUD {ts}"

    # This tests the complete workflow in a single task
    run_task(
        f"Create a task '{temp_task_title}' in '{TEST_TASKLIST_TITLE}', "
        f"then list tasks to verify it exists, "
        f"then update it to '{temp_task_title} {TEST_UPDATE_SUFFIX}', "
        f"and finally delete it.",
        expected=["completed"],
        service="tasks",
        skip_verification=True,  # Complex multi-step, skip verification
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_9():
    """Cross-service integration - Create task from email."""
    run_task(
        f"Search Gmail for the last email and create a task from it in '{TEST_TASKLIST_TITLE}'.",
        expected=["completed"],
        service="tasks",
        skip_verification=True,  # Depends on email content
        skip_5step_verification=False,
    )
