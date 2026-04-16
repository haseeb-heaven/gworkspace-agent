import json
import os

from .base import create_task, get_executor


def test_drive_validation():
    # Set keyring backend to file to avoid Secure Storage errors in headless/CLI environments
    os.environ["GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND"] = "file"

    executor = get_executor()
    if not executor.runner.validate_binary():
        import pytest
        pytest.skip(f"gws binary not found at {executor.runner.gws_binary_path}, skipping validation test.")
    context = {}

    # 1. Create Folder
    folder_name = "Systematic Validation Folder"
    task = create_task('drive', 'create_folder', {'folder_name': folder_name})
    res = executor.execute_single_task(task, context)

    # We expect a failure if not authenticated, which helps us verify the tool is actually running
    is_auth_error = "authError" in str(res.stdout) or "Access denied" in str(res.stderr)
    assert res.success or is_auth_error, f"Drive validation failed: {res.stderr}"

    if not res.success:
        import pytest
        pytest.skip("Drive tool is working but unauthenticated. Skipping further validation.")

    assert res.stdout and res.success, f"Drive validation failed: {res.stderr}"

    data = json.loads(res.stdout)
    folder_id = data["id"]
    print(f"Folder created: {folder_id}")

    # 2. Delete Folder (cleanup)
    task = create_task('drive', 'delete_file', {'file_id': folder_id})
    res = executor.execute_single_task(task, context)
    assert res.success, f"Failed to delete folder: {res.stderr}"
