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
    )


@pytest.mark.live_integration
def test_manual_2():
    # Create verification
    run_task(
        f"Create a new folder named '{TEST_FOLDER_NAME}'.",
        expected=["completed", TEST_FOLDER_NAME],
        service="drive",
        expected_fields={"name": TEST_FOLDER_NAME},
    )


@pytest.mark.live_integration
def test_manual_3():
    # Export/Read verification
    run_task(
        f"Search for a document named '{TEST_DOC_QUERY}', and if found, export it to PDF.",
        expected=["Planned", "completed"],
        service="drive",
    )


@pytest.mark.live_integration
def test_manual_4():
    # Rename/Move verification
    run_task(
        f"Search for a file named '{TEST_FOLDER_NAME}', rename it to '{TEST_RENAMED_FOLDER_NAME}', "
        "and then move it to the root of my Google Drive if it's not already there.",
        expected=["Planned", "completed", TEST_RENAMED_FOLDER_NAME],
        service="drive",
        expected_fields={"name": TEST_RENAMED_FOLDER_NAME},
    )
