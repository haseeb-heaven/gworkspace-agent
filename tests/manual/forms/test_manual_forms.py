import subprocess
import pytest

def run_task(task_string):
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
    run_task("Sync test data to Google Forms")

