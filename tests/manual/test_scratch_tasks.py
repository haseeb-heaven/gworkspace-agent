"""
Manual tests for scratch/tasks TXT files.
Tests each task by running it via gws_cli and verifying it executes successfully
with 5-step verification engine checks and gws.exe binary verification.
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import List

import pytest

ROOT = Path(__file__).parent.parent.parent
TASKS_DIR = ROOT / "scratch" / "tasks"
GWS_BINARY = ROOT / "gws.exe"


def verify_gws_binary() -> bool:
    """Verify gws.exe binary exists in root directory."""
    return GWS_BINARY.exists()


def verify_with_gws(service: str, action: str, resource_id: str) -> bool:
    """Verify operation using gws.exe binary for GWS_Verification."""
    try:
        if service == "drive" and action == "create_folder":
            result = subprocess.run(
                [str(GWS_BINARY), "drive", "files", "get", "--params", json.dumps({"fileId": resource_id, "fields": "id,name"})],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        elif service == "docs" and action == "create_document":
            result = subprocess.run(
                [str(GWS_BINARY), "docs", "documents", "get", "--params", json.dumps({"documentId": resource_id})],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        elif service == "sheets" and action == "create_spreadsheet":
            result = subprocess.run(
                [str(GWS_BINARY), "sheets", "spreadsheets", "get", "--params", json.dumps({"spreadsheetId": resource_id})],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        elif service == "gmail" and action == "send_message":
            result = subprocess.run(
                [str(GWS_BINARY), "gmail", "users", "messages", "get", "--params", json.dumps({"userId": "me", "id": resource_id})],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        elif service == "calendar" and action == "create_event":
            result = subprocess.run(
                [str(GWS_BINARY), "calendar", "events", "get", "--params", json.dumps({"calendarId": "primary", "eventId": resource_id})],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        elif service == "slides" and action == "create_presentation":
            result = subprocess.run(
                [str(GWS_BINARY), "slides", "presentations", "get", "--params", json.dumps({"presentationId": resource_id})],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        return True
    except Exception:
        return False


def check_verification_engine_output(stdout: str) -> bool:
    """Check if 5-step verification engine checks passed in output."""
    verification_checks = [
        "CHECK 1 PASSED - Parameter Validation",
        "CHECK 2 PASSED - Permission & Scope Validation",
        "CHECK 3 PASSED - Result Validation",
        "CHECK 4 PASSED - Data Integrity & Consistency Validation",
        "CHECK 5 PASSED - Idempotency & Safety Validation"
    ]

    for check in verification_checks:
        if check not in stdout:
            return False
    return True


def extract_resource_id_from_output(stdout: str) -> str:
    """Extract resource ID (file_id, document_id, etc.) from CLI output."""
    # Look for patterns like "ID: 1abc..." or "Document ID: 1abc..."
    import re
    patterns = [
        r"ID:\s*([A-Za-z0-9_-]+)",
        r"Document ID:\s*([A-Za-z0-9_-]+)",
        r"Spreadsheet ID:\s*([A-Za-z0-9_-]+)",
        r"Presentation ID:\s*([A-Za-z0-9_-]+)",
        r"Message ID:\s*([A-Za-z0-9_-]+)",
        r"Event ID:\s*([A-Za-z0-9_-]+)",
        r"with ID:\s*([A-Za-z0-9_-]+)"
    ]

    for pattern in patterns:
        match = re.search(pattern, stdout)
        if match:
            return match.group(1)

    return ""


def get_all_task_files() -> List[Path]:
    """Get all task TXT files from scratch/tasks."""
    return sorted(TASKS_DIR.glob("**/*.txt"))


def run_task_via_cli(task_file: Path) -> tuple[int, str, str]:
    """Run a task file via gws_cli and return exit code, stdout, stderr."""
    task_content = task_file.read_text().strip()

    result = subprocess.run(
        [sys.executable, str(ROOT / "gws_cli.py"), "--task", task_content],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=120
    )

    return result.returncode, result.stdout, result.stderr


@pytest.mark.parametrize("task_file", get_all_task_files(), ids=lambda p: str(p.relative_to(ROOT)))
@pytest.mark.manual
def test_task_execution(task_file: Path):
    """Test that each scratch task executes with 5-step verification and GWS_Verification."""
    # Verify gws.exe binary exists
    assert verify_gws_binary(), f"gws.exe not found at {GWS_BINARY}"

    returncode, stdout, stderr = run_task_via_cli(task_file)

    # Tasks should complete with exit code 0
    assert returncode == 0, f"Task failed with exit code {returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"

    # Output should not be empty
    assert len(stdout) > 0, "Task produced no output"

    # Check 5-step verification engine passed
    verification_passed = check_verification_engine_output(stdout)
    assert verification_passed, f"5-step verification engine checks failed in output:\n{stdout}"

    # Extract resource ID for GWS_Verification
    resource_id = extract_resource_id_from_output(stdout)
    if resource_id:
        # Determine service and action from task file path
        task_path = str(task_file.relative_to(TASKS_DIR))
        service = task_path.split('/')[0]

        # Map task paths to actions
        action_map = {
            "google_drive/create_env_based_folder.txt": ("drive", "create_folder"),
            "google_docs/update_env_doc.txt": ("docs", "create_document"),
            "google_sheets/create_env_sheet.txt": ("sheets", "create_spreadsheet"),
            "google_slides/create_presentation.txt": ("slides", "create_presentation"),
            "google_gmail/send_test_email.txt": ("gmail", "send_message"),
            "google_calendar/create_event.txt": ("calendar", "create_event"),
        }

        if task_path in action_map:
            service, action = action_map[task_path]
            gws_verify = verify_with_gws(service, action, resource_id)
            assert gws_verify, f"GWS_Verification with gws.exe failed for {service}.{action} with ID {resource_id}"


@pytest.mark.manual
def test_google_drive_folder_task():
    """Test google_drive/create_env_based_folder.txt with full verification."""
    assert verify_gws_binary(), f"gws.exe not found at {GWS_BINARY}"

    task_file = TASKS_DIR / "google_drive" / "create_env_based_folder.txt"
    assert task_file.exists(), f"Task file not found: {task_file}"

    returncode, stdout, stderr = run_task_via_cli(task_file)
    assert returncode == 0, f"Task failed with exit code {returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    assert check_verification_engine_output(stdout), "5-step verification checks failed"

    resource_id = extract_resource_id_from_output(stdout)
    if resource_id:
        assert verify_with_gws("drive", "create_folder", resource_id), "GWS_Verification failed"


@pytest.mark.manual
def test_google_docs_task():
    """Test google_docs/update_env_doc.txt with full verification."""
    assert verify_gws_binary(), f"gws.exe not found at {GWS_BINARY}"

    task_file = TASKS_DIR / "google_docs" / "update_env_doc.txt"
    assert task_file.exists(), f"Task file not found: {task_file}"

    returncode, stdout, stderr = run_task_via_cli(task_file)
    assert returncode == 0, f"Task failed with exit code {returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    assert check_verification_engine_output(stdout), "5-step verification checks failed"

    resource_id = extract_resource_id_from_output(stdout)
    if resource_id:
        assert verify_with_gws("docs", "create_document", resource_id), "GWS_Verification failed"


@pytest.mark.manual
def test_google_sheets_task():
    """Test google_sheets/create_env_sheet.txt with full verification."""
    assert verify_gws_binary(), f"gws.exe not found at {GWS_BINARY}"

    task_file = TASKS_DIR / "google_sheets" / "create_env_sheet.txt"
    assert task_file.exists(), f"Task file not found: {task_file}"

    returncode, stdout, stderr = run_task_via_cli(task_file)
    assert returncode == 0, f"Task failed with exit code {returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    assert check_verification_engine_output(stdout), "5-step verification checks failed"

    resource_id = extract_resource_id_from_output(stdout)
    if resource_id:
        assert verify_with_gws("sheets", "create_spreadsheet", resource_id), "GWS_Verification failed"


@pytest.mark.manual
def test_google_slides_task():
    """Test google_slides/create_presentation.txt with full verification."""
    assert verify_gws_binary(), f"gws.exe not found at {GWS_BINARY}"

    task_file = TASKS_DIR / "google_slides" / "create_presentation.txt"
    assert task_file.exists(), f"Task file not found: {task_file}"

    returncode, stdout, stderr = run_task_via_cli(task_file)
    assert returncode == 0, f"Task failed with exit code {returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    assert check_verification_engine_output(stdout), "5-step verification checks failed"

    resource_id = extract_resource_id_from_output(stdout)
    if resource_id:
        assert verify_with_gws("slides", "create_presentation", resource_id), "GWS_Verification failed"


@pytest.mark.manual
def test_google_gmail_task():
    """Test google_gmail/send_test_email.txt with full verification."""
    assert verify_gws_binary(), f"gws.exe not found at {GWS_BINARY}"

    task_file = TASKS_DIR / "google_gmail" / "send_test_email.txt"
    assert task_file.exists(), f"Task file not found: {task_file}"

    returncode, stdout, stderr = run_task_via_cli(task_file)
    assert returncode == 0, f"Task failed with exit code {returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    assert check_verification_engine_output(stdout), "5-step verification checks failed"

    resource_id = extract_resource_id_from_output(stdout)
    if resource_id:
        assert verify_with_gws("gmail", "send_message", resource_id), "GWS_Verification failed"


@pytest.mark.manual
def test_google_calendar_task():
    """Test google_calendar/create_event.txt with full verification."""
    assert verify_gws_binary(), f"gws.exe not found at {GWS_BINARY}"

    task_file = TASKS_DIR / "google_calendar" / "create_event.txt"
    assert task_file.exists(), f"Task file not found: {task_file}"

    returncode, stdout, stderr = run_task_via_cli(task_file)
    assert returncode == 0, f"Task failed with exit code {returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    assert check_verification_engine_output(stdout), "5-step verification checks failed"

    resource_id = extract_resource_id_from_output(stdout)
    if resource_id:
        assert verify_with_gws("calendar", "create_event", resource_id), "GWS_Verification failed"


@pytest.mark.manual
def test_cross_service_task():
    """Test cross_service/drive_to_sheets.txt with full verification."""
    assert verify_gws_binary(), f"gws.exe not found at {GWS_BINARY}"

    task_file = TASKS_DIR / "cross_service" / "drive_to_sheets.txt"
    assert task_file.exists(), f"Task file not found: {task_file}"

    returncode, stdout, stderr = run_task_via_cli(task_file)
    assert returncode == 0, f"Task failed with exit code {returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    assert check_verification_engine_output(stdout), "5-step verification checks failed"

    resource_id = extract_resource_id_from_output(stdout)
    if resource_id:
        assert verify_with_gws("sheets", "create_spreadsheet", resource_id), "GWS_Verification failed"
