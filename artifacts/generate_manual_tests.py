import os
from pathlib import Path

services = {
    "gmail": [
        "Search my inbox for the last 3 emails and log the output.",
        "Find an email about 'invoice' and save the snippet to a Google Sheet.",
        "Search for 'urgent', save the top result to a document, and reply back to the sender via email using haseebmir.hm@gmail.com."
    ],
    "drive": [
        "Search my drive for files containing 'budget' and list the top 5 results.",
        "Create a new folder named 'Agentic AI Test Folder'.",
        "Search for a document named 'CcaaS - AI Product', and if found, export it to PDF."
    ],
    "sheets": [
        "Create a Google Sheet called 'Systematic Testing Data'.",
        "Read the data from my 'Systematic Testing Data' sheet and email it to haseebmir.hm@gmail.com"
    ],
    "calendar": [
        "List my upcoming calendar events for the next week.",
        "Create a calendar event for a meeting tomorrow at 10am with the subject 'GWS Validation Check', and invite haseebmir.hm@gmail.com"
    ],
    "docs": [
        "Create a Google Doc called 'Investigation Report'.",
        "Read the 'Investigation Report' Google Doc and send an email to haseebmir.hm@gmail.com with the contents."
    ],
    "slides": [
        "Fetch my latest presentation and email the link to haseebmir.hm@gmail.com"
    ],
    "contacts": [
        "List my top 5 contacts and email them to haseebmir.hm@gmail.com"
    ],
    "chat": [
        "Send a message 'Automation test' to my primary space.",
        "List my spaces and email them to haseebmir.hm@gmail.com"
    ],
    "meet": [
        "Create a Google Meet conference and email the link to haseebmir.hm@gmail.com"
    ],
    "search": [
        "Web search for 'Agentic AI Google Workspace' and email the top results to haseebmir.hm@gmail.com"
    ],
    "admin": [
        "List 5 users in my workspace and email the list to haseebmir.hm@gmail.com"
    ],
    "forms": [
        "Sync test data to Google Forms"
    ],
    "code": [
        "Write a python script to calculate the first 10 fibonacci numbers, execute it, and email the results to haseebmir.hm@gmail.com"
    ]
}

template = """import subprocess
import pytest

def run_task(task_string):
    print(f"Running manual task: python gws_cli.py --task \\"{task_string}\\"")
    import os
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(["python", "gws_cli.py", "--task", task_string], capture_output=True, text=True, encoding="utf-8", env=env)
    if "missing field `client_id`" in result.stderr or "Authentication failed" in result.stderr:
        pytest.skip("Auth not configured")
    assert result.returncode == 0, f"Task failed: {result.stderr}"

{tests}
"""

test_template = """
@pytest.mark.live_integration
def test_manual_{idx}():
    run_task("{task}")
"""

base_dir = Path("tests/manual")

for service, tasks in services.items():
    service_dir = base_dir / service
    service_dir.mkdir(parents=True, exist_ok=True)
    
    # Remove old tasks.txt
    txt_path = service_dir / "tasks.txt"
    if txt_path.exists():
        txt_path.unlink()
        
    tests_str = ""
    for idx, task in enumerate(tasks):
        tests_str += test_template.format(idx=idx+1, task=task)
        
    py_path = service_dir / f"test_manual_{service}.py"
    with open(py_path, "w", encoding="utf-8") as f:
        f.write(template.replace("{tests}", tests_str))

print("Successfully generated all manual pytest files.")
