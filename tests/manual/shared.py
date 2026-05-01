import logging
import os
import re
import subprocess
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load .env at module level
load_dotenv()

def run_task(task_string, expected=None, unexpected=None, service=None, expected_fields=None):
    """
    Runs a manual task and performs triple verification if service is provided.
    1. Verify agent output (via expected/unexpected)
    2. Verify resource existence (via TripleVerifier)
    3. Verify data integrity (via TripleVerifier + validate_artifact_content)
    """
    load_dotenv()
    email = os.getenv("DEFAULT_RECIPIENT_EMAIL")
    if email:
        # Replace both placeholders and the actual email if it was hardcoded as person@example.com
        task_string = task_string.replace("person@example.com", email)

    test_file = os.getenv("TEST_FILE_NAME", "README.md")
    task_string = task_string.replace("TEST_FILE_NAME", test_file)

    print(f'Running manual task: python gws_cli.py --task "{task_string}"')

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    # Ensure we are in the project root
    cwd = Path(__file__).resolve().parents[2]

    import sys
    result = subprocess.run(
        [sys.executable, "gws_cli.py", "--task", task_string],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=str(cwd)
    )

    if "missing field `client_id`" in result.stderr or "Authentication failed" in result.stderr:
        pytest.skip("Auth not configured")

    if result.returncode != 0:
        pytest.fail(f"Task failed with code {result.returncode}:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")

    # Tier 1: Agent Output Verification
    if expected:
        for ex in expected:
            if ex.lower() not in result.stdout.lower():
                pytest.fail(f"Expected keyword '{ex}' not found in output")
    if unexpected:
        for unex in unexpected:
            if unex.lower() in result.stdout.lower():
                pytest.fail(f"Unexpected keyword '{unex}' found in output")

    # Tier 2 & 3: Live Resource Verification
    if service:
        # Extract ID from output
        # Common GWS ID patterns
        id_patterns = [
            r"(?:ID|id|documentId|spreadsheetId|messageId|message_id|fileId|file_id|presentationId|formId|name|resourceName):\s*([a-zA-Z0-9_-]{5,})",
            r"\b(spaces/[a-zA-Z0-9_-]+/messages/[a-zA-Z0-9_-]+)\b", # Chat Message Name
            r"\b([a-f0-9]{16})\b",         # Gmail IDs
            r"\b([a-zA-Z0-9_-]{20,})\b",  # Long IDs like Drive/Docs/Sheets/Slides (Greedy fallback)
        ]

        resource_id = None
        for pattern in id_patterns:
            match = re.search(pattern, result.stdout)
            if match:
                resource_id = match.group(1) if match.groups() else match.group(0)
                # Filter out false positives like separator lines or common words
                if not re.search(r"[a-zA-Z0-9]", resource_id):
                    continue
                if resource_id.lower() in ("result", "success", "status", "tasks", "summary"):
                    continue
                break

        if resource_id:
            # Skip verification for list/search/find tasks as they don't produce a single verifiable "created" resource
            is_mutation = any(word in task_string.lower() for word in ["create", "new", "add", "send", "save", "append", "move", "copy", "remove", "delete", "rename"])
            is_read_only = any(word in task_string.lower() for word in ["list", "search", "find", "show", "get"])

            if is_read_only and not is_mutation:
                print(f"--- Skipping Triple Verification for read-only/list task: {task_string} ---")
                return

            # Tier 2 & 3: Live Resource Verification using GWS_BINARY_PATH
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
                pytest.fail(f"Triple verification failed for {service} {resource_id}. Operation may not have been completed properly.")
            print("--- Triple Verification Passed: Resource exists and data is valid ---")
        else:
            if any(word in task_string.lower() for word in ["create", "new", "add", "send", "save", "append"]):
                print(f"Warning: Could not extract {service} ID from output for triple verification, but task appears to be a creation task.")
            else:
                print(f"Note: No ID extracted for {service} verification (expected for non-creation tasks).")
