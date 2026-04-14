import subprocess
import pytest

def run_task(task_string):
    print(f"Running manual task: python gws_cli.py --task \"{task_string}\"")
    result = subprocess.run(["python", "gws_cli.py", "--task", task_string], capture_output=True, text=True)
    if "missing field `client_id`" in result.stderr or "Authentication failed" in result.stderr:
        pytest.skip("Auth not configured")
    assert result.returncode == 0, f"Task failed: {result.stderr}"


@pytest.mark.live_integration
def test_manual_1():
    run_task("Send a message 'Automation test' to my primary space.")

@pytest.mark.live_integration
def test_manual_2():
    run_task("List my spaces and email them to haseebmir.hm@gmail.com")

