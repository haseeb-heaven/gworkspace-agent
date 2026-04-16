import subprocess
from dotenv import load_dotenv
load_dotenv() # Load .env at module level
import pytest

def run_task(task_string):
    import os
    load_dotenv() # Ensure .env is loaded inside helper
    email = os.getenv('DEFAULT_RECIPIENT_EMAIL', 'user@example.com')
    task_string = task_string.replace('user@example.com', email)
    import os

    import os

    print(f"Running manual task: python gws_cli.py --task \"{task_string}\"")
    import os
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(["python", "gws_cli.py", "--task", task_string], capture_output=True, text=True, encoding="utf-8", env=env)
    if "missing field `client_id`" in result.stderr or "Authentication failed" in result.stderr:
        pytest.skip("Auth not configured")
    assert result.returncode == 0, f"Task failed: {result.stderr}"


@pytest.mark.live_integration
def test_manual_1():
    run_task("Create a Google Sheet called 'Systematic Testing Data'.")

@pytest.mark.live_integration
def test_manual_2():
    run_task("Read the data from my 'Systematic Testing Data' sheet and email it to user@example.com")

