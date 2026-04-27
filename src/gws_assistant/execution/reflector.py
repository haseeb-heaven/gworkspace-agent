import logging
from typing import Any
from gws_assistant.exceptions import APIErrorType, classify_api_error
from gws_assistant.models import ReflectionDecision


class ReflectorMixin:
    """Mixin for analyzing errors and reflecting on execution outcomes."""

    def reflect_on_error(self, error: str | None, attempts: int, max_retries: int) -> tuple[ReflectionDecision, bool]:
        """
        Analyze execution error and return (decision, abort_plan).
        """
        abort_plan = False

        if not error:
            decision = ReflectionDecision(action="continue", reason="Task completed successfully.")
        elif "CODE_EXECUTION_ENABLED=false" in str(error):
            decision = ReflectionDecision(action="continue", reason="Code execution is disabled by configuration.")
        elif (
            "declined by user in sandbox" in str(error).lower()
            or "blocked by read-only mode" in str(error).lower()
            or "declined by user" in str(error).lower()
        ):
            decision = ReflectionDecision(
                action="continue", reason="Action blocked by safety policy or user. Aborting plan."
            )
            abort_plan = True
        elif "unresolved placeholder" in str(error).lower() or "unresolved stub" in str(error).lower():
            decision = ReflectionDecision(action="continue", reason="Deterministic placeholder error; skip retry.")
            abort_plan = True
        elif attempts < max_retries:
            error_str = str(error)
            error_type = classify_api_error(stderr=error_str, stdout="")
            if error_type in (APIErrorType.SERVER, APIErrorType.UNKNOWN):
                decision = ReflectionDecision(
                    action="retry", reason=f"Retrying transient/unknown error ({error_type.value})."
                )
            else:
                decision = ReflectionDecision(
                    action="continue", reason=f"Permanent or specific error ({error_type.value}); skip retry."
                )
                abort_plan = True
        else:
            decision = ReflectionDecision(action="replan", reason="Retries exhausted.")

        return decision, abort_plan
