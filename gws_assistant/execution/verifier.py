import json
import logging
import re
import time
from typing import Any

logger = logging.getLogger(__name__)

_INVALID_STRING_PATTERNS = (
    re.compile(r"^\s*$"),
    re.compile(r"^\s*(null|nan|undefined)\s*$", re.IGNORECASE),
    re.compile(r"___UNRESOLVED_PLACEHOLDER___"),
    re.compile(r"\{\{[^{}]+\}\}"),
    re.compile(r"(?<![\w$])\$[A-Za-z_][A-Za-z0-9_.-]*"),
)


def validate_artifact_content(value: Any, source_name: str = "artifact") -> None:
    """Reject null-like or unresolved-placeholder content recursively."""
    if value is None:
        raise ValueError(f"{source_name} contains None")
    if isinstance(value, str):
        for pattern in _INVALID_STRING_PATTERNS:
            if pattern.search(value):
                raise ValueError(f"{source_name} contains invalid value: {value!r}")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            validate_artifact_content(item, f"{source_name}.{key}")
        return
    if isinstance(value, (list, tuple, set)):
        for index, item in enumerate(value):
            validate_artifact_content(item, f"{source_name}[{index}]")
        return


class TripleVerifier:
    """Fetch a Workspace resource three times and validate returned content."""

    _RESOURCE_MAP = {
        "sheets": ("get_spreadsheet", "spreadsheet_id"),
        "docs": ("get_document", "document_id"),
        "drive": ("get_file", "file_id"),
        "calendar": ("get_event", "event_id"),
        "keep": ("get_note", "name"),
        "tasks": ("get_task", "task_id"),
        "gmail": ("get_message", "message_id"),
        "slides": ("get_presentation", "presentation_id"),
        "forms": ("get_form", "form_id"),
        "chat": ("get_message", "name"),
        "contacts": ("get_person", "resourceName"),
        "admin": ("list_activities", "application_name"),
        "meet": ("get_conference", "name"),
    }

    def __init__(
        self,
        runner: Any,
        planner: Any | None = None,
        logger_: logging.Logger | None = None,
        *,
        attempts: int = 3,
        sleep_seconds: float = 0.0,
    ) -> None:
        self.runner = runner
        self.planner = planner
        self.logger = logger_ or logger
        self.attempts = attempts
        self.sleep_seconds = sleep_seconds

    def verify_resource_by_id(self, service: str, resource_id: str, expected_fields: dict[str, Any] | None = None) -> bool:
        if service not in self._RESOURCE_MAP:
            self.logger.warning("No verification mapping for service: %s", service)
            return False
        if not resource_id or not str(resource_id).strip():
            self.logger.warning("Cannot verify %s with empty resource ID.", service)
            return False

        for index in range(self.attempts):
            if index and self.sleep_seconds:
                time.sleep(self.sleep_seconds * index)

            args = self._build_command(service, resource_id)
            self.logger.info("Triple-check attempt %d/%d for %s %s.", index + 1, self.attempts, service, resource_id)
            result = self.runner.run(args)
            if not result.success:
                self.logger.warning(
                    "Triple-check failed for %s %s: %s", service, resource_id, result.error or result.stderr
                )
                return False

            payload = self._payload(result)

            # Verify payload is not empty or null
            if not payload:
                self.logger.warning("Triple-check failed for %s %s: Empty payload", service, resource_id)
                return False

            # Verify payload is not just error messages
            if isinstance(payload, str):
                if "error" in payload.lower() or "not found" in payload.lower():
                    self.logger.warning("Triple-check failed for %s %s: Error in payload: %s", service, resource_id, payload[:100])
                    return False

            try:
                self._validate_expected_fields(payload, expected_fields or {})
                # Tier 3: Verify only the explicitly required fields
                for key in expected_fields or {}:
                    validate_artifact_content(
                        payload.get(key) if isinstance(payload, dict) else payload,
                        f"{service}_verification.{key}",
                    )

                # Additional content validation based on service type
                if service == "sheets" and isinstance(payload, dict):
                    # Verify spreadsheet has sheets
                    sheets = payload.get("sheets", [])
                    if not sheets:
                        self.logger.warning("Triple-check failed for %s %s: No sheets found", service, resource_id)
                        return False

                elif service == "docs" and isinstance(payload, dict):
                    # Verify document has content
                    body = payload.get("body", {})
                    if not body or not body.get("content"):
                        self.logger.warning("Triple-check failed for %s %s: No document content", service, resource_id)
                        return False

                elif service == "gmail" and isinstance(payload, dict):
                    # Verify email has essential fields
                    if not payload.get("id") or not payload.get("threadId"):
                        self.logger.warning("Triple-check failed for %s %s: Missing email ID or threadId", service, resource_id)
                        return False

                elif service == "drive" and isinstance(payload, dict):
                    # Verify file has essential fields
                    if not payload.get("id") or not payload.get("name"):
                        self.logger.warning("Triple-check failed for %s %s: Missing file ID or name", service, resource_id)
                        return False

            except ValueError as exc:
                self.logger.warning("Triple-check validation failed for %s %s: %s", service, resource_id, exc)
                return False

        self.logger.info("Triple-check passed for %s %s.", service, resource_id)
        return True

    def _build_command(self, service: str, resource_id: str) -> list[str]:
        if service not in self._RESOURCE_MAP:
            raise ValueError(f"Unsupported service for verification: {service}")
        action, id_param = self._RESOURCE_MAP[service]
        if self.planner:
            return self.planner.build_command(service, action, {id_param: resource_id})

        if service == "calendar":
            return [
                "calendar",
                "events",
                "get",
                "--params",
                json.dumps({"calendarId": "primary", "eventId": resource_id}),
            ]
        if service == "sheets":
            return ["sheets", "spreadsheets", "get", "--params", json.dumps({"spreadsheetId": resource_id})]
        if service == "docs":
            return ["docs", "documents", "get", "--params", json.dumps({"documentId": resource_id})]
        if service == "drive":
            return ["drive", "files", "get", "--params", json.dumps({"fileId": resource_id})]
        if service == "gmail":
            return ["gmail", "users", "messages", "get", "--params", json.dumps({"userId": "me", "id": resource_id})]
        if service == "keep":
            return ["keep", "notes", "get", "--params", json.dumps({"name": resource_id})]
        if service == "tasks":
            return ["tasks", "tasks", "get", "--params", json.dumps({"tasklist": "@default", "task": resource_id})]
        if service == "slides":
            return ["slides", "presentations", "get", "--params", json.dumps({"presentationId": resource_id})]
        if service == "forms":
            return ["forms", "forms", "get", "--params", json.dumps({"formId": resource_id})]
        if service == "chat":
            return ["chat", "spaces", "messages", "get", "--params", json.dumps({"name": resource_id})]
        if service == "contacts":
            return ["people", "people", "get", "--params", json.dumps({"resourceName": resource_id, "personFields": "names,emailAddresses"})]
        if service == "admin":
            return [
                "admin-reports", "activities", "list", "--params",
                json.dumps({"userKey": "all", "applicationName": resource_id, "maxResults": 5}),
            ]
        if service == "meet":
            return ["meet", "spaces", "get", "--params", json.dumps({"name": resource_id})]
        raise ValueError(f"Unsupported service for verification: {service}")

    @staticmethod
    def _payload(result: Any) -> Any:
        from gws_assistant.json_utils import safe_json_loads

        if getattr(result, "output", None) is not None:
            return result.output
        stdout = getattr(result, "stdout", "")
        return safe_json_loads(stdout, fallback_to_string=True)

    @staticmethod
    def _validate_expected_fields(payload: Any, expected_fields: dict[str, Any]) -> None:
        if not expected_fields:
            return
        if not isinstance(payload, dict):
            raise ValueError("payload is not an object")
        for key, expected in expected_fields.items():
            actual = payload.get(key)
            if actual != expected:
                raise ValueError(f"expected {key}={expected!r}, got {actual!r}")


class VerifierMixin:
    # Type hints for mypy
    runner: Any
    planner: Any
    logger: logging.Logger

    def verify_resource(self, service: str, resource_id: str, expected_fields: dict[str, Any] | None = None) -> bool:
        verifier = TripleVerifier(self.runner, self.planner, self.logger)
        return verifier.verify_resource_by_id(service, resource_id, expected_fields)

    def _verify_artifact_content(self, value: Any, source_name: str = "artifact") -> None:
        validate_artifact_content(value, source_name)
