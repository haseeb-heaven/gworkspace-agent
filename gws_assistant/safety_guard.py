import json
import logging
from datetime import datetime
from pathlib import Path

from gws_assistant.exceptions import SafetyBlockedError, SafetyConfirmationRequired
from gws_assistant.models import ExecutionResult

logger = logging.getLogger(__name__)


def _sanitize_for_log(value) -> str:
    text = str(value).replace("\n", "\\n").replace("\r", "\\r")
    text = text.replace("\t", "\\t")
    if len(text) > 500:
        text = text[:500] + "...[truncated]"
    return text


def _summarize_params(params: dict) -> dict:
    sensitive_keys = {
        "body", "content", "message", "text", "prompt", "query", "email", "to", "cc", "bcc",
        "subject", "file_id", "document_id", "spreadsheet_id", "calendar_id", "thread_id",
        "message_id", "access_token", "api_key", "token", "authorization",
    }
    summary: dict = {}
    for key, value in params.items():
        key_text = str(key)
        key_lower = key_text.lower()
        if key_lower in sensitive_keys:
            summary[key_text] = "[REDACTED]"
        elif isinstance(value, str):
            summary[key_text] = f"<str len={len(value)}>"
        elif isinstance(value, list):
            summary[key_text] = f"<list len={len(value)}>"
        elif isinstance(value, dict):
            summary[key_text] = f"<dict keys={sorted(str(k) for k in value.keys())}>"
        else:
            summary[key_text] = _sanitize_for_log(value)
    return summary

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
    "all files",
    "everything",
    "entire drive",
    "all emails",
    "all documents",
    "all spreadsheets",
    "wipe",
    "purge",
    "all contacts",
    "everyone",
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
        # Sanitize log fields - strip newlines from all string values to prevent log injection
        safe_params = {k: _sanitize_for_log(v) for k, v in _summarize_params(params).items()}
        log_entry = f"{timestamp} | {action} | {service} | {json.dumps(safe_params)} | {confirmed}\n"
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
            matched_keywords = [kw for kw in BULK_KEYWORDS if kw in raw_text_lower]
            cls._log_audit(
                "plan_block",
                "system",
                {"reason": "bulk_keyword_detected", "matched_keywords": matched_keywords, "task_count": len(plan.tasks)},
                False,
            )
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
            msg = f"This plan contains {destructive_count} destructive actions. Blocked for safety."
            if force_dangerous:
                # Add a hard cap even in force_dangerous mode
                if destructive_count > 10:
                    cls._log_audit("plan_block", "system", {"destructive_count": destructive_count, "reason": "exceeded force cap"}, False)
                    raise SafetyBlockedError(f"Too many destructive actions ({destructive_count}) even with --force-dangerous. Max allowed is 10.")
                else:
                    logger.warning(f"[FORCE-DANGEROUS] Allowing {destructive_count} destructive actions.")
                    cls._log_audit("plan_force_allowed", "system", {"destructive_count": destructive_count}, True)
            else:
                cls._log_audit("plan_block", "system", {"destructive_count": destructive_count}, False)
                raise SafetyBlockedError(msg + " Use --force-dangerous flag to override. This is logged.")

        if search_all_present and delete_present:
            msg = "Plan combines search_all with delete. Blocked for safety."
            cls._log_audit("plan_block", "system", {"reason": "search_all + delete"}, False)
            if not force_dangerous:
                raise SafetyBlockedError(msg)

    @classmethod
    def check_action(
        cls,
        task,
        is_dry_run: bool = False,
        no_confirm: bool = False,
        is_telegram: bool = False,
        force_dangerous: bool = False,
    ) -> str | ExecutionResult:
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
        safe_param_summary = _summarize_params(task.parameters or {})
        item_desc = f"{service}.{action} with param keys={sorted(safe_param_summary.keys())}"

        if is_dry_run:
            msg = f"[DRY-RUN] Would execute: {item_desc}"
            logger.info(msg)
            print(msg)
            return ExecutionResult(
                success=True, command=["mock"], output={"mock_success": True, "message": "Dry-run mode active"}
            )

        if no_confirm or force_dangerous:
            cls._log_audit(action, service, safe_param_summary, True)
            return "SAFE"

        if is_telegram:
            msg = f"Are you sure you want to {action} {item_desc}? (yes/no)"
            raise SafetyConfirmationRequired(
                msg,
                action_name=f"{service}.{action}",
                details=json.dumps(safe_param_summary, sort_keys=True),
            )

        # Standard CLI confirmation
        print(f"\n WARNING: You are about to perform a destructive action: {item_desc}")
        user_input = input("Are you sure you want to proceed? (y/n): ").strip().lower()
        if user_input in ("y", "yes"):
            cls._log_audit(action, service, safe_param_summary, True)
            return "SAFE"
        else:
            cls._log_audit(action, service, safe_param_summary, False)
            raise SafetyBlockedError("User aborted destructive action.")
