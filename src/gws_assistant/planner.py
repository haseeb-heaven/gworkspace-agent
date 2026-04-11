"""Action validation and command planning."""

from __future__ import annotations

import base64
import json
from typing import Any

from .exceptions import ValidationError
from .models import ActionSpec, ParameterSpec
from .service_catalog import SERVICES, normalize_service, supported_services


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
        raise ValidationError(f"No command builder for service: {service_key}")

    def _build_drive_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_files":
            page_size = self._safe_positive_int(params.get("page_size"), default=10)
            query = str(params.get("q") or "").strip()
            request_params: dict[str, Any] = {
                "pageSize": page_size,
                "fields": "files(id,name,mimeType,modifiedTime,webViewLink,owners(displayName,emailAddress)),nextPageToken",
            }
            if query:
                request_params["q"] = query
            return [
                "drive",
                "files",
                "list",
                "--params",
                json.dumps(request_params),
            ]
        if action == "create_folder":
            folder_name = self._required_text(params, "folder_name")
            return [
                "drive",
                "files",
                "create",
                "--json",
                json.dumps(
                    {"mimeType": "application/vnd.google-apps.folder", "name": folder_name},
                    ensure_ascii=True,
                ),
            ]
        if action == "get_file":
            file_id = self._required_text(params, "file_id")
            return ["drive", "files", "get", "--params", json.dumps({"fileId": file_id})]
        if action == "delete_file":
            file_id = self._required_text(params, "file_id")
            return ["drive", "files", "delete", "--params", json.dumps({"fileId": file_id})]
        if action == "export_file":
            file_id = self._required_text(params, "file_id")
            mime_type = str(params.get("mime_type") or "text/plain").strip()
            return [
                "drive", "files", "export",
                "--params", json.dumps({"fileId": file_id, "mimeType": mime_type}),
            ]
        raise ValidationError(f"Unsupported drive action: {action}")

    def _build_sheets_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "create_spreadsheet":
            title = self._required_text(params, "title")
            return [
                "sheets",
                "spreadsheets",
                "create",
                "--json",
                json.dumps({
                    "properties": {"title": title},
                    "sheets": [{"properties": {"title": title}}]
                }, ensure_ascii=True),
            ]
        if action == "get_spreadsheet":
            spreadsheet_id = self._required_text(params, "spreadsheet_id")
            return [
                "sheets",
                "spreadsheets",
                "get",
                "--params",
                json.dumps({"spreadsheetId": spreadsheet_id}),
            ]
        if action == "get_values":
            spreadsheet_id = self._required_text(params, "spreadsheet_id")
            range_name = self._format_range(str(params.get("range") or "Sheet1!A1:Z500"))
            return [
                "sheets",
                "spreadsheets",
                "values",
                "get",
                "--params",
                json.dumps({"spreadsheetId": spreadsheet_id, "range": range_name}),
            ]
        if action == "append_values":
            spreadsheet_id = self._required_text(params, "spreadsheet_id")
            range_name = self._format_range(str(params.get("range") or "Sheet1!A1"))
            values = params.get("values")
            if isinstance(values, str):
                values = [[values]]
            if not isinstance(values, list) or not values:
                values = [["No values supplied"]]
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
        raise ValidationError(f"Unsupported sheets action: {action}")

    def _build_gmail_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_messages":
            max_results = self._safe_positive_int(params.get("max_results"), default=10)
            query = str(params.get("q") or "").strip()
            request_params: dict[str, Any] = {
                "userId": "me",
                "maxResults": max_results,
                "fields": "messages(id,threadId),nextPageToken,resultSizeEstimate",
            }
            if query:
                request_params["q"] = query
            return [
                "gmail",
                "users",
                "messages",
                "list",
                "--params",
                json.dumps(request_params),
            ]
        if action == "get_message":
            message_id = self._required_text(params, "message_id")
            return [
                "gmail",
                "users",
                "messages",
                "get",
                "--params",
                json.dumps({"userId": "me", "id": message_id}),
            ]
        if action == "send_message":
            to_email = self._required_text(params, "to_email")
            subject = self._required_text(params, "subject")
            body = self._required_text(params, "body")
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

    def _build_calendar_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_events":
            calendar_id = str(params.get("calendar_id") or "primary").strip()
            return [
                "calendar",
                "events",
                "list",
                "--params",
                json.dumps(
                    {
                        "calendarId": calendar_id,
                        "singleEvents": True,
                        "orderBy": "startTime",
                        "maxResults": 20,
                    }
                ),
            ]
        if action == "create_event":
            summary = self._required_text(params, "summary")
            start_date_raw = self._required_text(params, "start_date")
            start_date = start_date_raw.split("T")[0]
            if len(start_date) > 10:
                start_date = start_date[:10]
            return [
                "calendar",
                "events",
                "insert",
                "--params",
                json.dumps({"calendarId": "primary"}),
                "--json",
                json.dumps({"summary": summary, "start": {"date": start_date}, "end": {"date": start_date}}, ensure_ascii=True),
            ]
        raise ValidationError(f"Unsupported calendar action: {action}")

    def _build_docs_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "get_document":
            document_id = self._required_text(params, "document_id")
            return ["docs", "documents", "get", "--params", json.dumps({"documentId": document_id})]
        if action == "create_document":
            title = self._required_text(params, "title")
            return [
                "docs", "documents", "create",
                "--json", json.dumps({"title": title}, ensure_ascii=True),
            ]
        if action == "batch_update":
            document_id = self._required_text(params, "document_id")
            text = str(params.get("text") or "").strip()
            requests_payload = [
                {
                    "insertText": {
                        "location": {"index": 1},
                        "text": text,
                    }
                }
            ]
            return [
                "docs", "documents", "batchUpdate",
                "--params", json.dumps({"documentId": document_id}),
                "--json", json.dumps({"requests": requests_payload}, ensure_ascii=True),
            ]
        raise ValidationError(f"Unsupported docs action: {action}")

    def _build_slides_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "get_presentation":
            presentation_id = self._required_text(params, "presentation_id")
            return ["slides", "presentations", "get", "--params", json.dumps({"presentationId": presentation_id})]
        raise ValidationError(f"Unsupported slides action: {action}")

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
            return [
                "chat",
                "spaces",
                "list",
                "--params",
                json.dumps({"pageSize": page_size}),
            ]
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
            return ["meet", "spaces", "list"]
        if action == "get_conference":
            name = self._required_text(params, "name")
            return [
                "meet",
                "spaces",
                "get",
                "--params",
                json.dumps({"name": name}),
            ]
        if action == "create_meeting":
            return ["meet", "spaces", "create"]
        raise ValidationError(f"Unsupported meet action: {action}")

    def _format_range(self, range_str: str) -> str:
        """Ensure sheet names with spaces are quoted correctly."""
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
        # Explicit None or empty string → check variations
        if value is not None and str(value).strip():
            return str(value)
        # Try camelCase / no-underscore variations
        variations = [key.lower().replace("_", ""), key.replace("_", "")]
        for k, v in params.items():
            if k.lower().replace("_", "") in variations and v is not None and str(v).strip():
                return str(v)
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
