import pytest

from ..base import create_task, get_executor


@pytest.mark.live_integration
def test_keep_creation_and_list():
    """Test creating a Keep note and listing it."""
    executor = get_executor()
    if not executor.runner.validate_binary():
        pytest.skip(f"gws binary not found at {executor.runner.gws_binary_path}, skipping validation test.")

    context = {}

    # 1. Create Note
    title = "Validation Note"
    body = "This is a validation test content."
    task = create_task("keep", "create_note", {"title": title, "body": body})
    res = executor.execute_single_task(task, context)

    # Handle auth issues gracefully
    is_auth_error = any(
        msg in str(res.stdout) + str(res.stderr)
        for msg in ["authError", "Access denied", "unauthorized", "insufficient authentication scopes"]
    )
    if not res.success and is_auth_error:
        pytest.skip("Keep tool is working but unauthenticated or unauthorized. Skipping further validation.")

    assert res.success, f"Keep creation failed: {res.stderr}"

    # 2. List Notes
    task = create_task("keep", "list_notes", {})
    res = executor.execute_single_task(task, context)
    assert res.success, f"Keep list failed: {res.stderr}"
    assert title in res.stdout, f"Created note title '{title}' not found in list output: {res.stdout}"
