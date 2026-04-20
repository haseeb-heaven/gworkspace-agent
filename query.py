import subprocess, json
try:
    res = subprocess.check_output(['D:/Code/gworkspace-agent/gws.exe', 'drive', 'files', 'list', '--params', '{"q": "name=\'temp_inventory_store\' and trashed=false", "fields": "files(id, name, mimeType, size)"}']).decode('utf-8')
    print(json.dumps(json.loads(res), indent=2))
except Exception as e:
    print(e)
