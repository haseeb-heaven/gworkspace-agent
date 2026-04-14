"""Action validation and command planning."""

from __future__ import annotations

import base64
import email as email_lib
import email.mime.application
import email.mime.multipart
import email.mime.text
import json
import logging
import os
import re
import subprocess
import tempfile
from datetime import date, datetime, timedelta
from typing import Any

from .drive_query_builder import sanitize_drive_query
from .exceptions import ValidationError, UnsupportedServiceError
from .gmail_query_builder import sanitize_gmail_query
from .models import ActionSpec, ParameterSpec
from .service_catalog import SERVICES, normalize_service, supported_services


_UNSUPPORTED_STUB_SERVICES = frozenset({"analytics", "bigquery"})

# Matches a raw Google Drive file ID (alphanumeric + hyphens/underscores, 25-60 chars).
# Drive file IDs look like: 1-A9SUqwDnbUE51VZ7FbAh8i-wUGz8Cqw9jCIUw0nMjo
_DRIVE_FILE_ID_RE = re.compile(r'^[A-Za-z0-9_\-]{25,60}$')

# MIME type used when exporting Google Docs to PDF for attachment.
_GDOC_EXPORT_MIME = "application/pdf"

# ---------------------------------------------------------------------------
# Date / time helpers
# ---------------------------------------------------------------------------

_WEEKDAY_NAMES = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

# ISO-8601 date pattern  YYYY-MM-DD
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Loose time pattern — matches "10 AM", "10:30 AM", "14:00", "9pm", etc.
_TIME_RE = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*([ap]m)?\b",
    re.IGNORECASE,
)


def _resolve_date_expression(raw: str) -> str:
    """Resolve a relative or absolute date string to YYYY-MM-DD.

    Handles:
      - ISO dates already in YYYY-MM-DD format  → returned as-is
      - "today"                                 → date.today()
      - "tomorrow"                              → date.today() + 1 day
      - "yesterday"                             → date.today() - 1 day
      - "next <weekday>"                        → next occurrence of that weekday
      - "<weekday>"                             → nearest future occurrence
      - Anything else                           → returned as-is (LLM supplied a literal)
    """
    val = raw.strip().lower()

    if _ISO_DATE_RE.match(raw.strip()):
        return raw.strip()

    today = date.today()

    if val == "today":
        return today.isoformat()

    if val in ("tomorrow", "tmrw", "tmr"):
        return (today + timedelta(days=1)).isoformat()

    if val == "yesterday":
        return (today - timedelta(days=1)).isoformat()

    # "next monday" / "next friday" etc.
    next_prefix = val.startswith("next ")
    check_val   = val[5:] if next_prefix else val

    if check_val in _WEEKDAY_NAMES:
        target_wd = _WEEKDAY_NAMES[check_val]
        days_ahead = (target_wd - today.weekday()) % 7
        # "next X" always means at least 7 days from now even if today is X
        if next_prefix and days_ahead == 0:
            days_ahead = 7
        elif days_ahead == 0:
            days_ahead = 7  # bare weekday name that matches today → next week
        return (today + timedelta(days=days_ahead)).isoformat()

    # Fallback — return as-is; the LLM may have already supplied an ISO date
    # embedded inside a longer string like "2026-04-14T10:00:00".
    return raw.strip().split("T")[0][:10]


def _parse_time_to_hhmm(raw: str) -> tuple[int, int] | None:
    """Extract (hour_24, minute) from a loose time string.  Returns None if unparseable."""
    m = _TIME_RE.search(raw.strip())
    if not m:
        return None
    hour   = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0
    ampm   = (m.group(3) or "").lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute


