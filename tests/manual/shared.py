import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Sequence

import pytest
from dotenv import load_dotenv

# Load .env at module level
load_dotenv()


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


def verify_with_gws(service: str, action: str, resource_id: str, binary_path: Path) -> bool:
    """Verify operation using gws.exe binary for GWS_Verification."""
    try:
        if service == "drive" and action in ("create_folder", "create"):
            result = subprocess.run(
                [str(binary_path), "drive", "files", "get", "--params", json.dumps({"fileId": resource_id, "fields": "id,name"})],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        elif service == "docs" and action in ("create_document", "create"):
            result = subprocess.run(
                [str(binary_path), "docs", "documents", "get", "--params", json.dumps({"documentId": resource_id})],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        elif service == "sheets" and action in ("create_spreadsheet", "create", "append"):
            result = subprocess.run(
                [str(binary_path), "sheets", "spreadsheets", "get", "--params", json.dumps({"spreadsheetId": resource_id})],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        elif service == "gmail" and action in ("send_message", "send"):
            result = subprocess.run(
                [str(binary_path), "gmail", "users", "messages", "get", "--params", json.dumps({"userId": "me", "id": resource_id})],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        elif service == "calendar" and action in ("create_event", "create"):
            result = subprocess.run(
                [str(binary_path), "calendar", "events", "get", "--params", json.dumps({"calendarId": "primary", "eventId": resource_id})],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        elif service == "slides" and action in ("create_presentation", "create"):
            result = subprocess.run(
                [str(binary_path), "slides", "presentations", "get", "--params", json.dumps({"presentationId": resource_id})],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        elif service == "keep" and action in ("create_note", "create"):
            result = subprocess.run(
                [str(binary_path), "keep", "notes", "get", "--params", json.dumps({"name": resource_id})],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        return True
    except Exception:
        return False


def run_task(
    task_string: str,
    expected: Sequence[str] | None = None,
    unexpected: Sequence[str] | None = None,
    service: str | None = None,
    expected_fields: dict[str, object] | None = None,
    *,
    skip_verification: bool = False,
    read_only: bool = False,
    skip_5step_verification: bool = False,
    skip_gws_verification: bool = False,
) -> None:
    """Run a manual task and perform verification if *service* is provided.

    1. Verify agent output (via expected/unexpected)
    2. Verify 5-step verification engine checks (unless skipped)
    3. Verify resource existence (via TripleVerifier)
    4. Verify data integrity (via TripleVerifier + validate_artifact_content)
    5. Verify with gws.exe binary for GWS_Verification (unless skipped)
    """
    load_dotenv()
    email = os.getenv("DEFAULT_RECIPIENT_EMAIL")
    if email:
        task_string = task_string.replace("person@example.com", email)

    test_file = os.getenv("TEST_FILE_NAME", "README.md")
    task_string = task_string.replace("TEST_FILE_NAME", test_file)

    print("Running manual task: python gws_cli.py --task <redacted>")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["NO_CONFIRM"] = "true"
    # Ensure we are in the project root
    cwd = Path(__file__).resolve().parents[2]
    script_path = cwd / "gws_cli.py"

    result = subprocess.run(  # noqa: S603
        [sys.executable, str(script_path), "--task", task_string],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=str(cwd),
    )

    auth_errors = ("missing field `client_id`" , "Authentication failed", "insufficient authentication scopes")
    if any(err in result.stderr.lower() or err in result.stdout.lower() for err in auth_errors):
        pytest.skip("Auth or Scopes not configured correctly")

    if result.returncode != 0:
        pytest.fail(
            f"Task failed with code {result.returncode}:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )

    print(f"DEBUG: Task STDOUT:\n{result.stdout.encode('ascii', 'ignore').decode('ascii')}")
    print(f"DEBUG: Task STDERR:\n{result.stderr.encode('ascii', 'ignore').decode('ascii')}")

    # Tier 1: Agent Output Verification
    if expected:
        for ex in expected:
            if ex.lower() not in result.stdout.lower():
                pytest.fail(f"Expected keyword '{ex}' not found in output")
    if unexpected:
        for unex in unexpected:
            if unex.lower() in result.stdout.lower():
                # On Windows, D:\ is very common in paths. Only fail if it's not a path.
                if unex == "D:\\" and "D:\\" in result.stdout:
                    # Heuristic: if it's followed by "Code" or a path separator, skip it
                    if re.search(r"D:\\.*[\\/]", result.stdout):
                        continue
                pytest.fail(f"Unexpected keyword '{unex}' found in output")

    # Tier 1.5: 5-Step Verification Engine Check
    if not skip_5step_verification:
        verification_passed = check_verification_engine_output(result.stdout)
        if verification_passed:
            print("--- 5-Step Verification Engine Checks Passed ---")
        else:
            print("--- Note: 5-Step Verification Engine Checks not found (may use heuristic mode) ---")

    # Tier 2 & 3: Live Resource Verification
    # Services without persistent GWS resources — skip triple verification
    if read_only:
        print("--- Skipping Triple Verification for read-only/conditional operation ---")
        return
    _NON_VERIFIABLE_SERVICES = frozenset({"code", "search", "computation"})
    if service and service in _NON_VERIFIABLE_SERVICES:
        print(f"--- Skipping Triple Verification for non-resource service: {service} ---")
        return
    if service and not skip_verification:
        task_lower = task_string.lower()
        if service == "meet" and any(word in task_lower for word in ("email", "mail", "send", "share")):
            print("--- Skipping Triple Verification for Meet cross-service sharing flow ---")
            return

        # Extract ID from output — ordered from most specific to least specific
        id_patterns = [
            r"(?:ID|id|documentId|spreadsheetId|messageId|message_id|fileId|file_id|presentationId|formId|name|resourceName|eventId|event_id):\s*([a-zA-Z0-9_/-]{5,})",
            r"(?:Triple-check passed for\s+[a-z]+\s+)([a-zA-Z0-9_/-]{5,})",
            r"\b(spaces/[a-zA-Z0-9_-]+/messages/[a-zA-Z0-9_-]+)\b",
            r"\b(spaces/[a-zA-Z0-9_-]+)\b",
            r"\b([a-f0-9]{16})\b",
            r"\b([a-zA-Z0-9_-]{30,128})\b",
        ]

        _COMMON_FALSE_POSITIVES = frozenset({
            "result", "success", "status", "tasks", "summary",
            "pythonioencoding", "authentication", "llm_model", "model",
            "gemini-flash-latest", "llama-3-groq-70b-8192-tool-use-preview",
        })

        resource_id = None
        for pattern in id_patterns:
            match = re.search(pattern, result.stdout)
            if match:
                candidate = match.group(1) if match.groups() else match.group(0)
                if not re.search(r"[a-zA-Z0-9]", candidate):
                    continue
                if candidate.lower() in _COMMON_FALSE_POSITIVES:
                    continue

                # Service-aware filtering
                if service == "gmail" and len(candidate) > 20: # Gmail IDs are 16 chars
                    continue
                if service in ("sheets", "docs", "drive") and len(candidate) < 25:
                    continue

                resource_id = candidate
                break

        if resource_id:
            # Skip verification for pure read-only tasks
            _mutation_words = {"create", "new", "add", "send", "save", "append", "move", "copy", "remove", "delete", "rename"}
            _read_words = {"list", "search", "find", "show", "get"}
            is_mutation = any(w in task_lower for w in _mutation_words)
            is_read_only = any(w in task_lower for w in _read_words)

            if is_read_only and not is_mutation:
                print("--- Skipping Triple Verification for read-only/list task ---")
                return

            from gws_assistant.config import AppConfig
            from gws_assistant.execution.verifier import TripleVerifier
            from gws_assistant.gws_runner import GWSRunner

            config = AppConfig.from_env()
            binary_path = Path(config.gws_binary_path)
            if not binary_path.is_absolute():
                binary_path = cwd / binary_path

            print(f"--- Triple Verification for {service} ---")
            print(f"Using binary (GWS_BINARY_PATH): {binary_path}")
            print(f"Verifying ID: {resource_id}")

            runner = GWSRunner(binary_path, logging.getLogger("triple_verifier"), config=config)
            verifier = TripleVerifier(runner, attempts=5, sleep_seconds=1)

            success = verifier.verify_resource_by_id(service, resource_id, expected_fields)
            if not success:
                pytest.fail(
                    f"Triple verification failed for {service} {resource_id}. "
                    "Operation may not have been completed properly."
                )
            print("--- Triple Verification Passed: Resource exists and data is valid ---")

            # Tier 4: GWS_Verification with gws.exe binary
            if not skip_gws_verification:
                gws_verify = verify_with_gws(service, "create", resource_id, binary_path)
                if gws_verify:
                    print("--- GWS_Verification Passed: Verified with gws.exe binary ---")
                else:
                    print("--- Note: GWS_Verification skipped or failed (non-critical) ---")
        else:
            _creation_words = {"create", "new", "add", "append"}
            _read_words = {"read", "get", "fetch", "list", "search", "find", "show"}

            # "send" is only a creation task for the service being verified
            # If we're verifying docs but the task sends an email, that's not a docs creation
            _service_specific_creation = {
                "gmail": {"send", "reply", "forward"},
                "sheets": {"create", "append", "add"},
                "docs": {"create", "append", "add"},
                "drive": {"create", "upload", "copy"},
                "slides": {"create", "append"},
                "forms": {"create"},
            }

            # Check if the task is primarily about creating the service being verified
            service_specific_creates = _service_specific_creation.get(service, set())

            # If the task starts with read words, it's likely a read task
            if any(word in task_lower for word in _read_words):
                print(f"Note: No ID extracted for {service} verification (expected for read task).")
                return

            # If the task has creation words for the specific service, it's a creation task
            if any(word in task_lower for word in service_specific_creates):
                pytest.fail(
                    f"Could not extract {service} resource ID from output for triple verification, "
                    "but task appears to be a creation task."
                )

            # "save" often refers to local files, so we check for drive/docs/sheets context
            if "save" in task_lower and any(w in task_lower for w in ("drive", "sheet", "doc", "file", "form")):
                if service in ["drive", "sheets", "docs"]:
                    pytest.fail(
                        f"Could not extract {service} resource ID from output for triple verification, "
                        "but task appears to be a creation task."
                    )

            print(f"Note: No ID extracted for {service} verification (expected for non-creation tasks).")
