import os

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task

# Names default to historical fixtures, but can be overridden per-environment.
TEST_SHEET_NAME = os.getenv("TEST_SHEET_NAME", "Systematic Testing Data")


@pytest.mark.live_integration
def test_manual_1():
    # Create verification
    run_task(
        f"Create a Google Sheet called '{TEST_SHEET_NAME}'.",
        expected=["Command succeeded", TEST_SHEET_NAME],
        service="sheets",
        expected_fields={"title": TEST_SHEET_NAME},
    )


@pytest.mark.live_integration
def test_manual_2():
    # Read and email verification
    run_task(
        f"Read the data from my '{TEST_SHEET_NAME}' sheet and email it.",
        expected=["Command succeeded", "Command succeeded"],
        service="sheets",
    )


@pytest.mark.live_integration
def test_manual_3():
    # Append and read verification
    run_task(
        f"Append a new row with 'Date', 'Status', 'Log' values to the '{TEST_SHEET_NAME}' sheet, "
        "then read the last row.",
        expected=["Command succeeded", "Command succeeded"],
        service="sheets",
    )
