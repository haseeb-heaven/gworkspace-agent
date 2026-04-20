import subprocess
import json
import os

gws_exe = "D:\\Code\\gworkspace-agent\\gws.exe"
source_id = "1tgwkywX85BQXluzUFizMOrxdGscUjlrr_2TSogN92tI"
folder_id = "1cZwScEjsqAWMepI-gPuXkg5_35AVa_pJ"
backup_name = "temp_inventory_store_backup"

# Task 4: Backup
copy_params = {"fileId": source_id}
copy_json = {"name": backup_name, "parents": [folder_id]}

print(f"--- Executing Task 4: Backup ---")
cmd_copy = [gws_exe, "drive", "files", "copy", "--params", json.dumps(copy_params), "--json", json.dumps(copy_json)]
res_copy = subprocess.run(cmd_copy, capture_output=True, text=True)
print("Copy STDOUT:", res_copy.stdout)

# Task 5: Read and Email
print(f"--- Executing Task 5: Read and Email ---")
# 1. Read (Export as CSV since it's a Sheet)
export_params = {"fileId": source_id, "mimeType": "text/csv"}
export_path = "scratch/temp_inventory.csv"
os.makedirs("scratch", exist_ok=True)
cmd_export = [gws_exe, "drive", "files", "export", "--params", json.dumps(export_params), "-o", export_path]
res_export = subprocess.run(cmd_export, capture_output=True, text=True)
print("Export Result:", res_export.returncode)

if os.path.exists(export_path):
    with open(export_path, "r") as f:
        content = f.read()
    
    # 2. Email using gws_cli.py to trigger VerificationEngine
    import base64
    cli_path = "D:\\Code\\gworkspace-agent\\gws_cli.py"
    email_task = f"Send email to haseebmir.hm@gmail.com with subject 'Inventory Store Entries' and body 'Here are the entries from temp_inventory_store:\n\n{content[:1000]}'"
    cmd_email = ["python", cli_path, "--task", email_task]
    res_email = subprocess.run(cmd_email, capture_output=True, text=True)
    print("Email CLI STDOUT:", res_email.stdout)
else:
    print("Export failed, cannot send email.")
