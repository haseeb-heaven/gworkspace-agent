import json
import pytest
import os
from .base import get_executor, create_task

def test_drive_validation():
    # Set keyring backend to file to avoid Secure Storage errors in headless/CLI environments
    os.environ["GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND"] = "file"
    
    executor = get_executor()
    context = {}
    
    # 1. Create Folder
    folder_name = "Systematic Validation Folder"
    task = create_task('drive', 'create_folder', {'folder_name': folder_name})
    res = executor.execute_single_task(task, context)
    
    # We expect a failure if not authenticated, which helps us verify the tool is actually running
    assert res.success, f"Drive validation failed: {res.stderr}"
    
    data = json.loads(res.stdout)
    folder_id = data["id"]
    print(f"Folder created: {folder_id}")
    
    # 2. Delete Folder (cleanup)
    task = create_task('drive', 'delete_file', {'file_id': folder_id})
    res = executor.execute_single_task(task, context)
    assert res.success, f"Failed to delete folder: {res.stderr}"
