#!/usr/bin/env python
"""Comprehensive verification script for GWS data structures."""

import json
import shlex
import subprocess
import sys
from typing import Sequence


def run_command(cmd: Sequence[str]) -> tuple[str, str, int]:
    """Run a shell command and return the output."""
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    return result.stdout, result.stderr, result.returncode

def verify_gmail_triage() -> bool:
    """Verify Gmail triage returns valid data."""
    print("=" * 60)
    print("VERIFYING: Gmail triage data structure")
    print("=" * 60)

    stdout, stderr, code = run_command(shlex.split("gws gmail +triage"))

    if code != 0:
        print(f"[FAILED] Gmail triage command failed with code {code}")
        print("[ERROR] Internal command error occurred during triage.")
        return False

    if not stdout:
        print("[FAILED] Gmail triage returned no output")
        return False

    print("[PASSED] Gmail triage command succeeded")
    print(f"Output length: {len(stdout)} characters")
    return True

def verify_gmail_read() -> bool:
    """Verify Gmail read returns valid JSON data."""
    print("\n" + "=" * 60)
    print("VERIFYING: Gmail read JSON data structure")
    print("=" * 60)

    # First get a message ID from triage
    stdout, stderr, code = run_command(shlex.split("gws gmail +triage"))
    if code != 0 or not stdout:
        print("[FAILED] Cannot get message ID from triage")
        return False

    # Extract first message ID (more robust parsing)
    lines = stdout.split('\n')
    message_id = None
    for line in lines:
        # Look for lines that contain message IDs (typically start with 19e)
        if '19e' in line and 'id' not in line.lower():  # Skip header line
            # Split by whitespace (the output is space-separated)
            parts = line.split()
            for part in parts:
                part = part.strip()
                if part.startswith('19e') and len(part) > 10:
                    message_id = part
                    print("Using message ID: [REDACTED]")
                    break
            if message_id:
                break

    if not message_id:
        print("[FAILED] Could not extract message ID from triage output")
        return False

    # Read the message with JSON format
    stdout, stderr, code = run_command(shlex.split(f'gws gmail +read --id {message_id} --format json'))

    if code != 0 or not stdout:
        print(f"[FAILED] Gmail read command failed with code {code}")
        if stderr:
            error_summary = stderr.split('\n')[0][:100]
            print(f"ERROR SUMMARY: {error_summary}...")
        return False

    # Verify JSON structure
    try:
        data = json.loads(stdout)
        required_fields = ['thread_id', 'message_id', 'from', 'to', 'subject', 'date', 'body_text']
        missing_fields = [f for f in required_fields if f not in data]

        if missing_fields:
            print(f"[FAILED] Missing required fields: {missing_fields}")
            return False

        print("[PASSED] Gmail read returns valid JSON with all required fields")
        print(f"Fields: {list(data.keys())}")
        return True

    except json.JSONDecodeError as e:
        print(f"[FAILED] Invalid JSON output: {e}")
        return False

def verify_docs_create() -> str:
    """Verify Google Docs create returns valid data."""
    print("\n" + "=" * 60)
    print("VERIFYING: Google Docs create data structure")
    print("=" * 60)

    # Implement real verification using subprocess.run (no shell=True) via run_command
    title = "Verification Test Doc"
    cmd = ["gws", "docs", "documents", "create", "--json", json.dumps({"title": title})]

    stdout, stderr, code = run_command(cmd)

    if code != 0:
        print(f"[FAILED] Docs create command failed with code {code}")
        print(f"STDERR: {stderr}")
        return ""

    try:
        data = json.loads(stdout)
        doc_id = data.get("documentId")
        if not doc_id:
            print(f"[FAILED] Docs create output missing documentId: {stdout}")
            return ""

        print(f"[PASSED] Docs create successful. Document ID: {doc_id}")
        return doc_id
    except json.JSONDecodeError as e:
        print(f"[FAILED] Invalid JSON output from Docs create: {e}")
        print(f"STDOUT: {stdout}")
        return ""

def verify_docs_write(document_id: str) -> bool:
    """Verify Google Docs write returns valid data."""
    print("\n" + "=" * 60)
    print("VERIFYING: Google Docs write data structure")
    print("=" * 60)

    text = "Hello from verification script!"
    requests_payload = [{"insertText": {"endOfSegmentLocation": {"segmentId": ""}, "text": text}}]
    json_body = json.dumps({"requests": requests_payload})

    cmd = [
        "gws",
        "docs",
        "documents",
        "batchUpdate",
        "--params",
        json.dumps({"documentId": document_id}),
        "--json",
        json_body
    ]

    stdout, stderr, code = run_command(cmd)

    if code != 0:
        print(f"[FAILED] Docs write command failed with code {code}")
        print(f"STDERR: {stderr}")
        return False

    print("[PASSED] Docs write (batchUpdate) successful")
    return True

