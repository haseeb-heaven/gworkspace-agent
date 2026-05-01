import subprocess

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest


from tests.manual.shared import run_task

@pytest.mark.live_integration
def test_manual_1():
    # Read and email verification
    run_task("List my top 5 contacts and email them.", expected=["Planned", "completed"], service="contacts")
@pytest.mark.live_integration
def test_manual_2():
    # Read and email verification
    run_task("List 5 users in my workspace directory and email the list.", expected=["Planned", "completed"], service="contacts")
