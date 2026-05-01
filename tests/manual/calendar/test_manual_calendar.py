import subprocess

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest


from tests.manual.shared import run_task

@pytest.mark.live_integration
def test_manual_1():
    # Read verification
    run_task("List my upcoming calendar events for the next week.", expected=["Result"], service="calendar")


@pytest.mark.live_integration
def test_manual_2():
    # Create verification
    import time
    ts = int(time.time())
    run_task(
        f"Create a calendar event for a meeting tomorrow at 10am with the subject 'GWS Validation {ts}'.",
        expected=["completed", f"GWS Validation {ts}"],
        service="calendar",
        expected_fields={"summary": f"GWS Validation {ts}"}
    )
