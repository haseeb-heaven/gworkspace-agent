import subprocess

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest


from tests.manual.shared import run_task

@pytest.mark.live_integration
def test_manual_1():
    # Read/Search verification
    run_task("Search my drive for files containing 'budget' and list the top 5 results.", expected=["Planned", "completed"], service="drive")


@pytest.mark.live_integration
def test_manual_2():
    # Create verification
    run_task("Create a new folder named 'Agentic AI Test Folder'.", expected=["completed", "Agentic AI Test Folder"], service="drive", expected_fields={"name": "Agentic AI Test Folder"})


@pytest.mark.live_integration
def test_manual_3():
    # Export/Read verification
    run_task("Search for a document named 'CcaaS - AI Product', and if found, export it to PDF.", expected=["Planned", "completed"], service="drive")


@pytest.mark.live_integration
def test_manual_4():
    # Rename/Move verification
    run_task(
        "Search for a file named 'Agentic AI Test Folder', rename it to 'Renamed AI Folder', and then move it to the root of my Google Drive if it's not already there.",
        expected=["Planned", "completed", "Renamed AI Folder"],
        service="drive",
        expected_fields={"name": "Renamed AI Folder"}
    )
