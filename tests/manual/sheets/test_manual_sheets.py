
from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task


@pytest.mark.live_integration
def test_manual_1():
    # Create verification
    run_task("Create a Google Sheet called 'Systematic Testing Data'.", expected=["completed", "Systematic Testing Data"], service="sheets", expected_fields={"title": "Systematic Testing Data"})


@pytest.mark.live_integration
def test_manual_2():
    # Read and email verification
    run_task("Read the data from my 'Systematic Testing Data' sheet and email it.", expected=["Planned", "completed"], service="sheets")


@pytest.mark.live_integration
def test_manual_3():
    # Append and read verification
    run_task(
        "Append a new row with 'Date', 'Status', 'Log' values to the 'Systematic Testing Data' sheet, then read the last row.",
        expected=["Planned", "completed"],
        service="sheets"
    )
