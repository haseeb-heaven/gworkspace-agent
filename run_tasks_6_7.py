import subprocess
import json
import os

gws_exe = "D:\\Code\\gworkspace-agent\\gws.exe"
folder_id = "1cZwScEjsqAWMepI-gPuXkg5_35AVa_pJ"

# Task 6: List Temp folder and save to file
print(f"--- Executing Task 6: Inventory File ---")
list_params = {"q": f"'{folder_id}' in parents", "fields": "files(id, name, mimeType)"}
res_list = subprocess.run([gws_exe, "drive", "files", "list", "--params", json.dumps(list_params)], capture_output=True, text=True)
files_data = json.loads(res_list.stdout).get("files", [])

inventory_lines = [f"{f['name']} ({f['mimeType']}) - {f['id']}" for f in files_data]
inventory_text = "\n".join(inventory_lines)
inventory_filename = "temp_current_inventory_2026-04-19.txt"

# Create file in Drive
create_params = {"fields": "id,name"}
create_json = {
    "name": inventory_filename,
    "mimeType": "text/plain",
    "parents": [folder_id]
}
# Since gws files create doesn't support content directly in one go easily via CLI without --upload, 
# I will use gws_cli.py for this to ensure content is handled.
cli_path = "D:\\Code\\gworkspace-agent\\gws_cli.py"
create_task = f"Create a text file named '{inventory_filename}' in the folder with ID '{folder_id}' with the following content:\n\n{inventory_text}\n\nThen send email to haseebmir.hm@gmail.com confirming it."
res_create = subprocess.run(["python", cli_path, "--task", create_task], capture_output=True, text=True)
print("Task 6 Result:", res_create.stdout)

# Task 7: Search for duplicates or empty files, delete, log
print(f"--- Executing Task 7: Cleanup ---")
# Strategy: Find files with same name
seen_names = {}
to_delete = []
for f in files_data:
    name = f['name']
    if name in seen_names:
        to_delete.append(f['id'])
    else:
        seen_names[name] = f['id']

print(f"Found {len(to_delete)} duplicates to delete.")

for fid in to_delete:
    del_res = subprocess.run([gws_exe, "drive", "files", "delete", "--params", json.dumps({"fileId": fid})], capture_output=True, text=True)
    print(f"Deleted {fid}: {del_res.returncode}")

# Log to temp_crud_log.txt (Find it first or create it)
log_task = f"Append 'Cleanup action: deleted {len(to_delete)} duplicate files' to 'temp_crud_log.txt' in folder ID '{folder_id}'. If it doesn't exist, create it. Then send cleanup report to haseebmir.hm@gmail.com."
res_log = subprocess.run(["python", cli_path, "--task", log_task], capture_output=True, text=True)
print("Task 7 Result:", res_log.stdout)
