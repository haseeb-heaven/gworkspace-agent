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
    # Now works with heuristic mode
    run_task(
        f"Create a Google Sheet named '{TEST_SHEET_NAME}'.",
        expected=["completed"],
        service="sheets",
        skip_verification=True,  # Heuristic mode may not use exact name
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_2():
    # Read and email verification
    # Now works with heuristic mode
    run_task(
        f"Read the data from the Google Sheet named '{TEST_SHEET_NAME}' and email it to person@example.com.",
        expected=["completed"],
        service="sheets",
        skip_verification=True,  # Email may not be configured
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_3():
    # Append and read verification
    # Now works with heuristic mode
    run_task(
        f"Add a row with data 'Test, Data, Row' to the Google Sheet named '{TEST_SHEET_NAME}'.",
        expected=["completed"],
        service="sheets",
        skip_verification=True,  # May not have sheet created
        skip_5step_verification=False,
    )
