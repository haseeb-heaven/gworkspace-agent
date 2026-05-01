import json
from pathlib import Path
from typing import Any

from gws_assistant.gws_runner import GWSRunner
from gws_assistant.models import ExecutionResult


class FakeGoogleWorkspace(GWSRunner):
    def __init__(self, should_fail_on_first_call=False):
        # We don't actually need a binary path, but we provide a fake one to satisfy the base class
        super().__init__(gws_binary_path=Path("/fake/gws"), logger=None, config=None)
        self.call_log: list[dict[str, Any]] = []
        self.should_fail_on_first_call = should_fail_on_first_call
        self.call_count = 0
        self.next_error = None
        self.mocked_responses = {}

    def validate_binary(self) -> bool:
        return True

    def run(self, args: list[str], timeout_seconds: int | None = None) -> ExecutionResult:
        self.call_count += 1

        # Parse args back into service, action, and parameters
        # Real args might have structural commands, but here we just look at the first component and then try to infer action based on args or the known mapped task actions.
        # But wait, in the executor, build_command outputs actual API command structures, e.g. ["gmail", "users", "messages", "list", ...]
        # We need to map that back to our logical action, or just use the raw args for logic.
        if len(args) < 2:
            return ExecutionResult(success=False, command=args, error="Not enough arguments")

        service = args[0]

        action = "unknown"
        if service == "gmail":
            if "messages" in args and "list" in args:
                action = "list_messages"
            elif "messages" in args and "get" in args:
                action = "get_message"
            elif "messages" in args and "send" in args:
                action = "send_message"
        elif service == "sheets":
            if "spreadsheets" in args and "create" in args:
                action = "create_spreadsheet"
            elif "values" in args and "append" in args:
                action = "append_values"
            elif "values" in args and "get" in args:
                action = "get_values"
            elif "+read" in args:
                action = "get_values"
            elif "spreadsheets" in args and "get" in args:
                action = "get_spreadsheet"
        elif service == "drive":
            if "files" in args and "list" in args:
                action = "list_files"
            elif "files" in args and "export" in args:
                action = "export_file"
            elif "files" in args and "get" in args:
                action = "get_file"
            elif "list" in args:  # heuristic planner might output basic args
                action = "list_files"
        elif service == "docs":
            if "documents" in args and "create" in args:
                action = "create_document"
            elif "documents" in args and "batchUpdate" in args:
                action = "batch_update"
            elif "create" in args:
                action = "create_document"
            elif "batchUpdate" in args:
                action = "batch_update"

        # Parse params
        params = {}
        for i in range(2, len(args)):
            if args[i] == "--params" and i + 1 < len(args):
                try:
                    params.update(json.loads(args[i + 1]))
                except Exception:
                    pass
            elif args[i] == "--json" and i + 1 < len(args):
                try:
                    params.update(json.loads(args[i + 1]))
                except Exception:
                    pass
            elif args[i].startswith("--") and i + 1 < len(args) and not args[i + 1].startswith("--"):
                key = args[i][2:]
                params[key] = args[i + 1]

        self.call_log.append({"service": service, "action": action, "args": args, "params": params})

        if self.should_fail_on_first_call and self.call_count == 1:
            return ExecutionResult(
                success=False,
                command=args,
                error="Injected transient error for testing",
                return_code=500,
                stderr="Injected transient error for testing",
            )

        if self.next_error:
            err = self.next_error
            self.next_error = None
            return err

        # Mock implementations
        output = {}
        if service == "gmail":
            if action == "list_messages":
                output = {
                    "messages": [
                        {"id": "msg1", "threadId": "th1", "snippet": "Unread message 1"},
                        {"id": "msg2", "threadId": "th2", "snippet": "Unread message 2"},
                        {"id": "msg3", "threadId": "th3", "snippet": "Invoice message"},
                    ]
                }
            elif action == "get_message":
                output = {
                    "id": params.get("id", "msg1"),
                    "threadId": "th1",
                    "snippet": "Full message content about invoice",
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "Jane Doe <jane.doe@gmail.com>"},
                            {"name": "Subject", "value": "Real Invoice Data"},
                            {"name": "Date", "value": "2023-10-01"},
                        ],
                        "body": {"data": "SGk="},
                    },  # Base64 for "Hi"
                    "body_text": "Full message content about invoice 100$",
                }
            elif action == "send_message":
                output = {"id": "sent_msg_123", "threadId": "sent_th_123", "labelIds": ["SENT"]}

        elif service == "sheets":
            if action == "create_spreadsheet":
                output = {
                    "spreadsheetId": "fake_sheet_id_123",
                    "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/fake_sheet_id_123",
                    "sheets": [{"properties": {"title": "Sheet1"}}],
                }
            elif action == "append_values":
                output = {
                    "spreadsheetId": params.get("spreadsheet_id", "fake_sheet_id_123"),
                    "updates": {"updatedRows": 3},
                }
            elif action == "get_values":
                output = {"values": [["Row1", "Data1"], ["Row2", "Data2"]]}
            elif action == "get_spreadsheet":
                output = {
                    "spreadsheetId": params.get("spreadsheetId", "fake_sheet_id_123"),
                    "properties": {"title": "Test Sheet"},
                    "sheets": [{"properties": {"title": "Sheet1"}, "data": {}}],
                }

        elif service == "drive":
            if action == "list_files":
                output = {"files": [{"id": "file123", "name": "Report Document.pdf", "mimeType": "application/pdf"}]}
            elif action == "export_file" or action == "get_file":
                output = {
                    "id": "file123",
                    "name": "Report Document.pdf",
                    "saved_file": "/tmp/fake_exported_file.pdf",
                    "content": "Fake content of exported file: extracted data 42",
                }

        elif service == "docs":
            if action == "create_document":
                output = {"documentId": "fake_doc_id_456", "body": {"content": []}}
            elif action == "batch_update":
                output = {"documentId": params.get("documentId", "fake_doc_id_456"), "body": {"content": []}}

        # Override with any custom mock responses
        key = f"{service}.{action}"
        if key in self.mocked_responses:
            output = self.mocked_responses[key]

        return ExecutionResult(success=True, command=args, stdout=json.dumps(output), output=output, return_code=0)
