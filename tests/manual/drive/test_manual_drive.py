import os

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task

TEST_DRIVE_SEARCH_QUERY = os.getenv("TEST_DRIVE_SEARCH_QUERY", "budget")
TEST_FOLDER_NAME = os.getenv("TEST_FOLDER_NAME", "Agentic AI Test Folder")
TEST_DOC_QUERY = os.getenv("TEST_DOC_QUERY", "CcaaS - AI Product")
TEST_RENAMED_FOLDER_NAME = os.getenv("TEST_RENAMED_FOLDER_NAME", "Renamed AI Folder")


@pytest.mark.live_integration

def test_manual_1():
    # Read/Search verification
    run_task(
        f"Search my drive for files containing '{TEST_DRIVE_SEARCH_QUERY}' and list the top 5 results.",
        expected=["Planned", "completed"],
        service="drive",
        read_only=True,  # Read-only operation
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_2():
    # Create verification
    run_task(
        f"Create a new folder named '{TEST_FOLDER_NAME}'.",
        expected=["completed", TEST_FOLDER_NAME],
        service="drive",
        expected_fields={"name": TEST_FOLDER_NAME},
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_3():
    # Export/Read verification
    run_task(
        f"Search for a document named '{TEST_DOC_QUERY}', and if found, export it to PDF.",
        expected=["Planned", "completed"],
        service="drive",
        read_only=True,  # May not have document
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_4():
    # Rename/Move verification
    # First create the folder if it doesn't exist, then rename it
    # This works with both LLM and heuristic mode
    run_task(
        f"Create a folder named '{TEST_FOLDER_NAME}' if it doesn't exist, then rename it to '{TEST_RENAMED_FOLDER_NAME}'.",
        expected=["completed"],
        service="drive",
        read_only=True,  # May not have folder
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_5():
    # File copy verification
    run_task(
        "Find a recent file in Drive and create a copy of it.",
        expected=["completed"],
        service="drive",
        read_only=True,  # May not have files to copy
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_6():
    # Batch operations verification
    run_task(
        "List all PDFs in Drive and export the first one if found.",
        expected=["completed"],
        service="drive",
        read_only=True,  # May not have PDFs
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_7():
    # Drive to email verification - tests template variable resolution
    # This test verifies that $drive_metadata_table and $drive_file_links are properly resolved
    run_task(
        f"Search my drive for files containing '{TEST_DRIVE_SEARCH_QUERY}' and email the results to me",
        expected=["completed"],
        service="gmail",  # The final action is sending email
        read_only=True,  # Email may not be configured
        skip_5step_verification=False,
    )


@pytest.mark.live_integration

def test_manual_8():
    # Drive metadata to email verification - tests email subject fix
    # This test verifies that email subjects use user-friendly search terms instead of Drive API query syntax
    run_task(
        f"Search drive for '{TEST_DOC_QUERY}' and send me a summary table via email",
        expected=["completed"],
        service="gmail",  # The final action is sending email
        read_only=True,  # Email may not be configured
        skip_5step_verification=False,
    )
