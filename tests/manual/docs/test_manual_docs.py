import os

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task

TEST_DOC_NAME = os.getenv("TEST_DOC_NAME", "Investigation Report")


@pytest.mark.live_integration
def test_manual_1():
    # Create verification
    run_task(
        f"Create a Google Doc called '{TEST_DOC_NAME}'.",
        expected=["completed", TEST_DOC_NAME],
        service="docs",
        expected_fields={"title": TEST_DOC_NAME},
        skip_5step_verification=False,
    )


@pytest.mark.live_integration
def test_manual_2():
    # Read and email verification
    run_task(
        f"Read the '{TEST_DOC_NAME}' Google Doc and send an email with the contents.",
        expected=["Planned", "completed"],
        service="docs",
        skip_5step_verification=False,
    )
