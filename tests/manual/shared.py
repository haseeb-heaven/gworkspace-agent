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


def run_task(
    task_string: str,
    expected: Sequence[str] | None = None,
    unexpected: Sequence[str] | None = None,
    service: str | None = None,
    expected_fields: dict[str, object] | None = None,
    *,
    skip_verification: bool = False,
) -> None:
    """Run a manual task and perform triple verification if *service* is provided.

    1. Verify agent output (via expected/unexpected)
    2. Verify resource existence (via TripleVerifier)
    3. Verify data integrity (via TripleVerifier + validate_artifact_content)
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

    # Tier 2 & 3: Live Resource Verification
    # Services without persistent GWS resources — skip triple verification
    _NON_VERIFIABLE_SERVICES = frozenset({"code", "search", "computation"})
    if service and service in _NON_VERIFIABLE_SERVICES:
        print(f"--- Skipping Triple Verification for non-resource service: {service} ---")
        return
    if service and not skip_verification:
        # Extract ID from output — ordered from most specific to least specific
        id_patterns = [
            r"(?:ID|id|documentId|spreadsheetId|messageId|message_id|fileId|file_id|presentationId|formId|name|resourceName):\s*([a-zA-Z0-9_./-]{5,})",
            r"\b(spaces/[a-zA-Z0-9_-]+/messages/[a-zA-Z0-9_-]+)\b",
            r"\b(spaces/[a-zA-Z0-9_-]+)\b",
            r"\b([a-f0-9]{16})\b",
            r"\b([a-zA-Z0-9_-]{30,80})\b",  # Increased min length to avoid matching random hex
        ]

        _COMMON_FALSE_POSITIVES = frozenset({
            "result", "success", "status", "tasks", "summary",
            "pythonioencoding", "authentication",
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
            task_lower = task_string.lower()
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
            verifier = TripleVerifier(runner, attempts=2, sleep_seconds=1)

            success = verifier.verify_resource(service, resource_id, expected_fields)
            if not success:
                pytest.fail(
                    f"Triple verification failed for {service} {resource_id}. "
                    "Operation may not have been completed properly."
                )
            print("--- Triple Verification Passed: Resource exists and data is valid ---")
        else:
            _creation_words = {"create", "new", "add", "send", "append"}
            # "save" often refers to local files, so we check for drive/docs/sheets context
            if "save" in task_string.lower() and any(w in task_string.lower() for w in ("drive", "sheet", "doc", "file", "form")):
                _creation_words.add("save")

            if any(word in task_string.lower() for word in _creation_words):
                pytest.fail(
                    f"Could not extract {service} resource ID from output for triple verification, "
                    "but task appears to be a creation task."
                )
            else:
                print(f"Note: No ID extracted for {service} verification (expected for non-creation tasks).")
