import subprocess

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest


from tests.manual.shared import run_task

@pytest.mark.live_integration
def test_manual_1():
    # Create and email verification
    run_task("Create a Google Meet conference and email the link.", expected=["Created", "Sent", "Meet"], service="meet")
