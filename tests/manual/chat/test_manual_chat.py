import subprocess

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest


from tests.manual.shared import run_task

@pytest.mark.live_integration
def test_manual_1():
    # Send verification
    run_task("Send a message 'Automation test' to my primary space.", expected=["completed", "Message"], service="chat")


@pytest.mark.live_integration
def test_manual_2():
    # List and email verification
    run_task("List my spaces and email them.", expected=["Planned", "completed"], service="chat")
