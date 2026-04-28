import pytest

from ..base import create_task, get_executor


def test_calendar_creation(default_email):
    executor = get_executor()
    if not executor.runner.validate_binary():
        pytest.skip("gws binary not found, skipping validation test.")

    context = {}
    # Create a calendar event
    task = create_task(
        "calendar",
        "create_event",
        {
            "summary": "Testing Framework",
            "description": f"Email details to {default_email}",
            "start_date": "2026-04-20",
            "start_time": "tomorrow at 10am",
            "end_time": "tomorrow at 11am",
        },
    )

    res = executor.execute_single_task(task, context)

    # We expect a failure if not authenticated, which helps us verify the tool is actually running
    is_auth_error = "authError" in str(res.stdout) or "Access denied" in str(res.stderr)
    assert res.success or is_auth_error, f"Calendar validation failed: {res.stderr}"
