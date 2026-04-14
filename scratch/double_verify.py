import subprocess
import json
import os

def run_gws(args, params=None, json_data=None):
    cmd = [r"D:\Code\gworkspace-agent\gws.exe"] + args
    if params:
        cmd.extend(["--params", json.dumps(params)])
    if json_data:
        cmd.extend(["--json", json.dumps(json_data)])
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return None
    try:
        return json.loads(result.stdout)
    except:
        return result.stdout

def main():
    print("--- Double Verification Report ---")
    
    # DRIVE 1: Search budget
    print("\n[DRIVE 1] Searching for 'budget'...")
    files = run_gws(["drive", "files", "list"], params={"q": "name contains 'budget'", "fields": "files(id,name)"})
    if files and "files" in files:
        print(f"Found {len(files['files'])} files: {[f['name'] for f in files['files']]}")
    else:
        print("No budget files found.")
    
    # DRIVE 2: Folder exists
    print("\n[DRIVE 2] Checking for 'Agentic AI Test Folder'...")
    folder = run_gws(["drive", "files", "list"], params={"q": "name = 'Agentic AI Test Folder' and mimeType = 'application/vnd.google-apps.folder'"})
    if folder and folder.get("files"):
        print(f"Folder exists: {folder['files'][0]['id']}")
    else:
        print("Folder NOT found!")

    # DOCS 1: Investigation Report
    print("\n[DOCS 1] Checking Doc 'Investigation Report'...")
    doc_search = run_gws(["drive", "files", "list"], params={"q": "name = 'Investigation Report' and mimeType = 'application/vnd.google-apps.document'"})
    if doc_search and doc_search.get("files"):
        doc_id = doc_search['files'][0]['id']
        doc = run_gws(["docs", "documents", "get"], params={"documentId": doc_id})
        if doc and isinstance(doc, dict):
            print(f"Doc Title: {doc.get('title')}")
            print("Doc exists and title matches.")
        else:
            print("Failed to get doc details.")
    
    # GMAIL 2: Spreadsheet Verification
    print("\n[GMAIL 2] Checking Spreadsheet content...")
    sheet_id = "13RSOy0sSUZknUn9TmUE2oa-j-Nk78v7dd3FWlewGjEk"
    values = run_gws(["sheets", "spreadsheets", "values", "get"], params={"spreadsheetId": sheet_id, "range": "Sheet1!A1:B10"})
    if values and isinstance(values, dict) and "values" in values:
        print(f"Sheet Data: {values['values']}")
    else:
        print("Sheet Data NOT found or empty.")

    # GMAIL 3: Doc check
    print("\n[GMAIL 3] Checking 'Urgent Search Result' Doc...")
    urgent_doc_id = "10ttUK5dxibKIxcUA2UJP0rsvsA5K7TixFm3BxZNUtjE"
    doc = run_gws(["docs", "documents", "get"], params={"documentId": urgent_doc_id})
    if doc and isinstance(doc, dict):
        print(f"Urgent Doc Title: {doc.get('title')}")
    else:
        print("Urgent Doc NOT found or failed to retrieve!")

    # CALENDAR 2: Verification
    print("\n[CALENDAR 2] Checking 'GWS Validation Check' Event...")
    event_id = "m6caeodra44slg6cstdjm0ncp0"
    event = run_gws(["calendar", "events", "get"], params={"calendarId": "primary", "eventId": event_id})
    if event and isinstance(event, dict):
        print(f"Event Summary: {event.get('summary')}")
        print(f"Event Start: {event.get('start')}")
    else:
        print("Event NOT found!")

    # SHEETS: Verification
    print("\n[SHEETS 1] Checking 'Systematic Testing Data' Sheet...")
    sys_sheet_id = "1tlNzVjIdlmu01J_R99Y6DmpZgxNJNsppYfFdLK5dY4o"
    sheet = run_gws(["sheets", "spreadsheets", "get"], params={"spreadsheetId": sys_sheet_id})
    if sheet and isinstance(sheet, dict):
        print(f"Sheet Title: {sheet.get('properties', {}).get('title')}")
    else:
        print("Sheet NOT found!")

if __name__ == "__main__":
    main()
