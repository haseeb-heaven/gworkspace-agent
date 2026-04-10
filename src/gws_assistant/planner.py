"""Action validation and command planning."""

from __future__ import annotations

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
        raise ValidationError(f"No command builder for service: {service_key}")

    def _build_drive_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_files":
            page_size = self._safe_positive_int(params.get("page_size"), default=10)
            return [
                "drive",
                "files",
                "list",
                "--params",
                json.dumps({"pageSize": page_size}),
                "--format",
                "table",
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
        raise ValidationError(f"Unsupported drive action: {action}")

    def _build_sheets_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "create_spreadsheet":
            title = self._required_text(params, "title")
            return [
                "sheets",
                "spreadsheets",
                "create",
                "--json",
                json.dumps({"properties": {"title": title}}, ensure_ascii=True),
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
        raise ValidationError(f"Unsupported sheets action: {action}")

    def _build_gmail_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_messages":
            max_results = self._safe_positive_int(params.get("max_results"), default=10)
            return [
                "gmail",
                "users",
                "messages",
                "list",
                "--params",
                json.dumps({"userId": "me", "maxResults": max_results}),
                "--format",
                "table",
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
        raise ValidationError(f"Unsupported gmail action: {action}")

    def _build_calendar_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_events":
            calendar_id = str(params.get("calendar_id") or "primary").strip()
            return [
                "calendar",
                "events",
                "list",
                "--params",
                json.dumps({"calendarId": calendar_id}),
                "--format",
                "table",
            ]
        if action == "create_event":
            summary = self._required_text(params, "summary")
            start_date = self._required_text(params, "start_date")
            return [
                "calendar",
                "events",
                "insert",
                "--params",
                json.dumps({"calendarId": "primary"}),
                "--json",
                json.dumps({"summary": summary, "start": {"date": start_date}}, ensure_ascii=True),
            ]
        raise ValidationError(f"Unsupported calendar action: {action}")

    @staticmethod
    def _required_text(params: dict[str, Any], key: str) -> str:
        value = str(params.get(key) or "").strip()
        if not value:
            raise ValidationError(f"Missing required parameter: {key}")
        return value

    @staticmethod
    def _safe_positive_int(value: Any, default: int) -> int:
        try:
            parsed = int(str(value).strip())
            return parsed if parsed > 0 else default
        except Exception:
            return default

