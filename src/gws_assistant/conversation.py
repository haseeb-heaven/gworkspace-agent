"""Conversation orchestration logic."""

from __future__ import annotations

import logging
from typing import Any

from .exceptions import ValidationError
from .models import ExecutionResult, Intent, ParameterSpec
from .output_formatter import HumanReadableFormatter
from .planner import CommandPlanner
from .service_catalog import SERVICES


class ConversationEngine:
    """Coordinates parsing, validation, follow-up prompts, and execution."""

    def __init__(
        self,
        planner: CommandPlanner,
        logger: logging.Logger,
    ) -> None:
        self.planner = planner
        self.logger = logger

    def needs_service_clarification(self, intent: Intent) -> bool:
        if not intent.service:
            return True
        return intent.service not in SERVICES

    def service_clarification_message(self) -> str:
        supported = ", ".join(self.planner.list_services())
        return f"Please choose one supported service: {supported}"

    def action_choices(self, service: str) -> list[str]:
        return [action.key for action in self.planner.list_actions(service)]

    def parameter_specs(self, service: str, action: str) -> tuple[ParameterSpec, ...]:
        return self.planner.required_parameters(service, action)

    def merge_parameters(
        self,
        intent: Intent,
        interactive_parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        merged = dict(intent.parameters)
        if interactive_parameters:
            merged.update({k: v for k, v in interactive_parameters.items() if v is not None})
        return merged

    def build_command(self, service: str, action: str, parameters: dict[str, Any]) -> list[str]:
        return self.planner.build_command(service, action, parameters)

    def validate_selection(self, service: str | None, action: str | None) -> tuple[str, str]:
        if not service:
            raise ValidationError("Service is required.")
        service_key = self.planner.ensure_service(service)
        action_key = self.planner.ensure_action(service_key, action)
        return service_key, action_key

    @staticmethod
    def format_result(result: ExecutionResult) -> str:
        return HumanReadableFormatter().format_execution_result(result)