class CommandPlanner:
    """Validates service/action and builds gws command arguments."""

    def list_services(self) -> list[str]:
        return supported_services()

    def list_actions(self, service: str) -> list[ActionSpec]:
        service_key = normalize_service(service)
        if not service_key or service_key not in SERVICES:
            raise ValidationError(f"Unsupported service: {service}")
        return list(SERVICES[service_key].actions.values())

    def ensure_service(self, service: str | None) -> str:
        normalized = normalize_service(service)
        if not normalized:
            raise ValidationError(
                f"Unsupported or missing service. Supported services: {', '.join(self.list_services())}"
            )
        return normalized

    def ensure_action(self, service: str, action: str | None) -> str:
        if not action:
            raise ValidationError("Action is required.")
        service_key = self.ensure_service(service)
        if action not in SERVICES[service_key].actions:
            available = ", ".join(sorted(SERVICES[service_key].actions.keys()))
            raise ValidationError(f"Unsupported action '{action}' for {service_key}. Available: {available}")
        return action

    def required_parameters(self, service: str, action: str) -> tuple[ParameterSpec, ...]:
        service_key = self.ensure_service(service)
        action_key = self.ensure_action(service_key, action)
        return SERVICES[service_key].actions[action_key].parameters

    def build_command(self, service: str, action: str, parameters: dict[str, Any]) -> list[str]:
        if str(service).lower() in _UNSUPPORTED_STUB_SERVICES:
            raise UnsupportedServiceError(f"No command builder for service: {service}")

        service_key = self.ensure_service(service)
        action_key = self.ensure_action(service_key, action)
        params = parameters or {}

        if service_key == "drive":    return self._build_drive_command(action_key, params)
        if service_key == "sheets":   return self._build_sheets_command(action_key, params)
        if service_key == "gmail":    return self._build_gmail_command(action_key, params)
        if service_key == "calendar": return self._build_calendar_command(action_key, params)
        if service_key == "docs":     return self._build_docs_command(action_key, params)
        if service_key == "slides":   return self._build_slides_command(action_key, params)
        if service_key == "contacts": return self._build_contacts_command(action_key, params)
        if service_key == "chat":     return self._build_chat_command(action_key, params)
        if service_key == "meet":     return self._build_meet_command(action_key, params)
        if service_key == "search":   return self._build_search_command(action_key, params)
        if service_key == "admin":    return self._build_admin_command(action_key, params)
        if service_key == "forms":    return self._build_forms_command(action_key, params)
        if service_key in ("code", "computation"): return [service_key, action_key, "internal"]
        raise ValidationError(f"No command builder for service: {service_key}")

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _build_search_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "web_search":
            query = self._required_text(params, "query")
            return ["search", "web", "search", "--params", json.dumps({"query": query}, ensure_ascii=True)]
        raise ValidationError(f"Unsupported search action: {action}")

    # ------------------------------------------------------------------
    # Drive
    # ------------------------------------------------------------------

    def _build_drive_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_files":
            page_size = self._safe_positive_int(params.get("page_size"), default=10)
            raw_query = str(params.get("q") or "").strip()
            request_params: dict[str, Any] = {
                "pageSize": page_size,
                "fields": "files(id,name,mimeType,modifiedTime,webViewLink,owners(displayName,emailAddress)),nextPageToken",
            }
            if raw_query:
                # If the query specifically mentions 'document' and 'name', prioritize Google Docs mimeType.
                if "document" in raw_query.lower() and "name" in raw_query.lower():
                    request_params["q"] = f"({sanitize_drive_query(raw_query)}) and mimeType='application/vnd.google-apps.document'"
                else:
                    request_params["q"] = sanitize_drive_query(raw_query)
            return ["drive", "files", "list", "--params", json.dumps(request_params)]

        if action == "create_folder":
            folder_name = self._required_text(params, "folder_name")
            return ["drive", "files", "create", "--json",
                    json.dumps({"mimeType": "application/vnd.google-apps.folder", "name": folder_name}, ensure_ascii=True)]

        if action == "get_file":
            file_id = self._required_text(params, "file_id")
            return ["drive", "files", "get", "--params", json.dumps({"fileId": file_id})]

        if action == "export_file":
            file_id = self._required_text(params, "file_id")

            requested_mime = str(params.get("mime_type") or "").strip()
            source_mime    = str(params.get("source_mime") or "").strip()

            # 🔥 PRIMARY: use source_mime if available to determine best export format
            if source_mime == "application/vnd.google-apps.document":
                mime_type = requested_mime or "application/pdf"

            elif source_mime == "application/vnd.google-apps.spreadsheet":
                mime_type = requested_mime or "text/csv"

            elif source_mime == "application/vnd.google-apps.presentation":
                mime_type = "application/pdf"

            else:
                # If no source_mime, respect requested_mime or default to PDF
                mime_type = requested_mime or "application/pdf"

            return [
                "drive",
                "files",
                "export",
                "--params",
                json.dumps({
                    "fileId": file_id,
                    "mimeType": mime_type
                })
            ]
        
        if action == "delete_file":
            file_id = self._required_text(params, "file_id")
            return ["drive", "files", "delete", "--params", json.dumps({"fileId": file_id})]

        if action == "move_file":
            file_id = self._required_text(params, "file_id")
            folder_id = self._required_text(params, "folder_id")
            # In Drive v3, move is accomplished via update with addParents/removeParents
            return [
                "drive",
                "files",
                "update",
                "--params",
                json.dumps({
                    "fileId": file_id,
                    "addParents": folder_id,
                    "removeParents": "root"  # Optional: assuming it was in root or we don't know the old parent
                })
            ]

        raise ValidationError(f"Unsupported drive action: {action}")

    # ------------------------------------------------------------------
    # Sheets
    # ------------------------------------------------------------------

    def _build_sheets_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "create_spreadsheet":
            title = self._required_text(params, "title")
            return ["sheets", "spreadsheets", "create", "--json",
                    json.dumps({
                        "properties": {"title": title},
                        "sheets": [{"properties": {"title": title}}]
                    }, ensure_ascii=True)]

        if action == "get_spreadsheet":
            spreadsheet_id = self._required_text(params, "spreadsheet_id")
            return ["sheets", "spreadsheets", "get", "--params", json.dumps({"spreadsheetId": spreadsheet_id})]

        if action == "get_values":
            spreadsheet_id = self._required_text(params, "spreadsheet_id")
            range_name = self._format_range(str(params.get("range") or "A1:Z500"))
            return ["sheets", "spreadsheets", "values", "get", "--params",
                    json.dumps({"spreadsheetId": spreadsheet_id, "range": range_name})]

        if action == "append_values":
            spreadsheet_id = self._required_text(params, "spreadsheet_id")
            range_name = self._format_range(str(params.get("range") or "A1"))
            values = params.get("values")
            if isinstance(values, str):
                values = [[values]]
            if not isinstance(values, list) or not values:
                values = [["No values supplied"]]
            return [
                "sheets", "spreadsheets", "values", "append",
                "--params", json.dumps({"spreadsheetId": spreadsheet_id, "range": range_name,
                                        "valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"}, ensure_ascii=True),
                "--json",  json.dumps({"range": range_name, "majorDimension": "ROWS", "values": values}, ensure_ascii=True),
            ]

        raise ValidationError(f"Unsupported sheets action: {action}")

    # ------------------------------------------------------------------
    # Gmail
    # ------------------------------------------------------------------

    def _build_gmail_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_messages":
            max_results = self._safe_positive_int(params.get("max_results"), default=10)
            raw_query   = str(params.get("q") or "").strip()
            request_params: dict[str, Any] = {
                "userId": "me",
                "maxResults": max_results,
                "fields": "messages(id,threadId),nextPageToken,resultSizeEstimate",
            }
            if raw_query:
                # Fix #8 — sanitize Gmail query just like we sanitize Drive queries.
                request_params["q"] = sanitize_gmail_query(raw_query)
            return ["gmail", "users", "messages", "list", "--params", json.dumps(request_params)]

        if action == "get_message":
            # Allow message_id to be missing or a placeholder during planning
            message_id = params.get("message_id") or "{{message_id}}"
            return ["gmail", "users", "messages", "get", "--params",
                    json.dumps({"userId": "me", "id": message_id})]

        if action == "send_message":
            to_email = self._required_text(params, "to_email")
            subject  = self._required_text(params, "subject")
            body     = self._required_text(params, "body")

            attachments = params.get("attachments")
            attachment_paths: list[str] = []
            if isinstance(attachments, str) and attachments.strip():
                attachment_paths = [attachments.strip()]
            elif isinstance(attachments, list):
                attachment_paths = [str(a).strip() for a in attachments if str(a).strip()]

            # Resolve any raw Drive file IDs in attachment_paths to local PDF files.
            # When the planner receives a Drive file ID (e.g. the agent passed the ID
            # from a drive.list_files result directly as the attachment value), we must
            # export/download the file first so that _build_raw_email_with_attachments
            # can open a real local file.  Without this step the attachment silently
            # disappears because os.path.isfile(drive_id) is always False.
            resolved_attachment_paths: list[str] = []
            for path in attachment_paths:
                if _DRIVE_FILE_ID_RE.match(path):
                    # It looks like a Drive file ID, not a local filesystem path.
                    local_path = self._export_drive_file_to_temp(path)
                    if local_path:
                        resolved_attachment_paths.append(local_path)
                    else:
                        # Export failed — fall back to sending a Drive link in the body
                        # so the recipient still has access to the document.
                        drive_link = f"https://drive.google.com/file/d/{path}/view"
                        body = (
                            body.rstrip()
                            + "\n\nNote: The requested document could not be attached directly. "
                            + f"You can access it here: {drive_link}"
                        )
                else:
                    resolved_attachment_paths.append(path)

            if resolved_attachment_paths:
                raw_email = self._build_raw_email_with_attachments(
                    to_email=to_email, subject=subject, body=body,
                    attachment_paths=resolved_attachment_paths,
                )
            else:
                raw_email = self._build_raw_email(to_email=to_email, subject=subject, body=body)

            return ["gmail", "users", "messages", "send",
                    "--params", json.dumps({"userId": "me"}),
                    "--json",   json.dumps({"raw": raw_email}, ensure_ascii=True)]

        raise ValidationError(f"Unsupported gmail action: {action}")

    # ------------------------------------------------------------------
    # Calendar
    # ------------------------------------------------------------------

    def _build_calendar_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_events":
            calendar_id = str(params.get("calendar_id") or "primary").strip()
            return ["calendar", "events", "list", "--params",
                    json.dumps({"calendarId": calendar_id, "singleEvents": True,
                                "orderBy": "startTime", "maxResults": 20})]

        if action == "create_event":
            summary = self._required_text(params, "summary")

            # ------------------------------------------------------------------
            # Fix 1 — resolve relative date expressions ("tomorrow", "next monday"…)
            # The LLM sometimes passes the literal word "tomorrow" or a stale
            # hardcoded date.  _resolve_date_expression() converts both to a
            # correct YYYY-MM-DD string anchored to today's actual date.
            # ------------------------------------------------------------------
            start_date_raw = self._required_text(params, "start_date")
            start_date     = _resolve_date_expression(start_date_raw)

            # ------------------------------------------------------------------
            # Fix 2 — use dateTime + timeZone when a time is provided.
            # Prefer an explicit start_datetime param (already ISO-8601), then
            # fall back to combining start_date + start_time.  Only use the
            # all-day {"date": ...} format when absolutely no time is given.
            # ------------------------------------------------------------------
            time_zone = str(params.get("time_zone") or params.get("timezone") or "UTC").strip()

            # Accept a fully-qualified start_datetime from the LLM if provided.
            start_datetime_raw = str(params.get("start_datetime") or "").strip()

            # Also accept a bare time string in start_time or start_date itself.
            start_time_raw = str(params.get("start_time") or "").strip()


            event_start: dict[str, str]
            event_end:   dict[str, str]

            if start_datetime_raw:
                # LLM supplied a full ISO datetime — use it directly.
                dt_str = start_datetime_raw if "T" in start_datetime_raw else f"{start_date}T{start_datetime_raw}"
                event_start = {"dateTime": dt_str, "timeZone": time_zone}
                # Default end = start + 1 hour
                try:
                    dt_obj  = datetime.fromisoformat(dt_str)
                    end_str = (dt_obj + timedelta(hours=1)).isoformat()
                except ValueError:
                    end_str = dt_str
                event_end = {"dateTime": end_str, "timeZone": time_zone}

            elif start_time_raw:
                parsed_time = _parse_time_to_hhmm(start_time_raw)
                if parsed_time:
                    h, m     = parsed_time
                    dt_start = datetime(
                        *[int(p) for p in start_date.split("-")], h, m
                    )
                    dt_end   = dt_start + timedelta(hours=1)
                    event_start = {"dateTime": dt_start.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": time_zone}
                    event_end   = {"dateTime": dt_end.strftime("%Y-%m-%dT%H:%M:%S"),   "timeZone": time_zone}
                else:
                    # Unparseable time string — fall back to all-day.
                    event_start = {"date": start_date}
                    event_end   = {"date": start_date}
            else:
                # No time provided at all — create an all-day event.
                event_start = {"date": start_date}
                event_end   = {"date": start_date}

            # ------------------------------------------------------------------
            # Fix 3 — populate description with spreadsheet_url / description.
            # The LLM may pass the sheet URL as "spreadsheet_url", "sheet_url",
            # "description", or "body".  Accept all aliases.
            # ------------------------------------------------------------------
            description = (
                str(params.get("description") or "").strip()
                or str(params.get("spreadsheet_url") or "").strip()
                or str(params.get("sheet_url") or "").strip()
                or str(params.get("body") or "").strip()
            )

            # ------------------------------------------------------------------
            # Fix 4 — forward reminder_minutes into the reminders block.
            # Previously this param was silently ignored.
            # ------------------------------------------------------------------
            reminder_minutes_raw = params.get("reminder_minutes") or params.get("reminder")
            reminder_minutes     = self._safe_positive_int(reminder_minutes_raw, default=0)

            event_body: dict[str, Any] = {
                "summary": summary,
                "start":   event_start,
                "end":     event_end,
            }

            if description:
                event_body["description"] = description

            if reminder_minutes > 0:
                event_body["reminders"] = {
                    "useDefault": False,
                    "overrides":  [{"method": "popup", "minutes": reminder_minutes}],
                }

            return ["calendar", "events", "insert",
                    "--params", json.dumps({"calendarId": "primary"}),
                    "--json",   json.dumps(event_body, ensure_ascii=True)]

        raise ValidationError(f"Unsupported calendar action: {action}")

    # ------------------------------------------------------------------
    # Docs
    # ------------------------------------------------------------------

    def _build_docs_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "create_document":
            # Fix #3 — Google Docs REST API ignores 'body' on creation; only 'title' is accepted.
            title = self._required_text(params, "title") if params.get("title") else "Untitled Document"
            doc_body: dict[str, Any] = {"title": title}
            return ["docs", "documents", "create", "--json", json.dumps(doc_body, ensure_ascii=True)]

        if action == "get_document":
            doc_id = (params.get("document_id") or params.get("documentId")
                      or params.get("file_id")   or params.get("fileId"))
            if not doc_id or not str(doc_id).strip():
                raise ValidationError("Missing required parameter: document_id")
            return ["docs", "documents", "get", "--params", json.dumps({"documentId": str(doc_id).strip()})]

        if action == "batch_update":
            document_id      = self._required_text(params, "document_id")
            text             = str(params.get("text") or "").strip()
            requests_payload = [{"insertText": {"location": {"index": 1}, "text": text}}]
            return ["docs", "documents", "batchUpdate",
                    "--params", json.dumps({"documentId": document_id}),
                    "--json",   json.dumps({"requests": requests_payload}, ensure_ascii=True)]

        raise ValidationError(f"Unsupported docs action: {action}")

    # ------------------------------------------------------------------
    # Slides, Contacts, Chat, Meet
    # ------------------------------------------------------------------

    def _build_slides_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "get_presentation":
            presentation_id = self._required_text(params, "presentation_id")
            return ["slides", "presentations", "get", "--params", json.dumps({"presentationId": presentation_id})]
        raise ValidationError(f"Unsupported slides action: {action}")

    def _build_contacts_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_contacts":
            page_size = self._safe_positive_int(params.get("page_size"), default=10)
            return ["people", "people", "connections", "list", "--params",
                    json.dumps({"resourceName": "people/me", "pageSize": page_size,
                                "personFields": "names,emailAddresses,phoneNumbers"})]
        raise ValidationError(f"Unsupported contacts action: {action}")

    def _build_chat_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_spaces":
            page_size = self._safe_positive_int(params.get("page_size"), default=10)
            return ["chat", "spaces", "list", "--params", json.dumps({"pageSize": page_size})]
        if action == "send_message":
            space = self._required_text(params, "space")
            text  = self._required_text(params, "text")
            return ["chat", "spaces", "messages", "create",
                    "--params", json.dumps({"parent": space}),
                    "--json",   json.dumps({"text": text}, ensure_ascii=True)]
        if action == "list_messages":
            space     = self._required_text(params, "space")
            page_size = self._safe_positive_int(params.get("page_size"), default=10)
            return ["chat", "spaces", "messages", "list", "--params",
                    json.dumps({"parent": space, "pageSize": page_size})]
        raise ValidationError(f"Unsupported chat action: {action}")

    def _build_meet_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_conferences":
            return ["meet", "spaces", "list"]
        if action == "get_conference":
            name = self._required_text(params, "name")
            return ["meet", "spaces", "get", "--params", json.dumps({"name": name})]
        if action == "create_meeting":
            return ["meet", "spaces", "create"]
        raise ValidationError(f"Unsupported meet action: {action}")

    # ------------------------------------------------------------------
    # Admin & Forms
    # ------------------------------------------------------------------

    def _build_admin_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "log_activity":
            # Synthetic tool handled in execution.py
            return ["admin", "log_activity", "internal"]
        
        if action == "list_activities":
            app_name = str(params.get("application_name") or "drive").strip()
            max_res  = self._safe_positive_int(params.get("max_results"), default=10)
            return ["admin-reports", "activities", "list", 
                    "--params", json.dumps({"userKey": "all", "applicationName": app_name, "maxResults": max_res})]
        
        raise ValidationError(f"Unsupported admin action: {action}")

    def _build_forms_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "create_form":
            title = str(params.get("title") or "Untitled Form").strip()
            return ["forms", "forms", "create", "--json", json.dumps({"info": {"title": title}}, ensure_ascii=True)]
        
        if action == "get_form":
            form_id = self._required_text(params, "form_id")
            return ["forms", "forms", "get", "--params", json.dumps({"formId": form_id})]
        
        raise ValidationError(f"Unsupported forms action: {action}")

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _format_range(self, range_str: str) -> str:
        range_str = range_str.strip()
        if "!" not in range_str:
            return range_str
        sheet_part, cell_part = range_str.split("!", 1)
        if " " in sheet_part and not (sheet_part.startswith("'") and sheet_part.endswith("'")):
            return f"'{sheet_part}'!{cell_part}"
        return range_str

    @staticmethod
    def _required_text(params: dict[str, Any], key: str) -> str:
        value = params.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
        variations = [key.lower().replace("_", ""), key.replace("_", "")]
        for k, v in params.items():
            if k.lower().replace("_", "") in variations and v is not None and str(v).strip():
                return str(v).strip()
        raise ValidationError(f"Missing required parameter: {key}")

    @staticmethod
    def _safe_positive_int(value: Any, default: int) -> int:
        try:
            parsed = int(str(value).strip())
            return parsed if parsed > 0 else default
        except Exception:
            return default

    @staticmethod
    def _build_raw_email(to_email: str, subject: str, body: str) -> str:
        message = (
            f"To: {to_email}\r\n"
            f"Subject: {subject}\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n"
            "MIME-Version: 1.0\r\n"
            "\r\n"
            f"{body}"
        )
        return base64.urlsafe_b64encode(message.encode("utf-8")).decode("ascii")

    @staticmethod
    def _build_raw_email_with_attachments(
        to_email: str, subject: str, body: str, attachment_paths: list[str],
    ) -> str:
        msg = email_lib.mime.multipart.MIMEMultipart("mixed")
        msg["To"]           = to_email
        msg["Subject"]      = subject
        msg["MIME-Version"] = "1.0"
        msg.attach(email_lib.mime.text.MIMEText(body, "plain", "utf-8"))

        for path in attachment_paths:
            if not os.path.isfile(path):
                continue
            filename = os.path.basename(path)
            with open(path, "rb") as fh:
                data = fh.read()
            part = email_lib.mime.application.MIMEApplication(data, Name=filename)
            part["Content-Disposition"] = f'attachment; filename="{filename}"'
            msg.attach(part)

        return base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

    @staticmethod
    def _export_drive_file_to_temp(file_id: str) -> str | None:
        try:
            # Fix #4 — stdlib imports (subprocess, tempfile, os, json) are already at module level.
            tmp_dir = tempfile.mkdtemp(prefix="gws_attach_")

            gws_exe = os.environ.get("GWS_EXE") or os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "gws.exe",
            )

            # 🔥 Try multiple formats intelligently
            export_attempts = [
                ("application/pdf", ".pdf"),   # Docs, Slides
                ("text/csv", ".csv"),          # Sheets
            ]

            for mime_type, ext in export_attempts:
                file_path = os.path.join(tmp_dir, f"{file_id}{ext}")

                export_params = json.dumps({
                    "fileId": file_id,
                    "mimeType": mime_type,
                })

                result = subprocess.run(
                    [
                        gws_exe,
                        "drive",
                        "files",
                        "export",
                        "--params",
                        export_params,
                        "--output",
                        file_path,
                    ],
                    capture_output=True,
                    timeout=30,
                )

                if (
                    result.returncode == 0
                    and os.path.isfile(file_path)
                    and os.path.getsize(file_path) > 0
                ):
                    return file_path

            return None

        except Exception:
            return None
