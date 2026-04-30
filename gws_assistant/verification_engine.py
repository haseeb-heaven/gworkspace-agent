import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class VerificationError(Exception):
    def __init__(self, tool: str, reason: str, field: str | None = None, severity: str = "ERROR"):
        self.tool = tool
        self.reason = reason
        self.field = field
        self.severity = severity
        msg = f"[{severity}] {tool} verification failed: {reason}"
        if field:
            msg += f" (field: {field})"
        super().__init__(msg)


class VerificationEngine:
    PLACEHOLDER_REGEXES = [
        re.compile(r"^<.*?>$"),
        re.compile(r"^\[.*?\]$"),
        re.compile(r"^{{.*?}}$"),
        re.compile(r"^{.*?}$"),
    ]

    EXACT_PLACEHOLDERS = {
        "none", "null", "n/a", "na", "undefined",
        "todo", "fixme", "placeholder", "example", "sample", "dummy",
        "your_value", "insert_here", "replace_me", "changeme", "default",
        "fake", "mock", "temporary", "tbd", "missing"
    }

    NUMERIC_PLACEHOLDERS = {"0000", "1234", "9999", "00000000"}

    EXACT_EMAILS = {"noreply@example.com"}

    EMAIL_PLACEHOLDER_DOMAINS = ["@test.com"]

    SPECIAL_CHARS_ONLY = re.compile(r"^[^a-zA-Z0-9\s]+$")

    @classmethod
    def verify(cls, tool_name: str, params: dict, result: Any) -> None:
        if not isinstance(params, dict):
            params = {}

        logger.debug(f"Verifying {tool_name} with params keys {list(params.keys())}")

        try:
            cls.verify_params(tool_name, params)
        except VerificationError as e:
            if e.severity == "WARNING":
                logger.warning(str(e))
            else:
                logger.error(f"verify_params failed for {tool_name}: {e}")
                raise

        try:
            cls.verify_result(tool_name, params, result)
        except VerificationError as e:
            if e.severity == "WARNING":
                logger.warning(str(e))
            else:
                logger.error(f"verify_result failed for {tool_name}: {e}")
                raise

        try:
            cls.verify_attachment_sent(params, result)
        except VerificationError as e:
            if e.severity == "WARNING":
                logger.warning(str(e))
            else:
                logger.error(f"verify_attachment_sent failed for {tool_name}: {e}")
                raise

        try:
            cls.verify_document_not_empty(tool_name, params, result)
        except VerificationError as e:
            if e.severity == "WARNING":
                logger.warning(str(e))
            else:
                logger.error(f"verify_document_not_empty failed for {tool_name}: {e}")
                raise

    @classmethod
    def verify_params(cls, tool_name: str, params: dict) -> None:
        # tool_name is expected to be "service_action"
        if "_" in tool_name:
            service, action = tool_name.split("_", 1)
        else:
            service = tool_name
            action = tool_name

        # CATEGORY 2 - GMAIL
        if service == "gmail" or "message" in action or "email" in action or "send" in action:
            if "send" in tool_name or "reply" in tool_name or "forward" in tool_name:
                to = params.get("to") or params.get("to_email")
                if to is None or to == [] or cls._is_placeholder(str(to)) or not cls._is_valid_email(str(to)):
                    raise VerificationError(tool_name, "Invalid 'to' email address", "to")

                for field in ["cc", "bcc"]:
                    val = params.get(field)
                    if val:
                        if isinstance(val, list):
                            for v in val:
                                if not cls._is_valid_email(str(v)):
                                    raise VerificationError(tool_name, f"Invalid email in {field}", field)
                        elif isinstance(val, str):
                            if not cls._is_valid_email(val):
                                raise VerificationError(tool_name, f"Invalid {field} email address", field)

                subject = params.get("subject")
                if "reply" not in tool_name and "forward" not in tool_name:  # Reply/Forward might not need subject
                    if not subject or cls._is_placeholder(str(subject)) or len(str(subject).strip()) < 2:
                        raise VerificationError(
                            tool_name, "Subject must not be empty or placeholder, min 2 chars", "subject"
                        )

                body = params.get("body")
                if not body or cls._is_placeholder(str(body)) or len(str(body).strip()) < 5:
                    raise VerificationError(tool_name, "Body must not be empty or placeholder, min 5 chars", "body")

            attachments = params.get("attachments")
            if attachments:
                if not isinstance(attachments, list):
                    attachments = [attachments]
                for att in attachments:
                    if isinstance(att, dict):
                        file_id = att.get("file_id")
                        file_path = att.get("file_path")
                        if (
                            (file_id is None and file_path is None)
                            or (file_id is not None and cls._is_placeholder(str(file_id)))
                            or (file_path is not None and cls._is_placeholder(str(file_path)))
                        ):
                            raise VerificationError(
                                tool_name, "Attachment must have valid file_id or file_path", "attachments"
                            )
                        filename = att.get("filename")
                        if not filename or cls._is_placeholder(str(filename)):
                            raise VerificationError(tool_name, "Attachment must have filename", "attachments")
                        mime_type = att.get("mime_type")
                        if not mime_type or not str(mime_type).strip():
                            raise VerificationError(tool_name, "Attachment must have mime_type", "attachments")

            if "reply" in tool_name:
                thread_id = params.get("thread_id")
                if not thread_id or cls._is_placeholder(str(thread_id)):
                    raise VerificationError(tool_name, "Thread ID required for reply", "thread_id")

            if "forward" in tool_name or "reply" in tool_name:
                message_id = params.get("message_id")
                if not message_id or cls._is_placeholder(str(message_id)):
                    raise VerificationError(tool_name, "Message ID required for forward/reply", "message_id")

        # CATEGORY 3 - GOOGLE DRIVE / DOCUMENT
        if service in ("drive", "docs") or "document" in action or "file" in action or "drive" in action:
            if "create" in tool_name or "copy" in tool_name:
                title = params.get("title") or params.get("name") or params.get("folder_name")
                if not title or cls._is_placeholder(str(title)) or len(str(title).strip()) < 1:
                    print(f"DEBUG: Document title required failed for tool '{tool_name}' with params: {params}")
                    raise VerificationError(tool_name, "Document title required", "title")

            content = params.get("content")
            if content is not None:
                if str(content).strip() == "":
                    raise VerificationError(tool_name, "Document created empty", "content", severity="WARNING")

            for id_field in ["file_id", "document_id", "spreadsheet_id"]:
                file_id = params.get(id_field)
                if file_id is not None:
                    if cls._is_placeholder(str(file_id)) or not cls._is_valid_drive_id(str(file_id)):
                        raise VerificationError(tool_name, f"Invalid {id_field}", id_field)

            folder_id = params.get("folder_id")
            if folder_id is not None:
                if cls._is_placeholder(str(folder_id)):
                    raise VerificationError(tool_name, "Invalid folder_id", "folder_id")

            mime_type = params.get("mime_type")
            if mime_type is not None:
                if "/" not in str(mime_type):
                    raise VerificationError(tool_name, "Invalid mime_type", "mime_type")

            parent_id = params.get("parent_id")
            if parent_id is not None:
                if cls._is_placeholder(str(parent_id)):
                    raise VerificationError(tool_name, "Invalid parent_id", "parent_id")

        # CATEGORY 4 - GOOGLE SHEETS
        if service in ("sheets", "spreadsheet") or "sheet" in action or "spreadsheet" in action or "values" in action:
            spreadsheet_id = params.get("spreadsheet_id")
            if spreadsheet_id is not None:
                if cls._is_placeholder(str(spreadsheet_id)) or not cls._is_valid_drive_id(str(spreadsheet_id)):
                    raise VerificationError(tool_name, "Invalid spreadsheet_id", "spreadsheet_id")

            sheet_range = params.get("range")
            if sheet_range is not None:
                if not str(sheet_range).strip():
                    raise VerificationError(tool_name, "Range cannot be empty", "range")
                # Updated pattern to support single cells like A1, Sheet1!A1, ranges like A1:B2, and $last_spreadsheet_id, {{message_id}}
                range_pattern = re.compile(
                    r"^(?:(?:'[^']*'|[a-zA-Z0-9_ ]+)!)?[a-zA-Z]+[0-9]*(?::[a-zA-Z]+[0-9]*)?$|^(?:[$<\[{].*)$"
                )
                if not range_pattern.match(str(sheet_range)):
                    raise VerificationError(tool_name, "Invalid range format", "range")

            values = params.get("values")
            if "write" in tool_name or "append" in tool_name or values is not None:
                if values is None or values == [] or values == [[]]:
                    # Allow empty values for clear/delete/get
                    if all(x not in tool_name for x in ("clear", "delete", "get")):
                        raise VerificationError(tool_name, "Values cannot be empty", "values")

                # Check for placeholder in cells
                if isinstance(values, list):
                    for row in values:
                        if isinstance(row, list):
                            for cell in row:
                                if cell is not None and str(cell).strip() and cls._is_placeholder(str(cell)):
                                    print(f"DEBUG: Placeholder found in values: '{cell}', full params: {params}")
                                    raise VerificationError(tool_name, f"Placeholder found in values: {cell}", "values")

            sheet_name = params.get("sheet_name") or params.get("tab_name")
            if sheet_name is not None:
                if not str(sheet_name).strip():
                    raise VerificationError(tool_name, "Sheet name cannot be empty", "sheet_name")

        # CATEGORY 5 - GOOGLE CALENDAR
        if service == "calendar" or "event" in tool_name:
            if "create" in tool_name or "insert" in tool_name:
                summary = params.get("summary")
                if not summary or cls._is_placeholder(str(summary)) or len(str(summary).strip()) < 2:
                    raise VerificationError(tool_name, "Event summary required and min 2 chars", "summary")

                # Heuristic often provides start_date and start_time separately
                start = params.get("start") or params.get("start_date") or params.get("start_datetime")
                end = params.get("end") or params.get("end_date") or params.get("end_datetime")

                if not start or not cls._is_valid_iso8601(start):
                    # Relative strings like "tomorrow at 10am" are allowed as long as they aren't explicit placeholders
                    if cls._is_placeholder(str(start)):
                        raise VerificationError(tool_name, "Valid start date required", "start")

                if end and not cls._is_valid_iso8601(end):
                    if cls._is_placeholder(str(end)):
                        raise VerificationError(tool_name, "Valid end date required", "end")

                if start and end and cls._is_valid_iso8601(start) and cls._is_valid_iso8601(end):
                    if not cls._end_is_after_start(start, end):
                        raise VerificationError(tool_name, "End time must be after start time", "end")

            attendees = params.get("attendees")
            if attendees:
                if isinstance(attendees, list):
                    for att in attendees:
                        email = att.get("email") if isinstance(att, dict) else str(att)
                        if email and not cls._is_valid_email(email):
                            raise VerificationError(tool_name, "Invalid attendee email", "attendees")

            for field in ["location", "description"]:
                val = params.get(field)
                if val and cls._is_placeholder(str(val)):
                    raise VerificationError(tool_name, f"Placeholder found in {field}", field)

            event_id = params.get("event_id")
            if event_id is not None:
                if cls._is_placeholder(str(event_id)):
                    raise VerificationError(tool_name, "Invalid event_id", "event_id")

        # CATEGORY 6 - GOOGLE TASKS
        if service == "tasks" or "task" in tool_name:
            if "create" in tool_name or "insert" in tool_name:
                title = params.get("title")
                if not title or cls._is_placeholder(str(title)):
                    raise VerificationError(tool_name, "Task title required", "title")

            due = params.get("due")
            if due is not None:
                if not cls._is_valid_iso8601(str(due)):
                    raise VerificationError(tool_name, "Invalid due date format", "due")

            task_id = params.get("task_id")
            if task_id is not None:
                if cls._is_placeholder(str(task_id)):
                    raise VerificationError(tool_name, "Invalid task_id", "task_id")

            tasklist_id = params.get("tasklist_id")
            if tasklist_id is not None:
                if cls._is_placeholder(str(tasklist_id)):
                    raise VerificationError(tool_name, "Invalid tasklist_id", "tasklist_id")

        # CATEGORY 7 - GOOGLE CONTACTS
        if service == "contacts" or "contact" in tool_name:
            if "create" in tool_name:
                first_name = params.get("first_name")
                display_name = params.get("display_name")
                if not first_name and not display_name:
                    raise VerificationError(tool_name, "first_name or display_name required", "first_name")
                if first_name and cls._is_placeholder(str(first_name)):
                    raise VerificationError(tool_name, "Placeholder in first_name", "first_name")
                if display_name and cls._is_placeholder(str(display_name)):
                    raise VerificationError(tool_name, "Placeholder in display_name", "display_name")

            email = params.get("email")
            if email is not None:
                if not cls._is_valid_email(str(email)):
                    raise VerificationError(tool_name, "Invalid email", "email")

            phone = params.get("phone")
            if phone is not None:
                num = re.sub(r"\D", "", str(phone))
                if len(num) < 7:
                    raise VerificationError(tool_name, "Phone number too short", "phone")

            contact_id = params.get("contact_id")
            if contact_id is not None:
                if cls._is_placeholder(str(contact_id)):
                    raise VerificationError(tool_name, "Invalid contact_id", "contact_id")

    @classmethod
    def verify_result(cls, tool_name: str, params: dict, result: Any) -> None:
        # CATEGORY 8 - GENERAL
        if result is None:
            raise VerificationError(tool_name, "Result is None")

        if isinstance(result, dict):
            if not result:
                raise VerificationError(tool_name, "Result is an empty dict", severity="WARNING")

            if result.get("success") is False or result.get("ok") is False:
                raise VerificationError(tool_name, "Result contains success/ok: False")

            status = str(result.get("status", "")).lower()
            if status in ("error", "failed", "failure"):
                raise VerificationError(tool_name, f"Result status is {status}")

            try:
                code = int(result.get("code", 0))
                if code >= 400:
                    raise VerificationError(tool_name, f"Result contains HTTP error code {code}")
            except (ValueError, TypeError):
                pass

            for k, v in result.items():
                if k in ("id", "file_id", "message_id", "event_id") and v is None:
                    raise VerificationError(tool_name, f"ID field '{k}' is None", k)
                if isinstance(v, str) and (k.endswith("Url") or k.endswith("Link")):
                    if not v.startswith("http"):
                        raise VerificationError(tool_name, f"URL field '{k}' does not start with http", k)

            if "error" in result and result["error"]:
                raise VerificationError(tool_name, "Result contains error key with truthy value", "error")

            # Detect if AI returned PARAMS back as RESULT
            if len(params) > 0 and len(result) > 0:
                if all(k in result and result[k] == v for k, v in params.items()):
                    if len(result) == len(params):
                        raise VerificationError(tool_name, "Result is exactly the same as params", severity="WARNING")

            if "create" in tool_name.lower() or "insert" in tool_name.lower():
                has_id = any(
                    k in result
                    for k in [
                        "id",
                        "documentId",
                        "spreadsheetId",
                        "fileId",
                        "messageId",
                        "resourceName",
                        "threadId",
                        "name",
                    ]
                )
                if not has_id:
                    raise VerificationError(tool_name, "Create operation result missing ID")

        parts = tool_name.split("_")
        service = parts[0]
        action = tool_name

        # CATEGORY 2 - GMAIL
        if service == "gmail" or "message" in action or "email" in action or "send" in action:
            if isinstance(result, dict):
                # For lists, messages might be under a list
                if "list" in tool_name and ("messages" in result or "threads" in result):
                    pass
                else:
                    msg_id = result.get("id") or result.get("messageId")
                    if (
                        not msg_id
                        and "draft" not in tool_name
                        and "send" not in tool_name
                        and "delete" not in tool_name
                        and "trash" not in tool_name
                    ):
                        raise VerificationError(tool_name, "Result missing id or message_id")

                if "send" in tool_name:
                    if not result.get("labelIds") and not result.get("threadId"):
                        raise VerificationError(tool_name, "Send result missing labelIds or threadId")

        # CATEGORY 3 - DRIVE / DOCS
        if service in ("drive", "docs") or "document" in action or "file" in action or "drive" in action:
            if isinstance(result, dict):
                if (
                    "list" not in action
                    and "export" not in action
                    and "files" not in result
                    and "saved_file" not in result
                ):
                    doc_id = result.get("id") or result.get("documentId")
                    if not doc_id and "tabs" in result and isinstance(result["tabs"], list) and len(result["tabs"]) > 0:
                        # Tab-based document. Extract tabId as a fallback if documentId is missing at root
                        tab_props = result["tabs"][0].get("tabProperties", {})
                        doc_id = tab_props.get("tabId")

                    if not doc_id or cls._is_placeholder(str(doc_id)) or len(str(doc_id)) < 1:
                        raise VerificationError(tool_name, "Result missing valid id", "id")

        # CATEGORY 4 - SHEETS
        if service in ("sheets", "spreadsheet") or "sheet" in action or "spreadsheet" in action or "values" in action:
            if isinstance(result, dict):
                if "create" in tool_name:
                    if not result.get("spreadsheetId") and not result.get("id"):
                        raise VerificationError(tool_name, "Create sheet missing spreadsheetId")

        # CATEGORY 5 - GOOGLE CALENDAR
        if service == "calendar" or "event" in tool_name:
            if isinstance(result, dict):
                if result.get("status") == "cancelled":
                    raise VerificationError(tool_name, "Event status cancelled right after creation", "status")

        # CATEGORY 6 - TASKS
        if service == "tasks" or "task" in tool_name:
            if isinstance(result, dict):
                task_status = result.get("status")
                if task_status and task_status not in ("needsAction", "completed"):
                    raise VerificationError(tool_name, f"Invalid task status {task_status}", "status")

    @classmethod
    def verify_attachment_sent(cls, params: dict, result: Any) -> None:
        attachments = params.get("attachments")
        if attachments and isinstance(result, dict):
            if not isinstance(attachments, list):
                attachments = [attachments]
            if len(attachments) > 0:
                # Basic check: result should have something indicating attachments were handled
                payload = result.get("payload", {})
                parts = payload.get("parts", []) if isinstance(payload, dict) else []
                if not parts:
                    parts = result.get("attachments", [])

                # If no parts/attachments are found in the result, it's a failure.
                if not parts:
                    raise VerificationError(
                        "verify_attachment", "Attachment declared in params but not confirmed in result"
                    )

    @classmethod
    def verify_document_not_empty(cls, tool_name: str, params: dict, result: Any) -> None:
        if tool_name in ("create_document", "append_values", "create_spreadsheet", "write_sheet", "write_values"):
            content = params.get("content")
            values = params.get("values")
            if content is not None and str(content).strip() == "":
                raise VerificationError(tool_name, "Operation created/wrote an empty document or sheet", "content")
            if values is not None and (values == [] or values == [[]]):
                raise VerificationError(tool_name, "Operation created/wrote an empty document or sheet", "values")

    @classmethod
    def _is_placeholder(cls, value: str) -> bool:
        if value is None:
            return False
        val_str = str(value).strip()
        if not val_str:
            return True
        val_lower = val_str.lower()
        if val_lower in cls.EXACT_PLACEHOLDERS:
            return True
        if val_str in cls.NUMERIC_PLACEHOLDERS:
            return True
        if val_lower in cls.EXACT_EMAILS:
            return True
        for domain in cls.EMAIL_PLACEHOLDER_DOMAINS:
            if val_lower.endswith(domain):
                return True
        for pattern in cls.PLACEHOLDER_REGEXES:
            if pattern.match(val_str):
                return True
        if cls.SPECIAL_CHARS_ONLY.match(val_str):
            return True
        return False

    @classmethod
    def _is_valid_email(cls, value: str) -> bool:
        if cls._is_placeholder(value):
            return False
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(value)))

    @classmethod
    def _is_valid_iso8601(cls, value: Any) -> bool:
        if isinstance(value, dict):
            value = value.get("dateTime") or value.get("date")
        if not value:
            return False
        val_str = str(value)
        return bool(re.match(r"^\d{4}-\d{2}-\d{2}", val_str))

    @classmethod
    def _is_valid_url(cls, value: str) -> bool:
        return str(value).startswith("http")

    @classmethod
    def _is_valid_drive_id(cls, value: str) -> bool:
        val_str = str(value)
        if any(
            val_str.startswith(prefix)
            for prefix in ["sheet-", "doc-", "folder-", "file-", "evt-", "sent-", "m", "t", "$", "{{"]
        ):
            return True
        return bool(re.match(r"^[a-zA-Z0-9_-]+$", val_str)) and len(val_str) >= 1

    @classmethod
    def _end_is_after_start(cls, start: Any, end: Any) -> bool:
        from datetime import datetime

        def extract_date(v):
            if isinstance(v, dict):
                return v.get("dateTime") or v.get("date")
            return v

        s = extract_date(start)
        e = extract_date(end)
        if not s or not e:
            return True
        try:
            s_dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
            e_dt = datetime.fromisoformat(str(e).replace("Z", "+00:00"))
            return e_dt > s_dt
        except Exception:
            return str(e) > str(s)
