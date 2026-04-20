import os
import subprocess

EMAIL = "haseebmir.hm@gmail.com"

tasks = [
    f"Create 'temp_string_analysis.txt' in Temp folder with analysis summary, send content to {EMAIL}",
    f"Append Temp folder inventory status entry to 'temp_project_tasks' in Temp folder only, send updated snippet to {EMAIL}",
    f"Search Temp folder for .log or .tmp files older than 7 days, archive to 'temp_archived_logs.zip' in Temp folder only, send confirmation to {EMAIL}",
    f"Perform CRUD audit in Temp folder only: create 'temp_audit_test.txt', read, update, delete it, log to 'temp_crud_log.txt', send audit report to {EMAIL}",
    f"Create 'temp_operations_bundle_manifest.txt' in Temp folder listing 'temp_folder_index', 'temp_project_tasks', 'temp_inventory_store', send contents to {EMAIL}",
    f"Rename 'temp_folder_index' to 'temp_folder_index_v2' in Temp folder only, send updated reference to {EMAIL}",
    f"Delete 'temp_inventory_store_backup' from Temp folder only after confirming original exists, send deletion confirmation to {EMAIL}",
    f"Generate complete CRUD summary for Temp folder only covering all created, read, updated, renamed, archived, deleted files, send summary to {EMAIL}"
]

cli_path = "gws_cli.py"
python_exec = r"D:\henv\Scripts\python.exe"

from concurrent.futures import ThreadPoolExecutor, as_completed

EMAIL = "haseebmir.hm@gmail.com"

tasks = [
    f"Create 'temp_string_analysis.txt' in Temp folder with analysis summary, send content to {EMAIL}",
    f"Append Temp folder inventory status entry to 'temp_project_tasks' in Temp folder only, send updated snippet to {EMAIL}",
    f"Search Temp folder for .log or .tmp files older than 7 days, archive to 'temp_archived_logs.zip' in Temp folder only, send confirmation to {EMAIL}",
    f"Perform CRUD audit in Temp folder only: create 'temp_audit_test.txt', read, update, delete it, log to 'temp_crud_log.txt', send audit report to {EMAIL}",
    f"Create 'temp_operations_bundle_manifest.txt' in Temp folder listing 'temp_folder_index', 'temp_project_tasks', 'temp_inventory_store', send contents to {EMAIL}",
    f"Rename 'temp_folder_index' to 'temp_folder_index_v2' in Temp folder only, send updated reference to {EMAIL}",
    f"Delete 'temp_inventory_store_backup' from Temp folder only after confirming original exists, send deletion confirmation to {EMAIL}",
    f"Generate complete CRUD summary for Temp folder only covering all created, read, updated, renamed, archived, deleted files, send summary to {EMAIL}"
]

cli_path = "gws_cli.py"
python_exec = r"D:\henv\Scripts\python.exe"

def run_task(i, task):
    env = dict(os.environ)
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["OMP_NUM_THREADS"] = "1"

    with open(f"task_{i}_out.log", "w", encoding="utf-8") as f:
        f.write(f"Starting Task {i}...\n")
        f.flush()

        process = subprocess.run(
            [python_exec, cli_path, "--task", task],
            env=env,
            stdout=f,
            stderr=subprocess.STDOUT
        )
        f.write(f"\nTask {i} finished with exit code {process.returncode}\n")
    return i, process.returncode

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(run_task, i, task): i for i, task in enumerate(tasks, start=8)}
    for future in as_completed(futures):
        i, rc = future.result()
        print(f"Task {i} completed with return code {rc}")

print("All tasks completed.")

