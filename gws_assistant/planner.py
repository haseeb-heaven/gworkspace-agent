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
import sys
import tempfile
from datetime import date, datetime, timedelta
from typing import Any

from .drive_query_builder import sanitize_drive_query
from .exceptions import UnsupportedServiceError, ValidationError
from .gmail_query_builder import sanitize_gmail_query
from .models import ActionSpec, ParameterSpec
from .service_catalog import SERVICES, normalize_service, supported_services

_UNSUPPORTED_STUB_SERVICES = frozenset({"analytics", "bigquery"})

# Matches a raw Google Drive file ID (alphanumeric + hyphens/underscores, 25-60 chars).
# Drive file IDs look like: 1-A9SUqwDnbUE51VZ7FbAh8i-wUGz8Cqw9jCIUw0nMjo
_DRIVE_FILE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{25,60}$")

# MIME type used when exporting Google Docs to PDF for attachment.
_GDOC_EXPORT_MIME = "application/pdf"

# ---------------------------------------------------------------------------
# Date / time helpers
# ---------------------------------------------------------------------------

_WEEKDAY_NAMES = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
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
      - ISO dates already in YYYY-MM-DD format  -> returned as-is
      - "today"                                 -> date.today()
      - "tomorrow"                              -> date.today() + 1 day
      - "yesterday"                             -> date.today() - 1 day
      - "next <weekday>"                        -> next occurrence of that weekday
      - "<weekday>"                             -> nearest future occurrence
      - Anything else                           -> returned as-is (LLM supplied a literal)
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
    check_val = val[5:] if next_prefix else val

    if check_val in _WEEKDAY_NAMES:
        target_wd = _WEEKDAY_NAMES[check_val]
        days_ahead = (target_wd - today.weekday()) % 7
        # "next X" always means at least 7 days from now even if today is X
        if next_prefix and days_ahead == 0:
            days_ahead = 7
        elif days_ahead == 0:
            days_ahead = 7  # bare weekday name that matches today -> next week
        return (today + timedelta(days=days_ahead)).isoformat()

    # Fallback — return as-is; the LLM may have already supplied an ISO date
    # embedded inside a longer string like "2026-04-14T10:00:00".
    # We strip the time portion only if the prefix is a valid ISO date.
    stripped = raw.strip()
    if "T" in stripped:
        prefix = stripped.split("T")[0]
        if _ISO_DATE_RE.match(prefix):
            return prefix
    return stripped


