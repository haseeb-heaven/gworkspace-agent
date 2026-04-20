import subprocess
import json
import os

gws_exe = "D:\\Code\\gworkspace-agent\\gws.exe"
folder_id = "1cZwScEjsqAWMepI-gPuXkg5_35AVa_pJ"
query = f"'{folder_id}' in parents and name contains 'temp_inventory_store'"

params = {
    "q": query,
    "pageSize": 10,
    "fields": "files(id, name, mimeType)"
}

cmd = [gws_exe, "drive", "files", "list", "--params", json.dumps(params)]
print(f"Running: {' '.join(cmd)}")

result = subprocess.run(cmd, capture_output=True, text=True)
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
