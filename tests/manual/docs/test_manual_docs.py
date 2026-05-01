import subprocess

from dotenv import load_dotenv

load_dotenv() # Load .env at module level
import pytest


from tests.manual.shared import run_task

@pytest.mark.live_integration
def test_manual_1():
    # Create verification
    run_task("Create a Google Doc called 'Investigation Report'.", expected=["completed", "Investigation Report"], service="docs", expected_fields={"title": "Investigation Report"})


@pytest.mark.live_integration
def test_manual_2():
    # Read and email verification
    run_task("Read the 'Investigation Report' Google Doc and send an email with the contents.", expected=["Planned", "completed"], service="docs")

