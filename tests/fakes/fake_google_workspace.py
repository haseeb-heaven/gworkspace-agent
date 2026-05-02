"""Fake GWS runner for unit and integration tests.

Mocks Google Workspace API responses for all major services and file types.
"""

import json
import re
from pathlib import Path
from typing import Any

from gws_assistant.gws_runner import GWSRunner
from gws_assistant.models import ExecutionResult

# Pre-canned file metadata for common MIME types used in tests.
_FAKE_DRIVE_FILES: list[dict[str, Any]] = [
    {"id": "doc_abc_1", "name": "Quarterly Report.docx", "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    {"id": "sheet_def_2", "name": "Budget 2026.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    {"id": "slide_ghi_3", "name": "Pitch Deck.pptx", "mimeType": "application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    {"id": "pdf_jkl_4", "name": "Invoice.pdf", "mimeType": "application/pdf"},
    {"id": "txt_mno_5", "name": "notes.txt", "mimeType": "text/plain"},
    {"id": "csv_pqr_6", "name": "data.csv", "mimeType": "text/csv"},
    {"id": "img_stu_7", "name": "logo.png", "mimeType": "image/png"},
    {"id": "img_vwx_8", "name": "photo.jpg", "mimeType": "image/jpeg"},
    {"id": "audio_yz9", "name": "recording.mp3", "mimeType": "audio/mpeg"},
    {"id": "video_0ab", "name": "demo.mp4", "mimeType": "video/mp4"},
    {"id": "video_cde", "name": "archive.mkv", "mimeType": "video/x-matroska"},
    {"id": "gdoc_fgh", "name": "Meeting Notes", "mimeType": "application/vnd.google-apps.document"},
    {"id": "gsheet_ijk", "name": "Project Tracker", "mimeType": "application/vnd.google-apps.spreadsheet"},
    {"id": "gslides_lmn", "name": "Team Overview", "mimeType": "application/vnd.google-apps.presentation"},
]


def _find_file_by_id(file_id: str) -> dict[str, Any] | None:
    for f in _FAKE_DRIVE_FILES:
        if f["id"] == file_id:
            return f
    return None


def _find_file_by_name(name: str) -> dict[str, Any] | None:
    for f in _FAKE_DRIVE_FILES:
        if f["name"].lower() == name.lower():
            return f
    return None


class FakeGoogleWorkspace(GWSRunner):
    """Stub runner that records calls and returns synthetic GWS responses."""

    def __init__(self, should_fail_on_first_call: bool = False):
        super().__init__(gws_binary_path=Path("/fake/gws"), logger=None, config=None)
        self.call_log: list[dict[str, Any]] = []
        self.should_fail_on_first_call = should_fail_on_first_call
        self.call_count = 0
        self.next_error: ExecutionResult | None = None
        self.mocked_responses: dict[str, Any] = {}
        self._created_files: list[dict[str, Any]] = []
        self._trashed_files: set[str] = set()
        self._folders: dict[str, dict[str, Any]] = {}
        self._upload_counter = 0

    def validate_binary(self) -> bool:
        return True

    def _find_file(self, file_id: str) -> dict[str, Any] | None:
        """Search both pre-canned files and dynamically created/uploaded files."""
        return _find_file_by_id(file_id) or next(
            (f for f in self._created_files if f["id"] == file_id), None
        )

    def run(self, args: list[str], timeout_seconds: int | None = None) -> ExecutionResult:
        self.call_count += 1

        if len(args) < 2:
            return ExecutionResult(success=False, command=args, error="Not enough arguments")

        service = args[0]
        action = self._detect_action(service, args)
        params = self._parse_params(args)

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

        output = self._handle_service(service, action, params, args)

        # Allow custom overrides
        key = f"{service}.{action}"
        if key in self.mocked_responses:
            output = self.mocked_responses[key]

        # Persist exported / downloaded files to scratch so downstream code works.
        if action in ("export_file", "get_file") and isinstance(output, dict) and "saved_file" in output:
            self._persist_file(output)

        return ExecutionResult(
            success=True,
            command=args,
            stdout=json.dumps(output),
            output=output,
            return_code=0,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_action(service: str, args: list[str]) -> str:
        action = "unknown"
        if service == "gmail":
            if "messages" in args and "list" in args:
                action = "list_messages"
            elif "messages" in args and "get" in args:
                action = "get_message"
            elif "messages" in args and "send" in args:
                action = "send_message"
            elif "messages" in args and "trash" in args:
                action = "trash_message"
            elif "messages" in args and "delete" in args:
                action = "delete_message"
        elif service == "sheets":
            if "spreadsheets" in args and "create" in args:
                action = "create_spreadsheet"
            elif "values" in args and "append" in args:
                action = "append_values"
            elif "values" in args and "get" in args:
                action = "get_values"
            elif "values" in args and "clear" in args:
                action = "clear_values"
            elif "+read" in args:
                action = "get_values"
            elif "spreadsheets" in args and "get" in args:
                action = "get_spreadsheet"
        elif service == "drive":
            if "files" in args and "list" in args:
                action = "list_files"
            elif "files" in args and "create" in args and "--upload" in args:
                action = "upload_file"
            elif "files" in args and "create" in args:
                # Could be create_folder or create_file; inspect payload
                action = "create_file_or_folder"
            elif "files" in args and "export" in args:
                action = "export_file"
            elif "files" in args and "get" in args:
                action = "get_file"
            elif "files" in args and "delete" in args:
                action = "delete_file"
            elif "files" in args and "update" in args:
                # Could be trash, rename, or move
                action = "update_file"
            elif "files" in args and "copy" in args:
                action = "copy_file"
            elif "list" in args:
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
        elif service == "slides":
            if "presentations" in args and "create" in args:
                action = "create_presentation"
            elif "presentations" in args and "get" in args:
                action = "get_presentation"
        elif service == "calendar":
            if "events" in args and "list" in args:
                action = "list_events"
            elif "events" in args and "insert" in args:
                action = "create_event"
            elif "events" in args and "get" in args:
                action = "get_event"
            elif "events" in args and "delete" in args:
                action = "delete_event"
            elif "events" in args and "patch" in args:
                action = "update_event"
        elif service == "chat":
            if "spaces" in args and "list" in args:
                action = "list_spaces"
            elif "spaces" in args and "messages" in args and "create" in args:
                action = "send_message"
            elif "spaces" in args and "messages" in args and "list" in args:
                action = "list_messages"
        elif service == "keep":
            if "notes" in args and "list" in args:
                action = "list_notes"
            elif "notes" in args and "create" in args:
                action = "create_note"
        elif service == "meet":
            if "spaces" in args and "list" in args:
                action = "list_conferences"
            elif "spaces" in args and "get" in args:
                action = "get_conference"
            elif "spaces" in args and "create" in args:
                action = "create_meeting"
        elif service == "contacts":
            if "people" in args and "list" in args:
                action = "list_contacts"
            elif "people" in args and "get" in args:
                action = "get_person"
        elif service == "tasks":
            if any(a.lower() == "tasklists" for a in args) and "list" in args:
                action = "list_tasklists"
            elif "tasks" in args and "list" in args:
                action = "list_tasks"
            elif "tasks" in args and "insert" in args:
                action = "create_task"
            elif "tasks" in args and "get" in args:
                action = "get_task"
            elif "tasks" in args and "patch" in args:
                action = "update_task"
            elif "tasks" in args and "delete" in args:
                action = "delete_task"
        return action

    @staticmethod
    def _parse_params(args: list[str]) -> dict[str, Any]:
        params: dict[str, Any] = {}
        i = 2
        while i < len(args):
            if args[i] in ("--params", "--json") and i + 1 < len(args):
                try:
                    params.update(json.loads(args[i + 1]))
                except Exception:
                    pass
                i += 2
            elif args[i] == "--upload" and i + 1 < len(args):
                params["file_path"] = args[i + 1]
                i += 2
            elif args[i].startswith("--") and i + 1 < len(args) and not args[i + 1].startswith("--"):
                key = args[i][2:]
                params[key] = args[i + 1]
                i += 2
            else:
                i += 1
        return params

    def _handle_service(self, service: str, action: str, params: dict[str, Any], args: list[str]) -> Any:
        if service == "gmail":
            return self._handle_gmail(action, params)
        if service == "sheets":
            return self._handle_sheets(action, params)
        if service == "drive":
            return self._handle_drive(action, params, args)
        if service == "docs":
            return self._handle_docs(action, params)
        if service == "slides":
            return self._handle_slides(action, params)
        if service == "calendar":
            return self._handle_calendar(action, params)
        if service == "chat":
            return self._handle_chat(action, params)
        if service == "keep":
            return self._handle_keep(action, params)
        if service == "meet":
            return self._handle_meet(action, params)
        if service == "contacts":
            return self._handle_contacts(action, params)
        if service == "tasks":
            return self._handle_tasks(action, params)
        return {}

    # ------------------------------------------------------------------
    # Service handlers
    # ------------------------------------------------------------------

    def _handle_gmail(self, action: str, params: dict[str, Any]) -> Any:
        if action == "list_messages":
            return {
                "messages": [
                    {"id": "msg1", "threadId": "th1", "snippet": "Unread message 1"},
                    {"id": "msg2", "threadId": "th2", "snippet": "Unread message 2"},
                    {"id": "msg3", "threadId": "th3", "snippet": "Invoice message"},
                ]
            }
        if action == "get_message":
            return {
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
                },
                "body_text": "Full message content about invoice 100$",
            }
        if action == "send_message":
            return {"id": "sent_msg_123", "threadId": "sent_th_123", "labelIds": ["SENT"]}
        if action == "trash_message":
            return {"id": params.get("id", "msg1"), "labelIds": ["TRASH"]}
        if action == "delete_message":
            return {}
        return {}

    def _handle_sheets(self, action: str, params: dict[str, Any]) -> Any:
        if action == "create_spreadsheet":
            return {
                "spreadsheetId": "fake_sheet_id_123",
                "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/fake_sheet_id_123",
                "sheets": [{"properties": {"title": "Sheet1"}}],
            }
        if action == "append_values":
            return {
                "spreadsheetId": params.get("spreadsheet_id", "fake_sheet_id_123"),
                "updates": {"updatedRows": 3},
            }
        if action == "get_values":
            return {"values": [["Row1", "Data1"], ["Row2", "Data2"]]}
        if action == "clear_values":
            return {"spreadsheetId": params.get("spreadsheetId", "fake_sheet_id_123"), "clearedRange": params.get("range", "Sheet1!A1:Z100")}
        if action == "get_spreadsheet":
            return {
                "spreadsheetId": params.get("spreadsheetId", "fake_sheet_id_123"),
                "properties": {"title": "Test Sheet"},
                "sheets": [{"properties": {"title": "Sheet1"}, "data": {}}],
            }
        return {}

    def _handle_drive(self, action: str, params: dict[str, Any], args: list[str]) -> Any:
        # list_files
        if action == "list_files":
            q = params.get("q", "")
            files = list(_FAKE_DRIVE_FILES)
            if q:
                # 1. Try to extract specific field filters
                name_filters = re.findall(r"name\s+contains\s+['\"](.+?)['\"]", q, re.IGNORECASE)
                mime_filters = re.findall(r"mimeType\s*=\s*['\"](.+?)['\"]", q, re.IGNORECASE)

                # 2. Fallback to generic quoted terms if no field-specific filters found
                if not name_filters and not mime_filters:
                    generic_terms = re.findall(r"['\"](.+?)['\"]", q)
                    if generic_terms:
                        name_filters = generic_terms

                if name_filters or mime_filters:
                    filtered = []
                    for f in files:
                        name_match = True
                        if name_filters:
                            # ALL name terms must match (for multi-word queries)
                            name_match = all(t.lower() in f["name"].lower() for t in name_filters)

                        mime_match = True
                        if mime_filters:
                            # ANY mime term must match (usually only one)
                            mime_match = any(t.lower() == f["mimeType"].lower() for t in mime_filters)

                        if name_match and mime_match:
                            filtered.append(f)
                    files = filtered
            return {"files": files, "nextPageToken": None}

        # upload_file
        if action == "upload_file":
            self._upload_counter += 1
            upload_id = f"upload_{self._upload_counter}"
            name = params.get("name") or "Uploaded File"
            # Try to infer mime from the --upload-content-type flag or name
            mime = "application/octet-stream"
            for i, arg in enumerate(args):
                if arg == "--upload-content-type" and i + 1 < len(args):
                    mime = args[i + 1]
                    break
            if mime == "application/octet-stream":
                for ext, known_mime in {
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".mp3": "audio/mpeg",
                    ".mp4": "video/mp4",
                    ".mkv": "video/x-matroska",
                    ".pdf": "application/pdf",
                    ".txt": "text/plain",
                    ".csv": "text/csv",
                    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                }.items():
                    if name.lower().endswith(ext):
                        mime = known_mime
                        break
            file_meta = {"id": upload_id, "name": name, "mimeType": mime, "webViewLink": f"https://drive.google.com/file/d/{upload_id}/view"}
            self._created_files.append(file_meta)
            return file_meta

        # create_file_or_folder — disambiguate via mimeType in payload
        if action == "create_file_or_folder":
            payload_mime = params.get("mimeType", "")
            name = params.get("name", "Untitled")
            if payload_mime == "application/vnd.google-apps.folder":
                fid = f"folder_{len(self._folders) + 1}"
                self._folders[fid] = {"id": fid, "name": name, "mimeType": payload_mime}
                return {"id": fid, "name": name, "mimeType": payload_mime}
            # create_file
            fid = f"created_{len(self._created_files) + 1}"
            mime = payload_mime or "application/vnd.google-apps.document"
            file_meta = {"id": fid, "name": name, "mimeType": mime, "webViewLink": f"https://drive.google.com/file/d/{fid}/view"}
            self._created_files.append(file_meta)
            return file_meta

        # get_file / export_file
        if action in ("get_file", "export_file"):
            file_id = params.get("fileId") or params.get("file_id", "file123")
            file_info = self._find_file(file_id) or self._find_file("doc_abc_1")

            if not file_info:
                return {"error": f"File {file_id} not found"}

            mime_type = file_info.get("mimeType", "application/octet-stream")
            is_binary = mime_type.startswith(("image/", "audio/", "video/", "application/pdf"))
            ext = ".bin"
            if mime_type == "application/pdf":
                ext = ".pdf"
            elif mime_type == "image/png":
                ext = ".png"
            elif mime_type == "image/jpeg":
                ext = ".jpg"
            elif mime_type == "audio/mpeg":
                ext = ".mp3"
            elif mime_type == "video/mp4":
                ext = ".mp4"
            elif mime_type == "video/x-matroska":
                ext = ".mkv"
            elif mime_type == "text/plain":
                ext = ".txt"
            elif mime_type == "text/csv":
                ext = ".csv"
            elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                ext = ".docx"
            elif mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
                ext = ".xlsx"
            elif mime_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
                ext = ".pptx"

            saved_path = f"scratch/exports/download_{file_id}{ext}"
            result: dict[str, Any] = {
                "id": file_info["id"],
                "name": file_info["name"],
                "mimeType": mime_type,
                "saved_file": saved_path,
            }
            if is_binary:
                result["content_bytes_base64"] = "ZmFrZSBiaW5hcnkgY29udGVudA=="  # "fake binary content"
            else:
                result["content"] = f"Fake content of exported file: extracted data 42 from {file_info['name']}"
            return result

        # delete_file
        if action == "delete_file":
            fid = params.get("fileId") or params.get("file_id", "file123")
            self._trashed_files.discard(fid)
            return {}

        # update_file (covers move_to_trash, rename, metadata update, move)
        if action == "update_file":
            fid = params.get("fileId") or params.get("file_id", "")
            file_info = self._find_file(fid)
            if not file_info:
                file_info = {"id": fid, "name": "Unknown", "mimeType": "application/octet-stream"}
            # Trash
            if params.get("trashed") is True:
                self._trashed_files.add(fid)
                return {"id": fid, "name": file_info["name"], "trashed": True}
            # Rename / metadata
            new_name = params.get("name")
            if new_name:
                file_info = {**file_info, "name": new_name}
            new_desc = params.get("description")
            if new_desc:
                file_info = {**file_info, "description": new_desc}
            # Move (addParents/removeParents simulated)
            if params.get("addParents"):
                file_info = {**file_info, "parents": [params["addParents"]]}
            return file_info

        # copy_file
        if action == "copy_file":
            fid = params.get("fileId") or params.get("file_id", "file123")
            orig = self._find_file(fid) or {"id": fid, "name": "Original", "mimeType": "application/octet-stream"}
            copy_name = params.get("name") or f"Copy of {orig['name']}"
            copy_id = f"copy_{fid}"
            return {"id": copy_id, "name": copy_name, "mimeType": orig["mimeType"], "webViewLink": f"https://drive.google.com/file/d/{copy_id}/view"}

        return {}

    def _handle_docs(self, action: str, params: dict[str, Any]) -> Any:
        if action == "create_document":
            return {"documentId": "fake_doc_id_456", "title": params.get("title", "Untitled Doc"), "documentUrl": "https://docs.google.com/document/d/fake_doc_id_456"}
        if action == "batch_update":
            return {"documentId": params.get("documentId", "fake_doc_id_456"), "body": {"content": []}}
        return {}

    def _handle_slides(self, action: str, params: dict[str, Any]) -> Any:
        if action == "create_presentation":
            return {"presentationId": "fake_slide_id_789", "title": params.get("title", "Untitled Presentation"), "presentationUrl": "https://docs.google.com/presentation/d/fake_slide_id_789"}
        if action == "get_presentation":
            return {"presentationId": params.get("presentationId", "fake_slide_id_789"), "title": "Test Presentation", "slides": []}
        return {}

    def _handle_calendar(self, action: str, params: dict[str, Any]) -> Any:
        if action == "list_events":
            return {"items": [{"id": "evt1", "summary": "Team Sync", "start": {"dateTime": "2026-04-15T10:00:00Z"}, "end": {"dateTime": "2026-04-15T11:00:00Z"}}]}
        if action == "create_event":
            return {"id": "evt_new_1", "summary": params.get("summary", "New Event"), "htmlLink": "https://calendar.google.com/event?id=evt_new_1"}
        if action == "get_event":
            return {"id": params.get("eventId", "evt1"), "summary": "Team Sync", "start": {"dateTime": "2026-04-15T10:00:00Z"}, "end": {"dateTime": "2026-04-15T11:00:00Z"}}
        if action == "delete_event":
            return {}
        if action == "update_event":
            return {"id": params.get("eventId", "evt1"), "summary": params.get("summary", "Updated Event")}
        return {}

    def _handle_chat(self, action: str, params: dict[str, Any]) -> Any:
        if action == "list_spaces":
            return {"spaces": [{"name": "spaces/AAAA1234", "displayName": "Engineering", "type": "ROOM"}]}
        if action == "send_message":
            return {"name": f"spaces/AAAA1234/messages/{self.call_count}", "text": params.get("text", "Hello")}
        if action == "list_messages":
            return {"messages": [{"name": "spaces/AAAA1234/messages/1", "text": "Hi team", "sender": {"displayName": "Alice"}, "createTime": "2026-04-15T10:00:00Z"}]}
        return {}

    def _handle_keep(self, action: str, params: dict[str, Any]) -> Any:
        if action == "list_notes":
            return {"notes": [{"name": "notes/1", "title": "Shopping", "body": "Milk, Eggs"}]}
        if action == "create_note":
            return {"name": "notes/new_1", "title": params.get("title", "New Note"), "body": params.get("body", "")}
        return {}

    def _handle_meet(self, action: str, params: dict[str, Any]) -> Any:
        if action == "list_conferences":
            return {"spaces": [{"name": "spaces/MEET123", "meetingUri": "https://meet.google.com/abc-defg-hij", "activeConference": False}]}
        if action == "get_conference":
            return {"name": params.get("name", "spaces/MEET123"), "meetingUri": "https://meet.google.com/abc-defg-hij", "activeConference": False}
        if action == "create_meeting":
            return {"name": f"spaces/NEWMEET{self.call_count}", "meetingUri": f"https://meet.google.com/new-{self.call_count}"}
        return {}

    def _handle_contacts(self, action: str, params: dict[str, Any]) -> Any:
        if action == "list_contacts":
            return {"connections": [{"names": [{"displayName": "Alice Smith"}], "emailAddresses": [{"value": "alice@example.com"}], "phoneNumbers": [{"value": "+1-555-0100"}]}]}
        if action == "get_person":
            return {"resourceName": params.get("resourceName", "people/c123"), "names": [{"displayName": "Alice Smith"}], "emailAddresses": [{"value": "alice@example.com"}]}
        return {}

    def _handle_tasks(self, action: str, params: dict[str, Any]) -> Any:
        if action == "list_tasklists":
            return {"items": [{"id": "tl1", "title": "My Tasks", "updated": "2026-04-15T10:00:00Z"}]}
        if action == "list_tasks":
            return {"items": [{"id": "t1", "title": "Buy milk", "status": "needsAction", "due": "2026-04-16"}]}
        if action == "create_task":
            return {"id": f"t_new_{self.call_count}", "title": params.get("title", "New Task"), "status": "needsAction"}
        if action == "get_task":
            return {"id": params.get("task_id", "t1"), "title": "Buy milk", "status": "needsAction", "updated": "2026-04-15T10:00:00Z", "due": "2026-04-16", "notes": ""}
        if action == "update_task":
            return {"id": params.get("task_id", "t1"), "title": params.get("title", "Updated Task"), "status": params.get("status", "needsAction")}
        if action == "delete_task":
            return {"id": params.get("task_id", "t1")}
        return {}

    @staticmethod
    def _persist_file(output: dict[str, Any]) -> None:
        saved = output.get("saved_file")
        if not saved:
            return
        try:
            p = Path(saved)
            p.parent.mkdir(parents=True, exist_ok=True)
            if "content_bytes_base64" in output:
                import base64
                p.write_bytes(base64.b64decode(output["content_bytes_base64"]))
            else:
                p.write_text(output.get("content", ""), encoding="utf-8")
        except Exception:
            pass
