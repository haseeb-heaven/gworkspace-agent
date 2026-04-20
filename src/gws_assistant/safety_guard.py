import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

from gws_assistant.exceptions import SafetyBlockedError, SafetyConfirmationRequired
from gws_assistant.models import ExecutionResult

logger = logging.getLogger(__name__)

# Action categories to treat as destructive
DESTRUCTIVE_ACTIONS = {
    "drive": ["delete_file", "empty_trash", "move_to_trash"],
    "gmail": ["delete_message", "trash_message", "batch_delete", "empty_trash"],
    "sheets": ["delete_spreadsheet", "clear_all_data", "delete_sheet_tab"],
    "docs": ["delete_document"],
    "calendar": ["delete_event", "delete_calendar"],
    "contacts": ["delete_contact"],
}

# Keywords that indicate a bulk destruction attempt
BULK_KEYWORDS = [
    "all files", "everything", "entire drive", "all emails",
    "all documents", "all spreadsheets", "wipe", "purge"
]

class SafetyGuard:
    @staticmethod
    def _get_audit_log_path() -> Path:
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / "destructive_actions.log"

    @staticmethod
    def _log_audit(action: str, service: str, params: dict, confirmed: bool) -> None:
        log_path = SafetyGuard._get_audit_log_path()
        timestamp = datetime.now().isoformat()
        log_entry = f"{timestamp} | {action} | {service} | {json.dumps(params)} | {confirmed}\n"
        with open(log_path, "a") as f:
            f.write(log_entry)

    @classmethod
    def check_plan(cls, plan, force_dangerous: bool = False) -> None:
        """Scan the full task plan before execution starts."""
        destructive_count = 0
        search_all_present = False
        delete_present = False

        raw_text_lower = plan.raw_text.lower()
        if any(kw in raw_text_lower for kw in BULK_KEYWORDS):
            msg = "Plan contains bulk destruction keywords. Blocked for safety."
            cls._log_audit("plan_block", "system", {"raw_text": plan.raw_text}, False)
            if not force_dangerous:
                raise SafetyBlockedError(msg)

        for task in plan.tasks:
            service = task.service
            action = task.action

            if action in ("search_files", "search_messages"):
                # simplified check
                if not task.parameters or task.parameters.get("query") in ("*", "", None):
                     search_all_present = True

            if service in DESTRUCTIVE_ACTIONS and action in DESTRUCTIVE_ACTIONS[service]:
                destructive_count += 1
                delete_present = True

        if destructive_count > 3:
            msg = f"This plan contains {destructive_count} destructive actions. Blocked for safety. Use --force-dangerous flag to override. This is logged."
            cls._log_audit("plan_block", "system", {"destructive_count": destructive_count}, False)
            if not force_dangerous:
                raise SafetyBlockedError(msg)

        if search_all_present and delete_present:
            msg = "Plan combines search_all with delete. Blocked for safety."
            cls._log_audit("plan_block", "system", {"reason": "search_all + delete"}, False)
            if not force_dangerous:
                 raise SafetyBlockedError(msg)

    @classmethod
    def check_action(cls, task, is_dry_run: bool = False, no_confirm: bool = False, is_telegram: bool = False, force_dangerous: bool = False) -> str | ExecutionResult:
        """
        Check if an individual action is safe to execute.
        Returns "SAFE" if it can proceed normally, or an ExecutionResult if it's a dry-run mock response.
        Raises SafetyBlockedError or SafetyConfirmationRequired based on checks.
        """
        service = task.service
        action = task.action

        if service not in DESTRUCTIVE_ACTIONS or action not in DESTRUCTIVE_ACTIONS[service]:
            return "SAFE"

        # It is a destructive action
        if is_dry_run:
            msg = f"[DRY-RUN] Would execute: {service}.{action} with params: {task.parameters}"
            logger.info(msg)
            print(msg)
            return ExecutionResult(success=True, command=["mock"], output={"mock_success": True, "message": "Dry-run mode active"})

        item_desc = f"{service}.{action} with {task.parameters}"

        if no_confirm or force_dangerous:
            cls._log_audit(action, service, task.parameters, True)
            return "SAFE"

        if is_telegram:
            msg = f"Are you sure you want to {action} {item_desc}? (yes/no)"
            raise SafetyConfirmationRequired(msg, action_name=f"{service}.{action}", details=str(task.parameters))

        # Standard CLI confirmation
        print(f"\n⚠️ WARNING: You are about to perform a destructive action: {item_desc}")
        user_input = input("Are you sure you want to proceed? (y/n): ").strip().lower()
        if user_input in ('y', 'yes'):
            cls._log_audit(action, service, task.parameters, True)
            return "SAFE"
        else:
            cls._log_audit(action, service, task.parameters, False)
            raise SafetyBlockedError("User aborted destructive action.")