def _parse_time_to_hhmm(raw: str) -> tuple[int, int] | None:
    """Extract (hour_24, minute) from a loose time string.  Returns None if unparseable."""
    m = _TIME_RE.search(raw.strip())
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0
    ampm = (m.group(3) or "").lower()
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

        if service_key == "drive":
            return self._build_drive_command(action_key, params)
        if service_key == "sheets":
            return self._build_sheets_command(action_key, params)
        if service_key == "gmail":
            return self._build_gmail_command(action_key, params)
        if service_key == "calendar":
            return self._build_calendar_command(action_key, params)
        if service_key == "docs":
            return self._build_docs_command(action_key, params)
        if service_key == "slides":
            return self._build_slides_command(action_key, params)
        if service_key == "contacts":
            return self._build_contacts_command(action_key, params)
        if service_key == "chat":
            return self._build_chat_command(action_key, params)
        if service_key == "meet":
            return self._build_meet_command(action_key, params)
        if service_key == "keep":
            return self._build_keep_command(action_key, params)
        if service_key == "search":
            return self._build_search_command(action_key, params)
        if service_key == "admin":
            return self._build_admin_command(action_key, params)
        if service_key == "forms":
            return self._build_forms_command(action_key, params)
        if service_key == "telegram":
            return self._build_telegram_command(action_key, params)
        if service_key == "tasks":
            return self._build_tasks_command(action_key, params)
        if service_key == "classroom":
            return self._build_classroom_command(action_key, params)
        if service_key == "script":
            return self._build_script_command(action_key, params)
        if service_key == "events":
            return self._build_events_command(action_key, params)
        if service_key == "modelarmor":
            return self._build_modelarmor_command(action_key, params)
        if service_key in ("code", "computation"):
            return [service_key, action_key, "internal"]
        if service_key == "workflow":
            return ["workflow", "list"]  # Placeholder for internal workflow listing
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
                # If the query looks like a document search, prioritize Google Docs mimeType.
                lowered = raw_query.lower()
                if any(kw in lowered for kw in ("document", "doc", "12th", "class")) and "mimetype" not in lowered:
                    request_params["q"] = (
                        f"({sanitize_drive_query(raw_query)}) and mimeType='application/vnd.google-apps.document'"
                    )
                else:
                    request_params["q"] = sanitize_drive_query(raw_query)
            return ["drive", "files", "list", "--params", json.dumps(request_params, ensure_ascii=True)]

        if action == "create_folder":
            folder_name = self._required_text(params, "folder_name")
            return [
                "drive",
                "files",
                "create",
                "--params",
                json.dumps({"fields": "id,name,mimeType,webViewLink"}),
                "--json",
                json.dumps({"mimeType": "application/vnd.google-apps.folder", "name": folder_name}, ensure_ascii=True),
            ]

        if action == "upload_file":
            file_path = self._required_text(params, "file_path")
            name = str(params.get("name") or os.path.basename(file_path)).strip()
            return [
                "drive",
                "files",
                "create",
                "--upload",
                file_path,
                "--params",
                json.dumps({"fields": "id,name,mimeType,webViewLink"}),
                "--json",
                json.dumps({"name": name}, ensure_ascii=True),
            ]

        if action == "get_file":
            file_id = self._required_text(params, "file_id")
            return [
                "drive",
                "files",
                "get",
                "--params",
                json.dumps({"fileId": file_id, "fields": "id,name,mimeType,webViewLink"}),
            ]

        if action == "create_file":
            name = self._required_text(params, "name")
            mime_type = str(params.get("mime_type") or "application/vnd.google-apps.document").strip()
            folder_id = str(params.get("folder_id") or "").strip()

            payload: dict[str, Any] = {"name": name, "mimeType": mime_type}
            if folder_id:
                payload["parents"] = [folder_id]

            return [
                "drive",
                "files",
                "create",
                "--params",
                json.dumps({"fields": "id,name,mimeType,webViewLink"}),
                "--json",
                json.dumps(payload, ensure_ascii=True),
            ]

        if action == "export_file":
            file_id = self._required_text(params, "file_id")

            requested_mime = str(params.get("mime_type") or "").strip()
            source_mime = str(params.get("source_mime") or "").strip()

            # PRIMARY: use source_mime if available to determine best export format
            # Only certain types support the 'export' endpoint.
            # Folders, Shortcuts, Scripts, and regular files MUST use 'get' with 'alt=media'.
            exportable_mimes = {
                "application/vnd.google-apps.document",
                "application/vnd.google-apps.spreadsheet",
                "application/vnd.google-apps.presentation",
                "application/vnd.google-apps.drawing",
            }
            is_workspace_doc = source_mime in exportable_mimes
            if source_mime == "application/vnd.google-apps.folder":
                # Folders CANNOT be exported or downloaded as media.
                # Returning a ValidationError here helps the agent realize it picked a folder instead of a document.
                raise ValidationError(
                    f"File '{file_id}' is a folder and cannot be read as document content. Please search specifically for documents or list folder contents."
                )

            if source_mime and not is_workspace_doc:
                return [
                    "drive",
                    "files",
                    "get",
                    "--params",
                    json.dumps({"fileId": file_id, "alt": "media"}),
                    "-o",
                    f"scratch/exports/download_{file_id}",
                ]

            if source_mime == "application/vnd.google-apps.document":
                mime_type = requested_mime or "text/plain"
            elif source_mime == "application/vnd.google-apps.spreadsheet":
                if not requested_mime or requested_mime == "text/plain":
                    mime_type = "text/csv"
                else:
                    mime_type = requested_mime
            elif source_mime == "application/vnd.google-apps.presentation":
                mime_type = requested_mime or "application/pdf"
            else:
                # If no source_mime, respect requested_mime or default to PDF
                mime_type = requested_mime or "application/pdf"

            # If the user explicitly asks for media/download or it's already a PDF and they want it
            if mime_type == "media" or (source_mime == "application/pdf" and mime_type == "application/pdf"):
                return [
                    "drive",
                    "files",
                    "get",
                    "--params",
                    json.dumps({"fileId": file_id, "alt": "media"}),
                    "-o",
                    f"scratch/exports/download_{file_id}",
                ]

            return [
                "drive",
                "files",
                "export",
                "--params",
                json.dumps({"fileId": file_id, "mimeType": mime_type}),
                "-o",
                f"scratch/exports/download_{file_id}",
            ]

        if action == "delete_file":
            file_id = self._required_text(params, "file_id")
            return ["drive", "files", "delete", "--params", json.dumps({"fileId": file_id})]

        if action == "update_file_metadata":
            file_id = self._required_text(params, "file_id")
            name = str(params.get("name") or "").strip()
            description = str(params.get("description") or "").strip()

            payload = {}
            if name:
                payload["name"] = name
            if description:
                payload["description"] = description

            if not payload:
                raise ValidationError("At least one metadata field (name or description) must be provided.")

            return [
                "drive",
                "files",
                "update",
                "--params",
                json.dumps({"fileId": file_id, "fields": "id,name,description"}),
                "--json",
                json.dumps(payload, ensure_ascii=True),
            ]

        if action == "move_file":
            file_id = self._required_text(params, "file_id")
            folder_id = self._required_text(params, "folder_id")
            # In Drive v3, move is accomplished via update with addParents/removeParents.
            # The execution engine will intercept this placeholder and fetch parents.
            update_params = {"fileId": file_id, "addParents": folder_id, "removeParents": "{{fetch_parents}}"}

            return ["drive", "files", "update", "--params", json.dumps(update_params)]

        if action == "copy_file":
            file_id = self._required_text(params, "file_id")
            name = str(params.get("name") or "").strip()
            folder_id = str(params.get("folder_id") or "").strip()

            _request_params: dict[str, Any] = {"fileId": file_id}
            _payload: dict[str, Any] = {}
            if name:
                _payload["name"] = name
            if folder_id:
                _payload["parents"] = [folder_id]

            cmd = ["drive", "files", "copy", "--params", json.dumps(_request_params)]
            if _payload:
                cmd.extend(["--json", json.dumps(_payload, ensure_ascii=True)])
            return cmd

        if action == "move_to_trash":
            file_id = self._required_text(params, "file_id")
            return ["drive", "files", "update", "--params", json.dumps({"fileId": file_id}), "--json", json.dumps({"trashed": True})]

        raise ValidationError(f"Unsupported drive action: {action}")

    # ------------------------------------------------------------------
    # Sheets
    # ------------------------------------------------------------------

    def _build_sheets_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "create_spreadsheet":
            title = self._required_text(params, "title")
            return [
                "sheets",
                "spreadsheets",
                "create",
                "--json",
                json.dumps(
                    {"properties": {"title": title}, "sheets": [{"properties": {"title": title}}]}, ensure_ascii=True
                ),
            ]

        if action == "get_spreadsheet":
            spreadsheet_id = self._required_text(params, "spreadsheet_id")
            return ["sheets", "spreadsheets", "get", "--params", json.dumps({"spreadsheetId": spreadsheet_id})]

        if action == "get_values":
            spreadsheet_id = self._required_text(params, "spreadsheet_id")
            range_name = str(params.get("range") or "A1")
            return [
                "sheets",
                "+read",
                "--spreadsheet",
                spreadsheet_id,
                "--range",
                range_name,
            ]

        if action == "append_values":
            spreadsheet_id = self._required_text(params, "spreadsheet_id")
            range_name = self._format_range(str(params.get("range") or "A1"))

            values = params.get("values")
            # Ensure 'values' is a list of lists, even if it's a single string or flat list
            if isinstance(values, str):
                values = [[values]]  # e.g. "hello" -> [["hello"]]
            elif isinstance(values, list):
                if values and not isinstance(values[0], list):
                    values = [values]  # e.g. ['a', 'b'] -> [['a', 'b']]
                elif not values:  # Handle empty list
                    values = [["No values supplied"]]
            else:  # Handle non-string, non-list types (e.g., None, int, etc.)
                val_str = "" if values is None else str(values)
                values = [[val_str]]  # Wrap in list of lists

            return [
                "sheets",
                "spreadsheets",
                "values",
                "append",
                "--params",
                json.dumps(
                    {
                        "spreadsheetId": spreadsheet_id,
                        "range": range_name,
                        "valueInputOption": "RAW",
                        "insertDataOption": "INSERT_ROWS",
                    },
                    ensure_ascii=True,
                ),
                "--json",
                json.dumps({"range": range_name, "majorDimension": "ROWS", "values": values}, ensure_ascii=True),
            ]

        if action == "delete_spreadsheet":
            spreadsheet_id = self._required_text(params, "spreadsheet_id")
            return ["drive", "files", "delete", "--params", json.dumps({"fileId": spreadsheet_id})]

        if action == "clear_values":
            spreadsheet_id = self._required_text(params, "spreadsheet_id")
            range_name = self._format_range(str(params.get("range") or "A1"))
            return [
                "sheets",
                "spreadsheets",
                "values",
                "clear",
                "--params",
                json.dumps({"spreadsheetId": spreadsheet_id, "range": range_name}, ensure_ascii=True),
            ]

        raise ValidationError(f"Unsupported sheets action: {action}")

    # ------------------------------------------------------------------
    # Gmail
    # ------------------------------------------------------------------

    def _build_gmail_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_messages":
            max_results = self._safe_positive_int(params.get("max_results"), default=10)
            raw_query = str(params.get("q") or "").strip()
            request_params: dict[str, Any] = {
                "userId": "me",
                "maxResults": max_results,
                "fields": "messages(id,threadId),nextPageToken,resultSizeEstimate",
            }
            if raw_query:
                # Fix #8 — sanitize Gmail query just like we sanitize Drive queries.
                request_params["q"] = sanitize_gmail_query(raw_query)
            return ["gmail", "users", "messages", "list", "--params", json.dumps(request_params, ensure_ascii=True)]

        if action == "get_message":
            # Allow message_id to be missing or a placeholder during planning
            message_id = params.get("message_id") or "{{message_id}}"
            return ["gmail", "users", "messages", "get", "--params", json.dumps({"userId": "me", "id": message_id})]

        if action == "trash_message":
            message_id = self._required_text(params, "message_id")
            return ["gmail", "users", "messages", "trash", "--params", json.dumps({"userId": "me", "id": message_id})]

        if action == "delete_message":
            message_id = self._required_text(params, "message_id")
            return ["gmail", "users", "messages", "delete", "--params", json.dumps({"userId": "me", "id": message_id})]

        if action == "send_message":
            to_email = self._required_text(params, "to_email").strip().rstrip(".")
            subject = self._required_text(params, "subject")
            body = self._required_text(params, "body")

            # Scrub any internal [File: \\?\D:\...] or [File: /...] paths from the body
            body = re.sub(r'\[File: [^\]]+\]', '[See attached document]', body)

            attachments = params.get("attachments")
            attachment_paths: list[str] = []
            if isinstance(attachments, str) and attachments.strip():
                attachment_paths = [attachments.strip()]
            elif isinstance(attachments, list):
                attachment_paths = [str(a).strip() for a in attachments if str(a).strip()]

            # Resolve any raw Drive file IDs in attachment_paths to local files.
            resolved_attachment_paths: list[str] = []
            for path in attachment_paths:
                if _DRIVE_FILE_ID_RE.match(path):
                    local_path = self._export_drive_file_to_temp(path)
                    if local_path:
                        resolved_attachment_paths.append(local_path)
                    else:
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
                    to_email=to_email,
                    subject=subject,
                    body=body,
                    attachment_paths=resolved_attachment_paths,
                )
            else:
                raw_email = self._build_raw_email(to_email=to_email, subject=subject, body=body)

            return [
                "gmail",
                "users",
                "messages",
                "send",
                "--params",
                json.dumps({"userId": "me"}),
                "--json",
                json.dumps({"raw": raw_email}, ensure_ascii=True),
            ]

        raise ValidationError(f"Unsupported gmail action: {action}")

    # ------------------------------------------------------------------
    # Calendar
    # ------------------------------------------------------------------

    def _build_calendar_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_events":
            calendar_id = str(params.get("calendar_id") or "primary").strip()
            return [
                "calendar",
                "events",
                "list",
                "--params",
                json.dumps({"calendarId": calendar_id, "singleEvents": True, "orderBy": "startTime", "maxResults": 20}),
            ]

        if action == "create_event":
            summary = self._required_text(params, "summary")
            start_date_raw = self._required_text(params, "start_date")
            start_date = _resolve_date_expression(start_date_raw)
            time_zone = str(params.get("time_zone") or params.get("timezone") or "UTC").strip()
            start_datetime_raw = str(params.get("start_datetime") or "").strip()
            start_time_raw = str(params.get("start_time") or "").strip()

            event_start: dict[str, str]
            event_end: dict[str, str]

            if start_datetime_raw:
                dt_str = start_datetime_raw if "T" in start_datetime_raw else f"{start_date}T{start_datetime_raw}"
                event_start = {"dateTime": dt_str, "timeZone": time_zone}
                try:
                    dt_obj = datetime.fromisoformat(dt_str)
                    end_str = (dt_obj + timedelta(hours=1)).isoformat()
                except ValueError:
                    end_str = dt_str
                event_end = {"dateTime": end_str, "timeZone": time_zone}
            elif start_time_raw:
                parsed_time = _parse_time_to_hhmm(start_time_raw)
                if parsed_time:
                    h, m = parsed_time
                    y, month, day = [int(p) for p in start_date.split("-")]
                    dt_start = datetime(y, month, day, h, m)
                    dt_end = dt_start + timedelta(hours=1)
                    event_start = {"dateTime": dt_start.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": time_zone}
                    event_end = {"dateTime": dt_end.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": time_zone}
                else:
                    event_start = {"date": start_date}
                    try:
                        event_end = {"date": (date.fromisoformat(start_date) + timedelta(days=1)).isoformat()}
                    except ValueError:
                        event_end = {"date": start_date}
            else:
                event_start = {"date": start_date}
                try:
                    event_end = {"date": (date.fromisoformat(start_date) + timedelta(days=1)).isoformat()}
                except ValueError:
                    event_end = {"date": start_date}

            description = (
                str(params.get("description") or "").strip()
                or str(params.get("spreadsheet_url") or "").strip()
                or str(params.get("sheet_url") or "").strip()
                or str(params.get("body") or "").strip()
            )

            reminder_minutes_raw = params.get("reminder_minutes") or params.get("reminder")
            reminder_minutes = self._safe_positive_int(reminder_minutes_raw, default=0)

            event_body: dict[str, Any] = {
                "summary": summary,
                "start": event_start,
                "end": event_end,
            }

            if description:
                event_body["description"] = description

            if params.get("with_meet") or params.get("add_meet"):
                event_body["conferenceData"] = {
                    "createRequest": {
                        "requestId": f"meet-{int(datetime.now().timestamp())}",
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                }

            if reminder_minutes > 0:
                event_body["reminders"] = {
                    "useDefault": False,
                    "overrides": [{"method": "popup", "minutes": reminder_minutes}],
                }

            params_dict: dict[str, Any] = {"calendarId": "primary"}
            if "conferenceData" in event_body:
                params_dict["conferenceDataVersion"] = 1

            return [
                "calendar",
                "events",
                "insert",
                "--params",
                json.dumps(params_dict),
                "--json",
                json.dumps(event_body, ensure_ascii=True),
            ]

        if action == "get_event":
            calendar_id = str(params.get("calendar_id") or "primary").strip()
            event_id = self._required_text(params, "event_id")
            return [
                "calendar",
                "events",
                "get",
                "--params",
                json.dumps({"calendarId": calendar_id, "eventId": event_id}),
            ]

        if action == "delete_event":
            calendar_id = str(params.get("calendar_id") or "primary").strip()
            event_id = self._required_text(params, "event_id")
            return [
                "calendar",
                "events",
                "delete",
                "--params",
                json.dumps({"calendarId": calendar_id, "eventId": event_id}),
            ]

        if action == "update_event":
            calendar_id = str(params.get("calendar_id") or "primary").strip()
            event_id = self._required_text(params, "event_id")
            patch_body = {}
            if params.get("summary"):
                patch_body["summary"] = str(params.get("summary")).strip()
            if params.get("description"):
                patch_body["description"] = str(params.get("description")).strip()
            if params.get("location"):
                patch_body["location"] = str(params.get("location")).strip()
            if params.get("start"):
                patch_body["start"] = params["start"]
            if params.get("end"):
                patch_body["end"] = params["end"]
            if params.get("attendees"):
                patch_body["attendees"] = params["attendees"]
            if params.get("reminders"):
                patch_body["reminders"] = params["reminders"]

            return [
                "calendar",
                "events",
                "patch",
                "--params",
                json.dumps({"calendarId": calendar_id, "eventId": event_id}),
                "--json",
                json.dumps(patch_body, ensure_ascii=True),
            ]

        raise ValidationError(f"Unsupported calendar action: {action}")

    # ------------------------------------------------------------------
    # Docs
    # ------------------------------------------------------------------

    def _build_docs_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "create_document":
            title = self._required_text(params, "title")
            doc_body: dict[str, Any] = {"title": title}
            return ["docs", "documents", "create", "--json", json.dumps(doc_body, ensure_ascii=True)]

        if action == "get_document":
            doc_id = (
                params.get("document_id") or params.get("documentId") or params.get("file_id") or params.get("fileId")
            )
            if not doc_id or not str(doc_id).strip():
                raise ValidationError("Missing required parameter: document_id")
            return ["docs", "documents", "get", "--params", json.dumps({"documentId": str(doc_id).strip()})]

        if action == "batch_update":
            document_id = self._required_text(params, "document_id")
            text = str(params.get("text") or "").strip()
            location: dict[str, Any] = {}
            if "index" in params:
                location = {"location": {"index": int(params["index"])}}
            else:
                location = {"endOfSegmentLocation": {"segmentId": ""}}

            requests_payload = [{"insertText": {**location, "text": text}}]
            return [
                "docs",
                "documents",
                "batchUpdate",
                "--params",
                json.dumps({"documentId": document_id}),
                "--json",
                json.dumps({"requests": requests_payload}, ensure_ascii=True),
            ]

        raise ValidationError(f"Unsupported docs action: {action}")

    # ------------------------------------------------------------------
    # Slides
    # ------------------------------------------------------------------

    def _build_slides_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "create_presentation":
            title = str(params.get("title") or "Untitled Presentation").strip()
            return ["slides", "presentations", "create", "--json", json.dumps({"title": title}, ensure_ascii=True)]
        if action == "get_presentation":
            presentation_id = (
                params.get("presentation_id")
                or params.get("presentationId")
                or params.get("id")
                or params.get("file_id")
            )
            if not presentation_id:
                raise ValidationError("Missing required parameter: presentation_id")
            return ["slides", "presentations", "get", "--params", json.dumps({"presentationId": str(presentation_id)})]
        raise ValidationError(f"Unsupported slides action: {action}")

    # ------------------------------------------------------------------
    # Contacts, Chat, Meet, Keep, Admin, Forms, Telegram
    # ------------------------------------------------------------------

    def _build_contacts_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_contacts":
            page_size = self._safe_positive_int(params.get("page_size"), default=10)
            return [
                "people",
                "people",
                "connections",
                "list",
                "--params",
                json.dumps(
                    {
                        "resourceName": "people/me",
                        "pageSize": page_size,
                        "personFields": "names,emailAddresses,phoneNumbers",
                    }
                ),
            ]
        raise ValidationError(f"Unsupported contacts action: {action}")

    def _build_chat_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_spaces":
            page_size = self._safe_positive_int(params.get("page_size"), default=10)
            return ["chat", "spaces", "list", "--params", json.dumps({"pageSize": page_size})]
        if action == "send_message":
            space = self._required_text(params, "space")
            text = self._required_text(params, "text")
            return [
                "chat",
                "spaces",
                "messages",
                "create",
                "--params",
                json.dumps({"parent": space}),
                "--json",
                json.dumps({"text": text}, ensure_ascii=True),
            ]
        if action == "list_messages":
            space = self._required_text(params, "space")
            page_size = self._safe_positive_int(params.get("page_size"), default=10)
            return [
                "chat",
                "spaces",
                "messages",
                "list",
                "--params",
                json.dumps({"parent": space, "pageSize": page_size}),
            ]
        raise ValidationError(f"Unsupported chat action: {action}")

    def _build_meet_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_conferences":
            return ["meet", "conferenceRecords", "list"]
        if action == "get_conference":
            name = self._required_text(params, "name")
            return ["meet", "spaces", "get", "--params", json.dumps({"name": name})]
        if action == "create_meeting":
            return ["meet", "spaces", "create"]
        raise ValidationError(f"Unsupported meet action: {action}")

    def _build_keep_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_notes":
            page_size = self._safe_positive_int(params.get("page_size"), default=10)
            return ["keep", "notes", "list", "--params", json.dumps({"pageSize": page_size})]
        if action == "create_note":
            title = str(params.get("title") or "New Note").strip()
            body = str(params.get("body") or "").strip()
            return [
                "keep",
                "notes",
                "create",
                "--json",
                json.dumps({"title": title, "body": {"text": {"text": body}}}, ensure_ascii=True),
            ]
        if action == "get_note":
            name = self._required_text(params, "name")
            return ["keep", "notes", "get", "--params", json.dumps({"name": name})]
        if action == "delete_note":
            name = self._required_text(params, "name")
            return ["keep", "notes", "delete", "--params", json.dumps({"name": name})]
        raise ValidationError(f"Unsupported keep action: {action}")

    def _build_admin_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "log_activity":
            return ["admin", "log_activity", "internal"]
        if action == "list_activities":
            app_name = str(params.get("application_name") or "drive").strip()
            max_res = self._safe_positive_int(params.get("max_results"), default=10)
            return [
                "admin-reports",
                "activities",
                "list",
                "--params",
                json.dumps({"userKey": "all", "applicationName": app_name, "maxResults": max_res}),
            ]
        raise ValidationError(f"Unsupported admin action: {action}")

    def _build_forms_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "create_form":
            title = str(params.get("title") or "Untitled Form").strip()
            return ["forms", "forms", "create", "--json", json.dumps({"info": {"title": title}}, ensure_ascii=True)]
        if action == "get_form":
            form_id = self._required_text(params, "form_id")
            return ["forms", "forms", "get", "--params", json.dumps({"formId": form_id})]
        raise ValidationError(f"Unsupported forms action: {action}")

    def _build_tasks_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_tasklists":
            max_res = self._safe_positive_int(params.get("max_results"), default=10)
            return ["tasks", "tasklists", "list", "--params", json.dumps({"maxResults": max_res})]
        if action == "list_tasks":
            tl_id = str(params.get("tasklist") or "@default").strip()
            show_comp = str(params.get("show_completed") or "true").strip().lower() == "true"
            return ["tasks", "tasks", "list", "--params", json.dumps({"tasklist": tl_id, "showCompleted": show_comp})]
        if action == "create_task":
            title = self._required_text(params, "title")
            tl_id = str(params.get("tasklist") or "@default").strip()
            body = {"title": title}
            if params.get("notes"):
                body["notes"] = str(params.get("notes"))
            if params.get("due"):
                body["due"] = str(params.get("due"))
            return [
                "tasks",
                "tasks",
                "insert",
                "--params",
                json.dumps({"tasklist": tl_id}),
                "--json",
                json.dumps(body, ensure_ascii=True),
            ]
        if action == "get_task":
            tl_id = str(params.get("tasklist") or "@default").strip()
            task_id = self._required_text(params, "task_id")
            return ["tasks", "tasks", "get", "--params", json.dumps({"tasklist": tl_id, "task": task_id})]
        if action == "update_task":
            tl_id = str(params.get("tasklist") or "@default").strip()
            task_id = self._required_text(params, "task_id")
            body = {k: v for k, v in params.items() if k in ("title", "status", "notes", "due") and v is not None}
            return [
                "tasks",
                "tasks",
                "update",
                "--params",
                json.dumps({"tasklist": tl_id, "task": task_id}),
                "--json",
                json.dumps(body),
            ]
        if action == "delete_task":
            tl_id = str(params.get("tasklist") or "@default").strip()
            task_id = self._required_text(params, "task_id")
            return ["tasks", "tasks", "delete", "--params", json.dumps({"tasklist": tl_id, "task": task_id})]
        raise ValidationError(f"Unsupported tasks action: {action}")

    def _build_classroom_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_courses":
            ps = self._safe_positive_int(params.get("page_size"), default=10)
            return ["classroom", "courses", "list", "--params", json.dumps({"pageSize": ps})]
        if action == "get_course":
            course_id = self._required_text(params, "id")
            return ["classroom", "courses", "get", "--params", json.dumps({"id": course_id})]
        raise ValidationError(f"Unsupported classroom action: {action}")

    def _build_script_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_projects":
            ps = self._safe_positive_int(params.get("page_size"), default=10)
            return ["script", "projects", "list", "--params", json.dumps({"pageSize": ps})]
        if action == "get_project":
            sid = self._required_text(params, "script_id")
            return ["script", "projects", "get", "--params", json.dumps({"scriptId": sid})]
        raise ValidationError(f"Unsupported script action: {action}")

    def _build_events_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_subscriptions":
            ps = self._safe_positive_int(params.get("page_size"), default=10)
            return ["events", "subscriptions", "list", "--params", json.dumps({"pageSize": ps})]
        raise ValidationError(f"Unsupported events action: {action}")

    def _build_modelarmor_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "sanitize_text":
            text = self._required_text(params, "text")
            template = self._required_text(params, "template")
            return [
                "modelarmor",
                "+sanitize-prompt",
                "--params",
                json.dumps({"template": template}),
                "--json",
                json.dumps({"text": text}, ensure_ascii=True),
            ]
        raise ValidationError(f"Unsupported modelarmor action: {action}")

    def _build_telegram_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "send_message":
            message = self._required_text(params, "message").strip()[:4000]
            python_exe = os.environ.get("PYTHON_EXE") or sys.executable or "python"
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            script_path = os.environ.get(
                "TELEGRAM_SCRIPT_PATH", os.path.join(base_dir, "scripts", "telegram_send_message.py")
            )
            return [python_exe, script_path, message]
        raise ValidationError(f"Unsupported telegram action: {action}")

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
        if "name" in key.lower():
            variations.append("name")
        if "id" in key.lower():
            variations.append("id")
        if "code" in key.lower():
            variations.extend(["script", "python"])
        if "text" in key.lower() or "body" in key.lower() or "content" in key.lower():
            variations.extend(["text", "body", "content"])

        for k, v in params.items():
            if k.lower().replace("_", "") in variations and v is not None and str(v).strip():
                return str(v).strip()
        raise ValidationError(f"Missing required parameter: {key}")

    @staticmethod
    def _safe_positive_int(value: Any, default: int) -> int:
        try:
            parsed = int(str(value).strip())
            return parsed if parsed > 0 else default
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _build_raw_email(to_email: str, subject: str, body: str) -> str:
        message = f"To: {to_email}\r\nSubject: {subject}\r\nContent-Type: text/plain; charset=utf-8\r\nMIME-Version: 1.0\r\n\r\n{body}"
        return base64.urlsafe_b64encode(message.encode("utf-8")).decode("ascii")

    @staticmethod
    def _build_raw_email_with_attachments(to_email: str, subject: str, body: str, attachment_paths: list[str]) -> str:
        msg = email_lib.mime.multipart.MIMEMultipart("mixed")
        msg["To"], msg["Subject"], msg["MIME-Version"] = to_email, subject, "1.0"
        msg.attach(email_lib.mime.text.MIMEText(body, "plain", "utf-8"))
        for path in attachment_paths:
            # Strip [File: ] decoration if present
            if isinstance(path, str) and path.startswith("[File: ") and path.endswith("]"):
                path = path[7:-1].strip()

            if not path or not os.path.isfile(str(path)):
                continue

            filename = os.path.basename(str(path))
            try:
                with open(str(path), "rb") as fh:
                    data = fh.read()
                part = email_lib.mime.application.MIMEApplication(data, Name=filename)
                part["Content-Disposition"] = f'attachment; filename="{filename}"'
                msg.attach(part)
            except Exception:
                continue
        return base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

    @staticmethod
    def _export_drive_file_to_temp(file_id: str) -> str | None:
        try:
            if not _DRIVE_FILE_ID_RE.match(file_id):
                logging.error("Refusing to export invalid Drive file ID: %s", file_id)
                return None

            tmp_dir = tempfile.mkdtemp(prefix="gws_attach_")
            gws_exe = os.environ.get("GWS_BINARY_PATH") or os.environ.get("GWS_EXE") or "gws"
            
            # 1. Try to download directly first (works for binary files, images, PDFs already in Drive)
            safe_name = re.sub(r"[^A-Za-z0-9_-]", "", file_id)
            direct_file_path = os.path.join(tmp_dir, safe_name)
            result = subprocess.run(
                [
                    gws_exe,
                    "drive",
                    "files",
                    "get",
                    "--params",
                    json.dumps({"fileId": file_id}),
                    "-o",
                    direct_file_path,
                ],
                capture_output=True,
                timeout=30,
            )
            if result.returncode == 0 and os.path.isfile(direct_file_path) and os.path.getsize(direct_file_path) > 0:
                return direct_file_path

            # 2. If get fails (e.g. Google Docs), try exporting to PDF or CSV
            for mime_type, ext in [("application/pdf", ".pdf"), ("text/csv", ".csv")]:
                file_path = os.path.join(tmp_dir, f"{file_id}{ext}")
                result = subprocess.run(
                    [
                        gws_exe,
                        "drive",
                        "files",
                        "export",
                        "--params",
                        json.dumps({"fileId": file_id, "mimeType": mime_type}),
                        "-o",
                        file_path,
                    ],
                    capture_output=True,
                    timeout=30,
                )
                if result.returncode == 0 and os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
                    return file_path
            return None
        except Exception:
            logging.exception("Failed to export drive file to temp: %s", file_id)
            return None