def verify_docs_get(document_id: str) -> bool:
    """Verify Google Docs get returns valid data."""
    print("\n" + "=" * 60)
    print("VERIFYING: Google Docs get data structure")
    print("=" * 60)

    cmd = [
        "gws",
        "docs",
        "documents",
        "get",
        "--params",
        json.dumps({"documentId": document_id})
    ]

    stdout, stderr, code = run_command(cmd)

    if code != 0:
        print(f"[FAILED] Docs get command failed with code {code}")
        print(f"STDERR: {stderr}")
        return False

    try:
        data = json.loads(stdout)
        if "documentId" not in data or "body" not in data:
            print(f"[FAILED] Docs get output missing required fields: {list(data.keys())}")
            return False

        print("[PASSED] Docs get returns valid document structure")
        return True
    except json.JSONDecodeError as e:
        print(f"[FAILED] Invalid JSON output from Docs get: {e}")
        return False

def verify_resolver_with_gmail_data() -> bool:
    """Verify resolver can handle Gmail data patterns."""
    print("\n" + "=" * 60)
    print("VERIFYING: Resolver with Gmail data patterns")
    print("=" * 60)

    try:
        import logging

        from gws_assistant.execution.resolver import ResolverMixin

        class MockResolver(ResolverMixin):
            def __init__(self):
                self.logger = logging.getLogger('test')

        resolver = MockResolver()

        # Test Gmail data structure
        context = {
            'task_results': {
                'task-1': {
                    'messages': [
                        {
                            'thread_id': 'test123',
                            'message_id': 'msg123',
                            'from': {'name': 'Test', 'email': 'test@example.com'},
                            'to': [{'name': None, 'email': 'recipient@example.com'}],
                            'subject': 'Test Subject',
                            'date': 'Fri, 8 May 2026 00:00:00 +0000',
                            'body_text': 'Test body'
                        }
                    ]
                }
            }
        }

        # Test various path patterns
        tests = [
            ('task-1.messages.message_id', ['msg123']),
            ('task-1.messages[0].message_id', 'msg123'),
            ('task-1.messages[0].from.email', 'test@example.com'),
            ('task-1.messages.subject', ['Test Subject']),
        ]

        for path, expected in tests:
            result = resolver._get_value_by_path(context['task_results'], path)
            if result != expected:
                print(f"[FAILED] Path '{path}' returned {result}, expected {expected}")
                return False
            print(f"[PASSED] Path '{path}' returned {result}")

        return True

    except Exception as e:
        print(f"[FAILED] Resolver test failed with exception: {e}")
        return False

def verify_resolver_with_docs_data() -> bool:
    """Verify resolver can handle Docs data patterns."""
    print("\n" + "=" * 60)
    print("VERIFYING: Resolver with Docs data patterns")
    print("=" * 60)

    try:
        import logging

        from gws_assistant.execution.resolver import ResolverMixin

        class MockResolver(ResolverMixin):
            def __init__(self):
                self.logger = logging.getLogger('test')

        resolver = MockResolver()

        # Test Docs data structure
        context = {
            'task_results': {
                'task-1': {
                    'documentId': 'doc123',
                    'body': {
                        'content': [
                            {
                                'paragraph': {
                                    'elements': [
                                        {
                                            'textRun': {
                                                'content': 'Test content\n'
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        }

        # Test various path patterns
        tests = [
            ('task-1.documentId', 'doc123'),
            ('task-1.body.content', context['task_results']['task-1']['body']['content']),
            ('task-1.body.content[0].paragraph.elements[0].textRun.content', 'Test content\n'),
        ]

        for path, expected in tests:
            result = resolver._get_value_by_path(context['task_results'], path)
            if result != expected:
                print(f"[FAILED] Path '{path}' returned {result}, expected {expected}")
                return False
            print(f"[PASSED] Path '{path}' returned correct type")

        return True

    except Exception as e:
        print(f"[FAILED] Resolver test failed with exception: {e}")
        return False

def main() -> int:
    """Run all verification tests."""
    print("COMPREHENSIVE GWS DATA STRUCTURE VERIFICATION")
    print("=" * 60)

    all_passed = True

    # Verify Gmail
    if not verify_gmail_triage():
        all_passed = False

    if not verify_gmail_read():
        all_passed = False

    # Verify Docs
    doc_id = verify_docs_create()
    if doc_id:
        if not verify_docs_write(doc_id):
            all_passed = False
        if not verify_docs_get(doc_id):
            all_passed = False
    else:
        all_passed = False

    # Verify Resolver
    if not verify_resolver_with_gmail_data():
        all_passed = False

    if not verify_resolver_with_docs_data():
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("[PASSED] ALL VERIFICATIONS PASSED")
        print("=" * 60)
        return 0
    else:
        print("[FAILED] SOME VERIFICATIONS FAILED")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
