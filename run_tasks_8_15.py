import subprocess
import json
import os
import time

gws_exe = "D:\\Code\\gworkspace-agent\\gws.exe"
cli_path = "D:\\Code\\gworkspace-agent\\gws_cli.py"
folder_id = "1cZwScEjsqAWMepI-gPuXkg5_35AVa_pJ"
recipient = "haseebmir.hm@gmail.com"

def run_cli(task):
    print(f"Running task: {task[:100]}...")
    res = subprocess.run(["python", cli_path, "--task", task], capture_output=True, text=True, encoding='utf-8', errors='replace')
    return res.stdout

# Task 8: Create temp_string_analysis.txt
print("--- Task 8 ---")
t8 = f"Create a file named 'temp_string_analysis.txt' in folder '{folder_id}' with content 'Analysis summary: All temp files processed.' then send email to {recipient}"
print(run_cli(t8))

# Task 9: Append to temp_project_tasks
print("--- Task 9 ---")
t9 = f"In folder '{folder_id}', find 'temp_project_tasks' (Sheet) and append a row: 'Inventory Status', 'Verified' then send email to {recipient}"
print(run_cli(t9))

# Task 10: Archive .log/.tmp (Simulate by listing and reporting)
print("--- Task 10 ---")
t10 = f"Search folder '{folder_id}' for .log or .tmp files, and send a status report to {recipient} about archiving them."
print(run_cli(t10))

# Task 11: CRUD Audit
print("--- Task 11 ---")
t11 = f"In folder '{folder_id}', perform CRUD audit: create 'temp_audit_test.txt', read it, update it with 'v2', then delete it. Log to 'temp_crud_log.txt' and email {recipient}"
print(run_cli(t11))

# Task 12: Bundle Manifest
print("--- Task 12 ---")
t12 = f"In folder '{folder_id}', create 'temp_operations_bundle_manifest.txt' listing the main files, and email {recipient}"
print(run_cli(t12))

# Task 13: Rename folder index
print("--- Task 13 ---")
t13 = f"In folder '{folder_id}', find 'temp_folder_index' and rename it to 'temp_folder_index_v2', then email {recipient}"
print(run_cli(t13))

# Task 14: Delete backup
print("--- Task 14 ---")
t14 = f"In folder '{folder_id}', delete 'temp_inventory_store_backup' and email {recipient}"
print(run_cli(t14))

# Task 15: CRUD Summary
print("--- Task 15 ---")
t15 = f"Generate a complete CRUD summary of all actions in folder '{folder_id}' based on 'temp_crud_log.txt' and email to {recipient}"
print(run_cli(t15))
