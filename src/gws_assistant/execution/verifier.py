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
    """Reject empty, null-like, or unresolved-placeholder content recursively."""
    if value is None:
        raise ValueError(f"{source_name} contains None")
    if isinstance(value, str):
        for pattern in _INVALID_STRING_PATTERNS:
            if pattern.search(value):
                raise ValueError(f"{source_name} contains invalid value: {value!r}")
        return
    if isinstance(value, dict):
        if not value:
            raise ValueError(f"{source_name} is an empty object")
        for key, item in value.items():
            validate_artifact_content(item, f"{source_name}.{key}")
        return
    if isinstance(value, (list, tuple, set)):
        if not value:
            raise ValueError(f"{source_name} is an empty collection")
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

    def verify_resource(self, service: str, resource_id: str, expected_fields: dict[str, Any] | None = None) -> bool:
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
                self.logger.warning("Triple-check failed for %s %s: %s", service, resource_id, result.error or result.stderr)
                return False

            payload = self._payload(result)
            try:
                validate_artifact_content(payload, f"{service}:{resource_id}")
                self._validate_expected_fields(payload, expected_fields or {})
            except ValueError as exc:
                self.logger.warning("Triple-check content validation failed for %s %s: %s", service, resource_id, exc)
                return False

        self.logger.info("Triple-check passed for %s %s.", service, resource_id)
        return True

    def _build_command(self, service: str, resource_id: str) -> list[str]:
        action, id_param = self._RESOURCE_MAP[service]
        if self.planner:
            return self.planner.build_command(service, action, {id_param: resource_id})

        if service == "calendar":
            return ["calendar", "events", "get", "--params", json.dumps({"calendarId": "primary", "eventId": resource_id})]
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
            return ["tasks", "tasks", "get", "--params", json.dumps({"task": resource_id})]
        raise ValueError(f"Unsupported service for verification: {service}")

    @staticmethod
    def _payload(result: Any) -> Any:
        if getattr(result, "output", None) is not None:
            return result.output
        stdout = getattr(result, "stdout", "")
        try:
            return json.loads(stdout)
        except Exception:
            return stdout

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
    def verify_resource(self, service: str, resource_id: str, expected_fields: dict[str, Any] | None = None) -> bool:
        verifier = TripleVerifier(self.runner, self.planner, self.logger)
        return verifier.verify_resource(service, resource_id, expected_fields)

    def _verify_artifact_content(self, value: Any, source_name: str = "artifact") -> None:
        validate_artifact_content(value, source_name)
