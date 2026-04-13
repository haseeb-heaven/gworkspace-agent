"""Plan execution service for ordered Google Workspace tasks."""

from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from .drive_query_builder import sanitize_drive_query
from .exceptions import APIErrorType, ValidationError, classify_api_error
from .gmail_query_builder import sanitize_gmail_query
from .gws_runner import GWSRunner
from .models import (
    ExecutionResult,
    PlanExecutionReport,
    PlannedTask,
    RequestPlan,
    TaskExecution,
    validate_planned_task,
)
from .planner import CommandPlanner, UnsupportedServiceError
from .relevance import extract_keywords, filter_drive_files, filter_gmail_messages

try:
    from .tools.web_search import web_search_tool
except Exception:  # pragma: no cover
    web_search_tool = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

_RECEIPT_SENDER_PATTERNS = re.compile(
    r"(noreply|no-reply|invoice|receipt|statements|do-not-reply|donotreply"
    r"|notifications?|billing|payments?|stripe\.com|paypal\.com|x\.com|twitter\.com)",
    re.IGNORECASE,
)

_CURRENCY_SIGNAL_RE = re.compile(
    r"\b(usd|inr|eur|gbp|jpy|cad|aud|chf|cny|rupee|dollar|euro|pound|yen"
    r"|exchange.?rate|conversion.?rate|forex|fx|rate|price|cost)\b",
    re.IGNORECASE,
)

_TASK_ID_PAT = r"(\d+|task-\d+|t\d+|t-\d+)"

_ARRAY_WILDCARD_RE = re.compile(
    fr"\{{{_TASK_ID_PAT}\.(\w+)\[\*\]\.(\w+)\}}"
)

_DOT_SENDER_REF_RE = re.compile(
    fr"\{{{_TASK_ID_PAT}\.(sender\.name|sender\.email|senderName|senderEmail"
    r"|sender_name|sender_email|fromName|from_name|fromEmail|from_email"
    r"|from\.name|from\.email"
    r"|subject|date|snippet|body)\}"
)

_HEADERS_DOT_REF_RE = re.compile(
    fr"\{{{_TASK_ID_PAT}\.headers\.(from\.name|from\.email|from|subject|date|snippet|to|cc|bcc)\}}",
    re.IGNORECASE,
)

_TEMPLATE_REF_RE = re.compile(fr"\{{{_TASK_ID_PAT}\.[\w\.\[\]\*]+\}}")

_GMAIL_BODY_VARIANTS: tuple[str, ...] = (
    "$gmail_message_body",
    "$gmail_messages_body",
    "$gmail_body",
    "$email_bodies",
    "$email_body",
    "$gmail_message_bodies",
    "$messages_body",
    "$message_body",
)

_DRIVE_FILE_REF_RE = re.compile(
    r"\{[^}]+\.files\[(\d+)\]\.(\w+)\}",
    re.IGNORECASE,
)

_SENDER_FIELD_ALIASES: dict[str, tuple[str, str]] = {
    "sendername":   ("from", "name"),
    "sender.name":  ("from", "name"),
    "sender_name":  ("from", "name"),
    "fromname":     ("from", "name"),
    "from_name":    ("from", "name"),
    "from.name":    ("from", "name"),
    "from.email":   ("from", "email"),
    "senderemail":  ("from", "email"),
    "sender.email": ("from", "email"),
    "sender_email": ("from", "email"),
    "fromemail":    ("from", "email"),
    "from_email":   ("from", "email"),
    "subject":      ("subject", "raw"),
    "date":         ("date", "raw"),
    "snippet":      ("snippet", "raw"),
    "body":         ("body", "body"),
}

_HEADERS_FIELD_ALIASES: dict[str, tuple[str, str]] = {
    "from.name":  ("from", "name"),
    "from.email": ("from", "email"),
    "from":       ("from", "raw"),
    "subject":    ("subject", "raw"),
    "date":       ("date", "raw"),
    "snippet":    ("snippet", "raw"),
    "to":         ("to", "raw"),
    "cc":         ("cc", "raw"),
    "bcc":        ("bcc", "raw"),
}

# ---------------------------------------------------------------------------
# Constants for data truncation & thresholds
# ---------------------------------------------------------------------------

_MAX_EXPAND_MESSAGES                = 5
_MAX_DRIVE_SUMMARY_FILES            = 50
_MAX_GMAIL_SUMMARY_MESSAGES_VERBOSE = 100
_MAX_GMAIL_SUMMARY_MESSAGES         = 50
_MAX_SHEET_UI_ROWS                  = 200
_DOCS_MIN_CHAR_THRESHOLD            = 50
_DEFAULT_SHEETS_CHECK_RANGE         = "A1:E20"
_GOOGLE_DOCS_URL_TEMPLATE           = "https://docs.google.com/document/d/{doc_id}/edit"


# ---------------------------------------------------------------------------
# Fix #2 — structured reflection advice
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class _ReflectionAdvice:
    """Internal result of _reflect_on_failure() — typed, not a raw string."""
    error_type: APIErrorType
    should_retry: bool
    suggestion: str
    summary: str

    def __str__(self) -> str:
        return (
            f"[{self.error_type.value}] {self.summary} "
            f"| retry={self.should_retry} | hint: {self.suggestion}"
        )


# ---------------------------------------------------------------------------
# PlanExecutor
# ---------------------------------------------------------------------------

class PlanExecutor:
    """Executes planned gws tasks sequentially and carries context forward."""

    def __init__(self, planner: CommandPlanner, runner: GWSRunner, logger: logging.Logger, config=None) -> None:
        self.planner = planner
        self.runner  = runner
        self.logger  = logger
        self.config  = config

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def execute(self, plan: RequestPlan) -> PlanExecutionReport:
        """Execute all tasks in the plan sequentially, threading context forward."""
        context: dict[str, Any] = {"request_text": plan.raw_text}

        for task in plan.tasks:
            if task.service == "gmail" and task.action == "send_message":
                addr = str(task.parameters.get("to_email") or "").strip()
                if addr and "@" in addr and not _RECEIPT_SENDER_PATTERNS.search(addr):
                    context["explicit_to_email"] = addr
                    break

        executions:   list[TaskExecution] = []
        thought_trace: list[dict]         = []
        task_list     = list(plan.tasks)
        current_index = 0

        while current_index < len(task_list):
            task = task_list[current_index]
            for expanded_task in self._expand_task(task, context):
                thought = self._think(goal=plan.raw_text, context=context, next_task=expanded_task)
                self.logger.info("Thought [step %d]: %s", current_index + 1, thought)

                resolved_task = self._resolve_task(expanded_task, context)
                result        = self.execute_single_task(resolved_task, context)
                executions.append(TaskExecution(task=resolved_task, result=result))

                context["last_observation"] = result.stdout
                thought_trace.append({
                    "step":        current_index + 1,
                    "thought":     thought,
                    "action":      f"{resolved_task.service}.{resolved_task.action}",
                    "observation": (result.stdout or "")[:(self.config.max_context_snippet_len if self.config else 300)],
                    "success":     result.success,
                })

                if not result.success:
                    advice = self._reflect_on_failure(resolved_task, result, context)
                    self.logger.warning("Reflection: %s", advice)
                    context["last_reflection"] = str(advice)

                    # Fix #2 — branch on error type, never blindly retry.
                    recovered = self._handle_failure(
                        task=resolved_task,
                        result=result,
                        advice=advice,
                        executions=executions,
                        context=context,
                    )
                    if recovered is not None:
                        # Replace the failed execution entry with the recovered one.
                        executions[-1] = TaskExecution(task=resolved_task, result=recovered)
                        context["last_observation"] = recovered.stdout
                        thought_trace[-1]["success"] = recovered.success
                    else:
                        self.logger.warning(
                            "Task failed id=%s (%s); continuing to capture full trace.",
                            resolved_task.id, advice.error_type.value,
                        )

                if self._should_replan(thought, result, context):
                    new_tasks = self._replan(plan.raw_text, context)
                    if new_tasks:
                        task_list[current_index + 1:] = new_tasks
                        self.logger.info("Re-planned: %d new tasks injected.", len(new_tasks))

            current_index += 1

        report = PlanExecutionReport(plan=plan, executions=executions, thought_trace=thought_trace)

        from .memory import save_episode
        save_episode(
            goal=plan.raw_text,
            tasks=[
                {"service": e.task.service, "action": e.task.action, "success": e.result.success}
                for e in executions
            ],
            outcome="success" if all(e.result.success for e in executions) else "partial_failure",
        )
        return report

    # ------------------------------------------------------------------
    # Fix #2 — error-type-aware failure handler
    # ------------------------------------------------------------------

    def _handle_failure(
        self,
        task: PlannedTask,
        result: ExecutionResult,
        advice: "_ReflectionAdvice",
        executions: list[TaskExecution],
        context: dict[str, Any],
    ) -> ExecutionResult | None:
        """Return a recovered ExecutionResult or None (caller continues).

        Branching logic:
          INVALID_QUERY → re-sanitize the query param and retry ONCE.
          AUTH          → permanent failure, no retry.
          RATE_LIMIT    → skip, warn caller to back off.
          SERVER        → let the existing runner retry mechanism handle it.
          NOT_FOUND     → skip permanently.
          UNKNOWN       → log and continue (preserve old behaviour).
        """
        et = advice.error_type

        if et == APIErrorType.INVALID_QUERY:
            return self._retry_with_sanitized_query(task, context)

        if et == APIErrorType.AUTH:
            self.logger.error(
                "Auth failure on task id=%s — check credentials / token expiry.", task.id
            )
            return None  # permanent, do not retry

        if et == APIErrorType.RATE_LIMIT:
            self.logger.warning(
                "Rate-limit hit on task id=%s — skipping to avoid further quota burn.", task.id
            )
            return None

        if et == APIErrorType.NOT_FOUND:
            self.logger.warning("Resource not found for task id=%s — skipping.", task.id)
            return None

        # SERVER / UNKNOWN — runner's run_with_retry already fired; just continue.
        return None

    def _retry_with_sanitized_query(
        self, task: PlannedTask, context: dict[str, Any]
    ) -> ExecutionResult | None:
        """Re-sanitize the 'q' parameter and resubmit the task exactly ONCE.

        Only applies to drive.list_files and gmail.list_messages.
        Returns the new ExecutionResult, or None if retry is not applicable.
        """
        if task.service not in ("drive", "gmail"):
            return None
        if task.action not in ("list_files", "list_messages"):
            return None

        raw_q = str(task.parameters.get("q") or "").strip()
        if not raw_q:
            return None

        if task.service == "drive":
            # Force fullText fallback: strip any structured syntax and use fullText.
            strip_chars = chr(39) + '"'
            safe_q = "fullText contains '{}'".format(raw_q.strip(strip_chars))
            self.logger.info(
                "INVALID_QUERY retry (drive): q=%r → fullText fallback q=%r", raw_q, safe_q
            )
        else:
            # Gmail: strip the query entirely and let the runner return all messages.
            safe_q = sanitize_gmail_query(raw_q)
            self.logger.info(
                "INVALID_QUERY retry (gmail): q=%r → sanitized q=%r", raw_q, safe_q
            )

        fixed_params = {**task.parameters, "q": safe_q}
        fixed_task = PlannedTask(
            id=task.id,
            service=task.service,
            action=task.action,
            parameters=fixed_params,
            reason=task.reason,
        )
        try:
            args = self.planner.build_command(fixed_task.service, fixed_task.action, fixed_task.parameters)
            result = self.runner.run(args)
            parsed_payload = _parse_json(result.stdout)
            result.output = {
                "command":        result.command,
                "stdout":         result.stdout,
                "stderr":         result.stderr,
                "parsed_payload": parsed_payload,
            }
            self._update_context(fixed_task, result.stdout, context)
            self.logger.info(
                "INVALID_QUERY retry succeeded=%s for task id=%s", result.success, task.id
            )
            return result
        except Exception as exc:
            self.logger.warning("INVALID_QUERY retry also failed for task id=%s: %s", task.id, exc)
            return None

    # ------------------------------------------------------------------
    # Single task execution
    # ------------------------------------------------------------------

    def execute_single_task(self, task: PlannedTask, context: dict[str, Any]) -> ExecutionResult:
        """Executes a single fully-resolved task and updates the context."""
        if task.service == "search":
            return self._execute_web_search(task, context)

        if task.service in ("code", "computation"):
            return self._execute_code_task(task, context)

        # Fix #1 — validate PlannedTask schema before anything else.
        try:
            validate_planned_task(task)
        except ValidationError as exc:
            self.logger.warning("Schema validation failed for task id=%s: %s", task.id, exc)
            return ExecutionResult(
                success=False,
                command=[],
                error=f"Schema validation error: {exc}",
            )

        placeholder = _find_unresolved_placeholder(task.parameters)
        if placeholder:
            return ExecutionResult(
                success=False,
                command=[],
                error=f"Plan contained an unresolved placeholder: {placeholder}",
            )

        try:
            args = self.planner.build_command(task.service, task.action, task.parameters)
        except UnsupportedServiceError as exc:
            self.logger.warning(
                "Task id=%s skipped (unsupported service '%s'): %s", task.id, task.service, exc
            )
            return ExecutionResult(success=True, command=[], stdout="", error=None)
        except ValidationError as exc:
            self.logger.warning("Task id=%s build_command failed: %s", task.id, exc)
            return ExecutionResult(success=False, command=[], error=str(exc))

        # Fix #4 guard — assert args is a well-formed list[str] before subprocess.
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            bad = repr(args)[:120]
            self.logger.error("build_command returned non-list or non-str args: %s", bad)
            return ExecutionResult(
                success=False,
                command=[],
                error=f"Command construction error: expected list[str], got {bad}",
            )

        if hasattr(self.runner, "run_with_retry"):
            result = self.runner.run_with_retry(args)
        else:
            result = self.runner.run(args)

        # Fix #5 — guarantee result.error is always set when success=False.
        if not result.success and not result.error:
            result.error = (
                result.stderr.strip()
                or result.stdout.strip()
                or f"Task {task.service}.{task.action} failed with return_code={result.return_code}"
            )

        parsed_payload = _parse_json(result.stdout)
        result.output = {
            "command":        result.command,
            "stdout":         result.stdout,
            "stderr":         result.stderr,
            "parsed_payload": parsed_payload,
        }
        self._update_context(task, result.stdout, context)

        verification_error = self._verify_artifact_content(task, result, context)
        if verification_error:
            self.logger.warning("Verification failed for task %s: %s", task.id, verification_error)
            result.success = False
            # Fix #5 — verification failures must set error (was missing before).
            result.error = f"Verification Failure: {verification_error}"

        return result

    # ------------------------------------------------------------------
    # Artifact verification (unchanged logic, error always set now)
    # ------------------------------------------------------------------

    def _verify_artifact_content(self, task: PlannedTask, result: ExecutionResult, context: dict[str, Any]) -> str | None:
        if not result.success:
            return None

        if task.service == "docs" and task.action == "create_document":
            doc_id = (result.output.get("parsed_payload") or {}).get("documentId")
            if not doc_id:
                return "No document ID found in output after creation."
            fetch_res = self.runner.run(["docs", "documents", "get", "--params", json.dumps({"documentId": doc_id})])
            if fetch_res.return_code != 0:
                return f"Failed to fetch document for verification: {fetch_res.stderr}"
            content = fetch_res.stdout
            if len(content.strip()) < _DOCS_MIN_CHAR_THRESHOLD:
                return "Newly created document is nearly empty."
            if "{{" in content or "placeholder" in content.lower():
                return "Document contains unresolved placeholders."

        if task.service == "sheets" and task.action in ("append_values", "create_spreadsheet"):
            sheet_id = context.get("last_spreadsheet_id") or (result.output.get("parsed_payload") or {}).get("spreadsheetId")
            if not sheet_id:
                return None
            if task.action == "append_values":
                range_val = task.parameters.get("range") or _DEFAULT_SHEETS_CHECK_RANGE
                check_res = self.runner.run(["sheets", "spreadsheets", "values", "get", "--params",
                                             json.dumps({"spreadsheetId": sheet_id, "range": range_val})])
                if "{{" in check_res.stdout or "No data" in check_res.stdout:
                    return "Spreadsheet data contains placeholders or is missing."

        if task.service == "gmail" and task.action == "send_message":
            search_res = self.runner.run(["gmail", "users", "messages", "list", "--params",
                                          json.dumps({"userId": "me", "maxResults": 1, "q": "label:SENT"})])
            if search_res.return_code == 0:
                payload = _parse_json(search_res.stdout)
                msgs    = payload.get("messages") if isinstance(payload, dict) else []
                if msgs:
                    msg_id  = msgs[0]["id"]
                    get_res = self.runner.run(["gmail", "users", "messages", "get", "--params",
                                              json.dumps({"userId": "me", "id": msg_id})])
                    content = get_res.stdout
                    if "{{" in content or "{task" in content:
                        return "Sent email contains unresolved placeholders."

        return None

    # ------------------------------------------------------------------
    # Think / replan
    # ------------------------------------------------------------------

    def _think(self, goal: str, context: dict, next_task: PlannedTask) -> str:
        try:
            from .langchain_agent import create_agent
            agent = create_agent(self.config, self.logger)
            if not agent:
                return "No LLM configured — proceeding with planned task."
            prompt = (
                f"Goal: {goal}\n"
                f"Completed steps: {len(context.get('task_results', {}))}\n"
                f"Last observation: {str(context.get('last_observation', 'None'))[:(self.config.max_context_snippet_len if self.config else 300)]}\n"
                f"Last reflection: {str(context.get('last_reflection', 'None'))[:(self.config.max_context_snippet_len if self.config else 200)]}\n"
                f"Next planned action: {next_task.service}.{next_task.action}\n"
                f"Parameters: {list(next_task.parameters.keys())}\n\n"
                "In one sentence: Is this the right next step? "
                "If not, state what should change. Be concise."
            )
            response = agent.invoke(prompt)
            return getattr(response, "content", str(response)).strip()
        except Exception as exc:
            self.logger.warning("_think() failed: %s", exc)
            return "Thought step skipped due to LLM error."

    def _should_replan(self, thought: str, result: ExecutionResult, context: dict) -> bool:
        if not result.success:
            return False
        lower_thought = thought.lower()
        return any(s in lower_thought for s in ("should change", "instead", "wrong step", "incorrect", "skip", "replan"))

    def _replan(self, goal: str, context: dict) -> list[PlannedTask]:
        try:
            from .langchain_agent import plan_with_langchain
            new_plan = plan_with_langchain(goal, self.config, self.logger)
            if new_plan and new_plan.tasks:
                completed_count = len(context.get("task_results", {}))
                return new_plan.tasks[completed_count:]
        except Exception as exc:
            self.logger.warning("_replan() failed: %s", exc)
        return []

    # ------------------------------------------------------------------
    # Fix #2 — structured reflection
    # ------------------------------------------------------------------

    def _reflect_on_failure(
        self, task: PlannedTask, result: ExecutionResult, context: dict
    ) -> "_ReflectionAdvice":
        """Return a typed _ReflectionAdvice instead of a raw string.

        classify_api_error() inspects stderr + stdout to determine the
        error category; the advice struct carries should_retry so callers
        never need to string-match to decide what to do.
        """
        error_type = classify_api_error(
            stderr=result.stderr or "",
            stdout=result.stdout or "",
        )
        # Also check result.error string (may carry synthesized messages).
        if error_type == APIErrorType.UNKNOWN and result.error:
            error_type = classify_api_error(stderr=result.error, stdout="")

        should_retry = error_type == APIErrorType.SERVER

        _SUGGESTIONS: dict[APIErrorType, str] = {
            APIErrorType.INVALID_QUERY: "Re-sanitize the query parameter with a fullText fallback.",
            APIErrorType.AUTH:          "Check OAuth token expiry and credentials file.",
            APIErrorType.RATE_LIMIT:    "Back off and retry after quota resets.",
            APIErrorType.SERVER:        "Transient server error — runner will retry automatically.",
            APIErrorType.NOT_FOUND:     "The requested resource does not exist; skip this task.",
            APIErrorType.UNKNOWN:       "Check required IDs are resolved in context.",
        }

        summary = (
            f"Task {task.id} ({task.service}.{task.action}) failed. "
            f"Error: {result.error or result.stderr or 'unknown'}. "
            f"Parameters used: {list(task.parameters.keys())}."
        )

        return _ReflectionAdvice(
            error_type=error_type,
            should_retry=should_retry,
            suggestion=_SUGGESTIONS[error_type],
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Web search / code execution
    # ------------------------------------------------------------------

    def _execute_code_task(self, task: PlannedTask, context: dict[str, Any]) -> ExecutionResult:
        from .tools.code_execution import execute_generated_code
        code = str(task.parameters.get("code") or "").strip()
        if not code:
            return ExecutionResult(success=False, command=[], error="Missing required parameter: code")

        structured = execute_generated_code(code, config=self.config or self.planner.config)
        output     = structured.get("output") or {}
        stdout     = output.get("stdout") or ""
        parsed_value = output.get("parsed_value")

        results_map = context.setdefault("task_results", {})
        results_map[task.id] = output
        if task.id.startswith("task-"):
            results_map[task.id.removeprefix("task-")] = output

        context["last_code_stdout"] = stdout.strip()
        context["last_code_result"] = str(parsed_value) if parsed_value is not None else stdout.strip()
        _ingest_code_stdout_into_context(stdout, context)

        result = ExecutionResult(success=structured["success"], command=["code_execution"], stdout=stdout)
        result.output = {
            "command":      result.command,
            "stdout":       stdout,
            "stderr":       output.get("stderr") or "",
            "parsed_payload": output,
            "parsed_value": parsed_value,
        }
        if not structured["success"]:
            result.error = structured.get("error") or "Code execution failed."
        return result

    def _execute_web_search(self, task: PlannedTask, context: dict[str, Any]) -> ExecutionResult:
        query       = str(task.parameters.get("query") or "").strip()
        max_results = int(task.parameters.get("max_results") or 5)
        try:
            payload = web_search_tool.invoke({"query": query, "max_results": max_results})
        except Exception as exc:
            return ExecutionResult(success=False, command=[], error=str(exc))

        results = payload.get("results") or []
        error   = payload.get("error")
        if error and not results:
            return ExecutionResult(success=False, command=[], error=error)

        context["web_search_query"]   = query
        context["web_search_results"] = results
        stdout = json.dumps(payload)
        result = ExecutionResult(success=True, command=["web_search", query], stdout=stdout)
        result.output = {"command": result.command, "stdout": stdout, "stderr": "", "parsed_payload": payload}

        results_map = context.setdefault("task_results", {})
        results_map[task.id] = payload
        if task.id.startswith("task-"):
            try:
                results_map[task.id.removeprefix("task-")] = payload
            except Exception:
                pass
        return result

    # ------------------------------------------------------------------
    # Task expansion / resolution
    # ------------------------------------------------------------------

    def _expand_task(self, task: PlannedTask, context: dict[str, Any]) -> list[PlannedTask]:
        if task.service != "gmail" or task.action != "get_message":
            return [task]
        message_id = str(task.parameters.get("message_id") or "").strip()
        if message_id == "$gmail_message_ids":
            message_id = ""
        if message_id and not _is_placeholder(message_id):
            return [task]
        message_ids = _gmail_message_ids(context)
        if not message_ids:
            self.logger.info("Skipping gmail.get_message task id=%s — no message IDs returned.", task.id)
            return []
        return [
            PlannedTask(
                id=f"{task.id}-{idx}",
                service=task.service,
                action=task.action,
                parameters={**task.parameters, "message_id": mid},
                reason=task.reason,
            )
            for idx, mid in enumerate(message_ids[:_MAX_EXPAND_MESSAGES], start=1)
        ]

    def _resolve_task(self, task: PlannedTask, context: dict[str, Any]) -> PlannedTask:
        """Resolve all placeholder tokens in a task’s parameters before execution."""
        parameters = _resolve_dot_sender_refs(task.parameters, context, self.logger)
        parameters = _resolve_array_wildcard_refs(parameters, context, self.logger)
        parameters = _resolve_headers_dot_refs(parameters, context, self.logger)
        parameters = _resolve_template(parameters, context, self.logger)
        parameters = _resolve_bare_step_id_params(parameters, context)

        if context.get("web_search_results"):
            parameters = _resolve_search_extraction_params(parameters, context, self.logger)

        if context.get("last_code_stdout") or context.get("last_code_result"):
            parameters = _resolve_code_output_params(parameters, context, self.logger)

        parameters = _resolve_gmail_body_variants(parameters, context, self.logger)

        if context.get("drive_payload"):
            parameters = _resolve_drive_file_refs(parameters, context, self.logger)

        parameters = _resolve_nested_dollar(parameters, context, self)

        # Pass 7 — attachment path resolution for gmail.send_message
        if task.service == "gmail" and task.action == "send_message":
            attach_val = parameters.get("attachments")
            if isinstance(attach_val, str) and attach_val.strip() in (
                "$drive_export_file", "$drive_export_path", "$drive_file_path",
            ):
                resolved_path = context.get("drive_export_file") or ""
                if resolved_path:
                    self.logger.info(
                        "Pass7-attach: resolved attachments '%s' → local path '%s'",
                        attach_val, resolved_path,
                    )
                    parameters["attachments"] = resolved_path
                else:
                    self.logger.warning(
                        "Pass7-attach: '%s' requested but no drive_export_file in context; "
                        "email will be sent without attachment.", attach_val,
                    )
                    parameters.pop("attachments", None)

        # Legacy $ resolution
        for key, value in list(parameters.items()):
            if value == "$last_spreadsheet_id":
                parameters[key] = context.get("last_spreadsheet_id") or ""
            elif value == "$gmail_summary_values":
                parameters[key] = self._gmail_summary_values(context)
            elif value == "$sheet_email_body":
                parameters[key] = self._sheet_email_body(context)
            elif value == "$drive_summary_values":
                parameters[key] = self._drive_summary_values(context)
            elif value == "$drive_export_file":
                parameters[key] = context.get("drive_export_content") or context.get("drive_export_file") or ""
                self.logger.info("Pass7: resolved $drive_export_file → %d chars", len(parameters[key]))
            elif value == "$web_search_markdown":
                parameters[key] = _web_search_markdown(context)
            elif value == "$web_search_table_values":
                parameters[key] = _web_search_table_values(context)
            elif isinstance(value, str) and _is_gmail_values_placeholder(value) and key in ("body", "values"):
                parameters[key] = self._gmail_summary_values(context)
            elif isinstance(value, str) and _is_sheet_body_placeholder(value) and key in ("body", "values"):
                parameters[key] = self._sheet_email_body(context)
            elif isinstance(value, str) and "$drive_summary" in value.lower() and key in ("body", "values"):
                parameters[key] = self._drive_summary_values(context)

            if key == "body" and isinstance(parameters[key], str):
                link = context.get("last_spreadsheet_url")
                if link and link not in parameters[key] and ("link" in parameters[key].lower() or "sheet" in parameters[key].lower()):
                    parameters[key] = f"{parameters[key]}\n\nLink to spreadsheet: {link}"
                doc_link = context.get("last_document_url")
                if doc_link and doc_link not in parameters[key]:
                    parameters[key] = f"{parameters[key]}\n\nLink to document: {doc_link}"

        if "spreadsheet_id" not in parameters and context.get("last_spreadsheet_id"):
            parameters["spreadsheet_id"] = context["last_spreadsheet_id"]
        if "document_id" not in parameters and context.get("last_document_id"):
            parameters["document_id"] = context["last_document_id"]
        if "folder_id" not in parameters and context.get("last_folder_id"):
            parameters["folder_id"] = context["last_folder_id"]
        if "message_id" not in parameters and context.get("last_message_id"):
            parameters["message_id"] = context["last_message_id"]

        if task.service == "gmail" and task.action == "send_message":
            to_email_val = str(parameters.get("to_email") or "").strip()
            explicit     = str(context.get("explicit_to_email") or "").strip()
            if explicit and "@" in explicit:
                parameters["to_email"] = explicit
            elif not to_email_val or _is_placeholder(to_email_val) or _RECEIPT_SENDER_PATTERNS.search(to_email_val):
                resolved_addr = _resolve_to_email_from_context(context)
                if resolved_addr:
                    self.logger.info("Auto-resolved to_email from context: %s", resolved_addr)
                    parameters["to_email"] = resolved_addr

        if (
            task.service == "sheets"
            and task.action in ("append_values", "get_values")
            and "range" in parameters
            and context.get("last_spreadsheet_tab")
        ):
            rng = str(parameters.get("range") or "")
            tab = context["last_spreadsheet_tab"]
            if rng.startswith("Sheet1!") or rng == "Sheet1":
                cell_part          = rng.split("!", 1)[1] if "!" in rng else "A1"
                parameters["range"] = f"'{tab}'!{cell_part}" if " " in tab else f"{tab}!{cell_part}"
                self.logger.info("Tab-fix: rewrote range '%s' → '%s'", rng, parameters["range"])
            elif "!" not in rng:
                parameters["range"] = f"'{tab}'!{rng}" if " " in tab else f"{tab}!{rng}"

        if task.service == "docs" and task.action == "batch_update":
            for text_key in ("text", "content"):
                raw = parameters.get(text_key)
                if isinstance(raw, str) and not raw.strip():
                    fallback = _gmail_messages_body_text(context)
                    if fallback and fallback != "No Gmail message body available.":
                        self.logger.warning(
                            "Bug2 safety-net: '%s' was empty for docs.batch_update — "
                            "filling from gmail_messages context.", text_key
                        )
                        parameters[text_key] = fallback

        return PlannedTask(
            id=task.id,
            service=task.service,
            action=task.action,
            parameters=parameters,
            reason=task.reason,
        )

    # ------------------------------------------------------------------
    # Context updater
    # ------------------------------------------------------------------

    def _update_context(self, task: PlannedTask, stdout: str, context: dict[str, Any]) -> None:
        payload      = _parse_json(stdout)
        user_keywords = extract_keywords(str(context.get("request_text") or ""))

        if payload and task.id:
            results = context.setdefault("task_results", {})
            results[task.id] = payload
            if task.id.startswith("task-"):
                try:
                    num = task.id.removeprefix("task-")
                    results[num] = payload
                    results[f"t{num}"] = payload
                except Exception:
                    pass

        if task.service == "gmail" and task.action == "list_messages":
            context["gmail_query"]       = task.parameters.get("q") or ""
            context["gmail_payload"]     = payload or {}
            context["gmail_message_ids"] = _gmail_message_ids(context)
        if task.service == "gmail" and task.action == "get_message" and payload:
            context.setdefault("gmail_messages", []).append(payload)
            all_msgs = context.get("gmail_messages", [])
            if len(all_msgs) > 1:
                context["gmail_messages"] = filter_gmail_messages(all_msgs, user_keywords)
        if task.service == "sheets" and task.action == "create_spreadsheet" and payload:
            context["last_spreadsheet_id"]  = payload.get("spreadsheetId") or ""
            context["last_spreadsheet_url"] = payload.get("spreadsheetUrl") or ""
            sheets_list = payload.get("sheets")
            if isinstance(sheets_list, list) and sheets_list:
                first_sheet = sheets_list[0]
                if isinstance(first_sheet, dict):
                    props = first_sheet.get("properties") or {}
                    context["last_spreadsheet_tab"] = props.get("title") or ""
            if not context.get("last_spreadsheet_tab"):
                title = (payload.get("properties") or {}).get("title") or ""
                context["last_spreadsheet_tab"] = title
        if task.service == "docs" and task.action == "create_document" and payload:
            doc_id = payload.get("documentId") or ""
            context["last_document_id"] = doc_id
            if doc_id:
                context["last_document_url"] = _GOOGLE_DOCS_URL_TEMPLATE.format(doc_id=doc_id)
        if task.service == "docs" and task.action == "get_document" and payload:
            doc_id = payload.get("documentId") or ""
            if doc_id and not context.get("last_document_id"):
                context["last_document_id"] = doc_id
            body         = payload.get("body") or {}
            content_list = body.get("content") or []
            text_chunks: list[str] = []
            for element in content_list:
                if not isinstance(element, dict):
                    continue
                para = element.get("paragraph") or {}
                for el in (para.get("elements") or []):
                    tr    = el.get("textRun") or {}
                    chunk = tr.get("content") or ""
                    if chunk:
                        text_chunks.append(chunk)
            context["last_document_content"] = "".join(text_chunks).strip()
            self.logger.info(
                "docs.get_document: stored %d chars in last_document_content",
                len(context["last_document_content"]),
            )
        if task.service == "drive" and task.action == "list_files" and payload:
            files = payload.get("files") if isinstance(payload, dict) else []
            if isinstance(files, list):
                filtered     = filter_drive_files(files, user_keywords)
                payload["files"] = filtered
            context["drive_query"]   = task.parameters.get("q") or ""
            context["drive_payload"] = payload
            results = context.setdefault("task_results", {})
            results[task.id] = payload
            if task.id.startswith("task-"):
                try:
                    results[task.id.removeprefix("task-")] = payload
                except Exception:
                    pass
        if task.service == "drive" and task.action == "export_file" and payload:
            saved_file = payload.get("saved_file")
            if not saved_file:
                self.logger.warning("drive.export_file: API response missing 'saved_file'; artifact ingestion skipped.")
                return
            try:
                import pathlib
                content = pathlib.Path(saved_file).read_text(encoding="utf-8", errors="ignore")
            except Exception:
                content = ""
            context["drive_export_content"] = content
            context["drive_export_file"]    = saved_file
            self.logger.info(
                "drive.export_file: stored %d chars from '%s' in drive_export_content",
                len(content), saved_file,
            )
        if task.service == "sheets" and task.action == "get_values" and payload:
            context["sheet_values_payload"] = payload

    # ------------------------------------------------------------------
    # Summary helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _drive_summary_values(context: dict[str, Any]) -> list[list[str]]:
        query   = str(context.get("drive_query") or "Drive search")
        payload = context.get("drive_payload") or {}
        files   = payload.get("files") if isinstance(payload, dict) else []
        if not isinstance(files, list) or not files:
            return [["Search", "File Name", "File Type", "Link"], [query, "No files found", "", ""]]
        rows = [["Search", "File Name", "File Type", "Link"]]
        for item in files[:_MAX_DRIVE_SUMMARY_FILES]:
            if isinstance(item, dict):
                rows.append([
                    query,
                    str(item.get("name") or ""),
                    str(item.get("mimeType") or "").split("/")[-1],
                    str(item.get("webViewLink") or ""),
                ])
        return rows

    @staticmethod
    def _gmail_summary_values(context: dict[str, Any]) -> list[list[str]]:
        query          = str(context.get("gmail_query") or "Gmail search")
        wants_company  = "company" in str(context.get("request_text") or "").lower()
        fetched_messages = context.get("gmail_messages")
        if isinstance(fetched_messages, list) and fetched_messages:
            if wants_company:
                rows: list[list[str]] = [["Search", "Company Name", "Subject", "From", "Message ID"]]
                seen: set[str] = set()
                for message in fetched_messages[:_MAX_GMAIL_SUMMARY_MESSAGES_VERBOSE]:
                    if not isinstance(message, dict):
                        continue
                    headers   = _gmail_headers(message)
                    subject   = headers.get("subject", "")
                    from_val  = headers.get("from", "")
                    body_text = _gmail_body_text(message)
                    companies = _extract_company_candidates(from_val, subject, body_text)
                    if not companies:
                        companies = [_company_from_sender(from_val)]
                    for company in companies:
                        key = company.lower()
                        if key in seen:
                            continue
                        seen.add(key)
                        rows.append([query, company, subject, from_val, str(message.get("id") or "")])
                if len(rows) == 1:
                    rows.append([query, "No company names detected", "", "", ""])
                return rows

            rows = [["Search", "Company", "From", "Subject", "Message ID"]]
            for message in fetched_messages[:_MAX_GMAIL_SUMMARY_MESSAGES]:
                if isinstance(message, dict):
                    headers  = _gmail_headers(message)
                    from_val = headers.get("from", "")
                    rows.append([
                        query,
                        _company_from_sender(from_val),
                        from_val,
                        headers.get("subject", ""),
                        str(message.get("id") or ""),
                    ])
            return rows

        rows = [["Search", "Message ID", "Thread ID"]]
        for message in _gmail_messages(context)[:_MAX_GMAIL_SUMMARY_MESSAGES]:
            rows.append([query, str(message.get("id") or ""), str(message.get("threadId") or "")])
        if len(rows) == 1:
            rows.append([query, "No messages returned", ""])
        return rows

    @staticmethod
    def _sheet_email_body(context: dict[str, Any]) -> str:
        code_stdout = str(context.get("last_code_stdout") or "").strip()
        if code_stdout:
            body_lines = ["Here are your computed results:", "", code_stdout]
            link = context.get("last_spreadsheet_url")
            if link:
                body_lines += ["", f"Full breakdown in spreadsheet: {link}"]
            return "\n".join(body_lines)

        payload = context.get("sheet_values_payload") or {}
        values  = payload.get("values") if isinstance(payload, dict) else None
        if not isinstance(values, list) or not values:
            return "No spreadsheet data was found."
        range_name = str(payload.get("range") or "spreadsheet range")
        lines = [f"Spreadsheet data from {range_name}:", ""]
        for row in values[:_MAX_SHEET_UI_ROWS]:
            if isinstance(row, list):
                lines.append(" | ".join(str(cell) for cell in row))
        return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Pass 0a — plain dot-ref sender field resolver
# ---------------------------------------------------------------------------

def _resolve_dot_sender_refs(
    params: Any, context: dict[str, Any], logger: logging.Logger,
) -> Any:
    if isinstance(params, dict):
        return {k: _resolve_dot_sender_refs(v, context, logger) for k, v in params.items()}
    if isinstance(params, list):
        return [_resolve_dot_sender_refs(item, context, logger) for item in params]
    if not isinstance(params, str):
        return params

    def _sub(m: re.Match) -> str:
        step_id_raw = m.group(1)
        field_raw   = m.group(2).lower()
        alias       = _SENDER_FIELD_ALIASES.get(field_raw)
        if alias is None:
            return m.group(0)
        header_key, extract_mode = alias
        messages: list[dict] = context.get("gmail_messages") or []
        if not messages:
            logger.warning("Pass0a: no gmail_messages for ref %s", m.group(0))
            return m.group(0)
        try:
            task_num_str = re.sub(r"^(task-|t-|t)", "", step_id_raw)
            step_num = int(task_num_str)
            msg_idx  = max(0, step_num - 2)
        except (ValueError, AttributeError):
            msg_idx = 0

        def _extract(msg: dict) -> str:
            if extract_mode == "body":
                return _gmail_body_text(msg) or str(msg.get("snippet") or "")
            if extract_mode in ("name", "email"):
                headers = _gmail_headers(msg)
                raw     = headers.get(header_key, "")
                if not raw:
                    return ""
                if extract_mode == "email":
                    addr_m = re.search(r"<([^>]+@[^>]+)>", raw)
                    return addr_m.group(1).strip() if addr_m else raw.strip()
                return raw.split("<", 1)[0].strip().strip('"')
            if header_key == "snippet":
                return str(msg.get("snippet") or "")
            return _gmail_headers(msg).get(header_key, "")

        if msg_idx < len(messages):
            value = _extract(messages[msg_idx])
            if value:
                logger.info("Pass0a: resolved %s → '%s' from message[%d]", m.group(0), value, msg_idx)
                return value
        seen_vals: list[str] = []
        seen_set:  set[str]  = set()
        for msg in messages:
            val = _extract(msg)
            if val and val not in seen_set:
                seen_set.add(val)
                seen_vals.append(val)
        if seen_vals:
            joined = ", ".join(seen_vals)
            logger.info("Pass0a: resolved %s → joined '%s'", m.group(0), joined[:80])
            return joined
        logger.warning("Pass0a: could not resolve %s", m.group(0))
        return m.group(0)

    return _DOT_SENDER_REF_RE.sub(_sub, params)


# ---------------------------------------------------------------------------
# Pass 0b — array-wildcard reference resolver
# ---------------------------------------------------------------------------

def _resolve_array_wildcard_refs(
    params: Any, context: dict[str, Any], logger: logging.Logger,
) -> Any:
    if isinstance(params, dict):
        return {k: _resolve_array_wildcard_from_key(k, v, context, logger) for k, v in params.items()}
    if isinstance(params, list):
        return [_resolve_array_wildcard_refs(item, context, logger) for item in params]
    if not isinstance(params, str):
        return params
    return _replace_wildcard_tokens(params, context, logger)


def _resolve_array_wildcard_from_key(
    key: str, value: Any, context: dict[str, Any], logger: logging.Logger,
) -> Any:
    if not isinstance(value, str):
        return _resolve_array_wildcard_refs(value, context, logger)
    matches = _ARRAY_WILDCARD_RE.findall(value)
    if not matches:
        return value
    stripped_value = value.strip()
    match = _ARRAY_WILDCARD_RE.search(value)
    if key in ("values", "rows") and match is not None and stripped_value == match.group(0):
        step_id, collection, field_name = matches[0]
        rows = _extract_wildcard_rows(step_id, collection, field_name, context, logger)
        if rows is not None:
            logger.info(
                "Bug3: resolved param '%s' wildcard {%s.%s[*].%s} → %d rows",
                key, step_id, collection, field_name, len(rows),
            )
            return rows
    return _replace_wildcard_tokens(value, context, logger)


def _replace_wildcard_tokens(value: str, context: dict[str, Any], logger: logging.Logger) -> str:
    def _sub(m: re.Match) -> str:
        step_id, collection, field_name = m.group(1), m.group(2), m.group(3)
        rows = _extract_wildcard_rows(step_id, collection, field_name, context, logger)
        if rows:
            return ", ".join(str(cell) for row in rows for cell in row if cell)
        return m.group(0)
    return _ARRAY_WILDCARD_RE.sub(_sub, value)


def _extract_wildcard_rows(
    step_id: str, collection: str, field_name: str,
    context: dict[str, Any], logger: logging.Logger,
) -> list[list[str]] | None:
    messages = context.get("gmail_messages") or []
    if not messages:
        logger.warning("Bug3: no gmail_messages for wildcard %s.%s[*].%s", step_id, collection, field_name)
        return None
    field_lower = field_name.lower()
    _HEADER_ALIASES: dict[str, str] = {
        "sendername": "from", "sender_name": "from", "name": "from",
        "senderemail": "from", "sender_email": "from", "email": "from",
        "subject": "subject", "date": "date", "to": "to", "cc": "cc",
    }
    header_key = _HEADER_ALIASES.get(field_lower, field_lower)
    rows: list[list[str]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        headers = _gmail_headers(msg)
        raw     = headers.get(header_key, "") or str(msg.get(field_name) or msg.get(field_lower) or "")
        if not raw:
            continue
        if field_lower in ("senderemail", "sender_email", "email"):
            addr_m = re.search(r"<([^>]+@[^>]+)>", raw)
            raw    = addr_m.group(1).strip() if addr_m else raw.strip()
        elif field_lower in ("sendername", "sender_name", "name"):
            raw = raw.split("<", 1)[0].strip().strip('"')
        if raw:
            rows.append([raw])
    return rows if rows else None


# ---------------------------------------------------------------------------
# Pass 0c — 3-level header ref resolver
# ---------------------------------------------------------------------------

def _resolve_headers_dot_refs(
    params: Any, context: dict[str, Any], logger: logging.Logger,
) -> Any:
    if isinstance(params, dict):
        return {k: _resolve_headers_dot_refs(v, context, logger) for k, v in params.items()}
    if isinstance(params, list):
        return [_resolve_headers_dot_refs(item, context, logger) for item in params]
    if not isinstance(params, str):
        return params

    def _sub(m: re.Match) -> str:
        step_id_raw = m.group(1)
        field_raw   = m.group(2).lower()
        alias       = _HEADERS_FIELD_ALIASES.get(field_raw)
        if alias is None:
            return m.group(0)
        header_key, extract_mode = alias
        messages: list[dict] = context.get("gmail_messages") or []
        if not messages:
            logger.warning("Pass0c: no gmail_messages for ref %s", m.group(0))
            return m.group(0)
        try:
            task_num_str = re.sub(r"^(task-|t-|t)", "", step_id_raw)
            step_num = int(task_num_str)
            msg_idx  = max(0, step_num - 2)
        except (ValueError, AttributeError):
            msg_idx = 0

        def _extract(msg: dict) -> str:
            hdrs = _gmail_headers(msg)
            raw  = hdrs.get(header_key, "")
            if not raw:
                return ""
            if extract_mode == "name":
                return raw.split("<", 1)[0].strip().strip('"')
            if extract_mode == "email":
                addr_m = re.search(r"<([^>]+@[^>]+)>", raw)
                return addr_m.group(1).strip() if addr_m else raw.strip()
            return raw

        if msg_idx < len(messages):
            value = _extract(messages[msg_idx])
            if value:
                logger.info("Pass0c: resolved %s → '%s' from message[%d]", m.group(0), value, msg_idx)
                return value
        seen_vals: list[str] = []
        seen_set:  set[str]  = set()
        for msg in messages:
            val = _extract(msg)
            if val and val not in seen_set:
                seen_set.add(val)
                seen_vals.append(val)
        if seen_vals:
            joined = ", ".join(seen_vals)
            logger.info("Pass0c: resolved %s → joined '%s'", m.group(0), joined[:80])
            return joined
        logger.warning("Pass0c: could not resolve %s", m.group(0))
        return m.group(0)

    return _HEADERS_DOT_REF_RE.sub(_sub, params)


# ---------------------------------------------------------------------------
# Pass 1 — template resolver
# ---------------------------------------------------------------------------

def _resolve_template(value: Any, context: dict[str, Any], logger: logging.Logger | None = None) -> Any:
    if isinstance(value, dict):
        return {k: _resolve_template(v, context, logger) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_template(v, context, logger) for v in value]
    if not isinstance(value, str):
        return value

    normalised = re.sub(fr"\{{{_TASK_ID_PAT}\.([\w\.]+)\[\]\.([\w]+)\}}", r"{\1.\2[*].\3}", value)
    if normalised != value and logger:
        logger.info("Bug1 fix: normalised empty-bracket token in '%s'", value[:120])
    value = normalised

    def replacer(match: re.Match) -> str:
        task_id_raw = match.group(1)
        key_path    = match.group(2)
        results     = context.get("task_results", {})

        # Flexible lookup: normalize "task-5", "t5", "t-5" all to "5"
        task_num    = re.sub(r"^(task-|t-|t)", "", task_id_raw)
        current     = results.get(task_id_raw) or results.get(task_num) or results.get(f"task-{task_num}")
        
        if not isinstance(current, dict):
            return match.group(0)

        segments: list[tuple[str, str | None]] = []
        for raw_part in key_path.split("."):
            bracket_m = re.match(r"^([\w]+)\[([\d\*]+)\]$", raw_part)
            if bracket_m:
                segments.append((bracket_m.group(1), None))
                segments.append((bracket_m.group(2), "idx"))
            else:
                segments.append((raw_part, None))

        if segments and segments[0][0] == "output" and len(segments) > 1:
            segments = segments[1:]

        for seg_key, seg_type in segments:
            if seg_type == "idx":
                if not isinstance(current, list):
                    return match.group(0)
                if seg_key == "*":
                    current = current[0] if current else None
                    if current is None:
                        return match.group(0)
                else:
                    try:
                        idx     = int(seg_key)
                        current = current[idx] if 0 <= idx < len(current) else None
                        if current is None:
                            return match.group(0)
                    except (ValueError, TypeError):
                        return match.group(0)
            else:
                if not isinstance(current, dict):
                    return match.group(0)
                norm  = seg_key.lower().replace("_", "")
                found = None
                for k, v in current.items():
                    if k.lower().replace("_", "") == norm:
                        found = v
                        break
                if found is None:
                    if norm in ("id", "spreadsheetid") and "spreadsheetId" in current:
                        found = current["spreadsheetId"]
                    elif norm in ("id", "documentid") and "documentId" in current:
                        found = current["documentId"]
                    elif norm in ("id", "fileid") and isinstance(current.get("files"), list) and current["files"]:
                        found = current["files"][0].get("id")
                    elif norm in ("id", "messageid") and isinstance(current.get("messages"), list) and current["messages"]:
                        found = current["messages"][0].get("id")
                if found is None:
                    return match.group(0)
                current = found

        if logger and current is not None:
            logger.info("Pass1: resolved %s → '%s'", match.group(0), str(current)[:80])
        return str(current) if current is not None else match.group(0)

    resolved = re.sub(fr"\{{{{{_TASK_ID_PAT}\.([\w\.\[\]\*]+)\}}}}", replacer, value)
    resolved = re.sub(fr"\{{{_TASK_ID_PAT}\.([\w\.\[\]\*]+)\}}", replacer, resolved)
    return resolved


# ---------------------------------------------------------------------------
# Pass 5 — gmail body variant normaliser
# ---------------------------------------------------------------------------

def _resolve_gmail_body_variants(
    params: Any, context: dict[str, Any], logger: logging.Logger,
) -> Any:
    if isinstance(params, dict):
        return {k: _resolve_gmail_body_variants(v, context, logger) for k, v in params.items()}
    if isinstance(params, list):
        return [_resolve_gmail_body_variants(item, context, logger) for item in params]
    if not isinstance(params, str):
        return params
    stripped = params.strip()
    if stripped in _GMAIL_BODY_VARIANTS and stripped != "$gmail_message_body":
        logger.info("Bug2: normalised gmail-body variant '%s' → '$gmail_message_body'", stripped)
        return "$gmail_message_body"
    return params


# ---------------------------------------------------------------------------
# Pass 6 — Drive file field resolver
# ---------------------------------------------------------------------------

def _resolve_drive_file_refs(
    params: Any, context: dict[str, Any], logger: logging.Logger,
) -> Any:
    if isinstance(params, dict):
        return {k: _resolve_drive_file_refs(v, context, logger) for k, v in params.items()}
    if isinstance(params, list):
        return [_resolve_drive_file_refs(item, context, logger) for item in params]
    if not isinstance(params, str):
        return params

    drive_payload = context.get("drive_payload") or {}
    files: list[dict] = drive_payload.get("files") if isinstance(drive_payload, dict) else []
    if not isinstance(files, list) or not files:
        return params

    def _sub(m: re.Match) -> str:
        try:
            idx = int(m.group(1))
        except (ValueError, TypeError):
            return m.group(0)
        field     = m.group(2)
        if idx < 0 or idx >= len(files):
            logger.warning("Pass6: files[%d] out of range (have %d files)", idx, len(files))
            return m.group(0)
        file_obj   = files[idx]
        if not isinstance(file_obj, dict):
            return m.group(0)
        field_lower = field.lower().replace("_", "")
        value       = None
        for k, v in file_obj.items():
            if k.lower().replace("_", "") == field_lower:
                value = v
                break
        if value is None:
            logger.warning("Pass6: field '%s' not found in files[%d]", field, idx)
            return m.group(0)
        logger.info("Pass6: resolved %s → '%s'", m.group(0), str(value)[:120])
        return str(value)

    return _DRIVE_FILE_REF_RE.sub(_sub, params)


# ---------------------------------------------------------------------------
# Code output placeholder resolution
# ---------------------------------------------------------------------------

_PLACEHOLDER_TOKEN_RE = re.compile(r"^PLACEHOLDER_[A-Z_]+$")
_ANGLE_BRACKET_RE     = re.compile(r"^[<\[\{][a-z_\s]+[>\]\}]$")


def _ingest_code_stdout_into_context(stdout: str, context: dict[str, Any]) -> None:
    code_values: dict[str, str] = context.setdefault("code_values", {})
    line_re = re.compile(
        r"(?P<label>[A-Za-z][\w\s/]+?)\s*[:=]\s*[$\u20b9\u20ac\u00a3]?\s*(?P<value>[\d,]+(?:\.\d+)?)",
        re.IGNORECASE,
    )
    for line in stdout.splitlines():
        m = line_re.search(line)
        if not m:
            continue
        label = m.group("label").strip().lower()
        value = m.group("value").replace(",", "")
        code_values[label] = value
        if "usd" in label or "dollar" in label:
            code_values["usd"] = value; code_values["total_usd"] = value
        if "inr" in label or "rupee" in label or "indian" in label:
            code_values["inr"] = value; code_values["total_inr"] = value
        if "total" in label:
            code_values["total"] = value


def _resolve_code_output_params(
    params: Any, context: dict[str, Any], logger: logging.Logger,
) -> Any:
    if isinstance(params, dict):
        return {k: _resolve_code_output_params(v, context, logger) for k, v in params.items()}
    if isinstance(params, list):
        return [_resolve_code_output_params(item, context, logger) for item in params]
    if not isinstance(params, str):
        return params
    stripped = params.strip()
    if _PLACEHOLDER_TOKEN_RE.match(stripped):
        return _pick_code_value(stripped, context, logger)
    if _ANGLE_BRACKET_RE.match(stripped):
        return _pick_code_value(stripped, context, logger)
    if stripped == "$last_code_stdout":
        return context.get("last_code_stdout") or ""
    if stripped == "$last_code_result":
        return context.get("last_code_result") or ""
    return params


def _pick_code_value(token: str, context: dict[str, Any], logger: logging.Logger) -> str:
    code_values: dict[str, str] = context.get("code_values") or {}
    token_lower = token.lower().replace("placeholder_", "").replace("_", " ").strip()
    for key, val in code_values.items():
        if key == token_lower or token_lower in key or key in token_lower:
            logger.info("BugA: resolved '%s' -> '%s' via code_values['%s']", token, val, key)
            return val
    fallback = context.get("last_code_result") or context.get("last_code_stdout") or ""
    if fallback:
        logger.info("BugA: resolved '%s' -> last_code_result fallback", token)
        return fallback
    logger.warning("BugA: could not resolve token '%s' — no code output in context", token)
    return token


# ---------------------------------------------------------------------------
# Bare step-ID param resolution
# ---------------------------------------------------------------------------

_BARE_STEP_REF_RE = re.compile(fr"^{_TASK_ID_PAT}\.([\w\.]+)$")


def _resolve_bare_step_id_params(params: Any, context: dict[str, Any]) -> Any:
    if isinstance(params, dict):
        return {k: _resolve_bare_step_id_params(v, context) for k, v in params.items()}
    if isinstance(params, list):
        return [_resolve_bare_step_id_params(item, context) for item in params]
    if not isinstance(params, str):
        return params
    m = _BARE_STEP_REF_RE.match(params.strip())
    if not m:
        return params
    step_id_raw = m.group(1)
    key_path    = m.group(2)
    results     = context.get("task_results", {})
    
    # Flexible lookup: normalize "task-5", "t5", "t-5" all to "5"
    task_num    = re.sub(r"^(task-|t-|t)", "", step_id_raw)
    payload     = results.get(step_id_raw) or results.get(task_num) or results.get(f"task-{task_num}")

    if not isinstance(payload, dict):
        return params
    current: Any = payload
    for part in key_path.split("."):
        if not isinstance(current, dict):
            return params
        norm    = part.lower().replace("_", "")
        matched = None
        for k, v in current.items():
            if k.lower().replace("_", "") == norm:
                matched = v
                break
        if matched is None:
            if norm in ("id", "spreadsheetid") and "spreadsheetId" in current:
                matched = current["spreadsheetId"]
            elif norm in ("id", "documentid") and "documentId" in current:
                matched = current["documentId"]
            else:
                return params
        current = matched
    return str(current) if current is not None else params


# ---------------------------------------------------------------------------
# Web-search extraction
# ---------------------------------------------------------------------------

_EXTRACTION_KEYWORDS = (
    "extract", "parse", "get rate", "put as", "from search result",
    "from result", "currency rate", "exchange rate",
)


def _looks_like_extraction_instruction(value: str) -> bool:
    lowered = value.lower().strip()
    return any(kw in lowered for kw in _EXTRACTION_KEYWORDS)


def _extract_numeric_from_web_search(context: dict[str, Any]) -> str | None:
    results   = context.get("web_search_results") or []
    rate_min  = float(context.get("exchange_rate_min") or 0.0001)
    rate_max  = float(context.get("exchange_rate_max") or 1e9)
    expected_pair = str(context.get("expected_currency_pair") or "").upper()
    float_re  = re.compile(r"\b(\d{1,10}\.\d{2,10})\b")
    best_value: str | None = None
    best_score: int        = -1
    for item in results:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or item.get("snippet") or "")
        for match in float_re.finditer(content):
            candidate = float(match.group(1))
            if not (rate_min < candidate < rate_max):
                continue
            start  = max(0, match.start() - 60)
            end    = min(len(content), match.end() + 60)
            window = content[start:end]
            score  = len(_CURRENCY_SIGNAL_RE.findall(window))
            if expected_pair and expected_pair in window.upper():
                score += 10
            if score > best_score:
                best_score = score
                best_value = str(round(candidate, 6))
    return best_value


def _resolve_search_extraction_params(
    params: Any, context: dict[str, Any], logger: logging.Logger,
) -> Any:
    if isinstance(params, dict):
        return {k: _resolve_search_extraction_params(v, context, logger) for k, v in params.items()}
    if isinstance(params, list):
        return [_resolve_search_extraction_params(item, context, logger) for item in params]
    if not isinstance(params, str):
        return params
    if not _looks_like_extraction_instruction(params):
        return params
    extracted = _extract_numeric_from_web_search(context)
    if extracted is not None:
        logger.info("BugFix2: replaced extraction instruction '%s' with '%s'", params[:80], extracted)
        return extracted
    logger.warning("BugFix2: could not extract value for instruction '%s'", params[:80])
    return params


# ---------------------------------------------------------------------------
# Nested $ resolver
# ---------------------------------------------------------------------------

def _resolve_nested_dollar(value: Any, context: dict[str, Any], executor: "PlanExecutor") -> Any:
    if isinstance(value, dict):
        return {k: _resolve_nested_dollar(v, context, executor) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_nested_dollar(item, context, executor) for item in value]
    if not isinstance(value, str):
        return value
    known_resolvers: dict[str, Any] = {
        "$last_spreadsheet_id":  context.get("last_spreadsheet_id") or "",
        "$last_document_id":     context.get("last_document_id") or "",
        "$last_code_stdout":     context.get("last_code_stdout") or "",
        "$last_code_result":     context.get("last_code_result") or "",
        "$user_email":           context.get("user_email") or context.get("explicit_to_email") or "",
        "$gmail_summary_values": executor._gmail_summary_values(context),
        "$sheet_email_body":     executor._sheet_email_body(context),
        "$drive_summary_values": executor._drive_summary_values(context),
        "$web_search_markdown":  _web_search_markdown(context),
        "$web_search_table_values": _web_search_table_values(context),
        "$gmail_message_body":   _gmail_messages_body_text(context),
        "$drive_export_file":    context.get("drive_export_content") or context.get("drive_export_file") or "",
    }
    if value in known_resolvers:
        return known_resolvers[value]
    return value


# ---------------------------------------------------------------------------
# Web-search context helpers
# ---------------------------------------------------------------------------

def _web_search_markdown(context: dict[str, Any]) -> str:
    results = context.get("web_search_results") or []
    if not results:
        return "No web search results available."
    lines: list[str] = []
    for item in results:
        if isinstance(item, dict):
            title   = item.get("title") or "Result"
            content = item.get("content") or ""
            link    = item.get("link") or item.get("url") or ""
            lines.append(f"## {title}\n{content}")
            if link:
                lines.append(f"Source: {link}")
            lines.append("")
    return "\n".join(lines).strip()


def _web_search_table_values(context: dict[str, Any]) -> list[list[str]]:
    results = context.get("web_search_results") or []
    rows: list[list[str]] = [["Title", "Content", "Link"]]
    for item in results:
        if isinstance(item, dict):
            rows.append([
                str(item.get("title") or ""),
                str(item.get("content") or ""),
                str(item.get("link") or item.get("url") or ""),
            ])
    if len(rows) == 1:
        rows.append(["No results", "", ""])
    return rows


def _gmail_messages_body_text(context: dict[str, Any]) -> str:
    full_messages = context.get("gmail_messages")
    if isinstance(full_messages, list) and full_messages:
        parts: list[str] = []
        for msg in full_messages[:5]:
            if isinstance(msg, dict):
                text = _gmail_body_text(msg) or str(msg.get("snippet") or "")
                if text:
                    parts.append(text)
        if parts:
            return "\n\n".join(parts)
    stub_messages = _gmail_messages(context)
    if stub_messages:
        id_lines  = [str(m.get("id") or m.get("threadId") or "") for m in stub_messages if m]
        non_empty = [line for line in id_lines if line]
        if non_empty:
            return "\n".join(non_empty)
    return "No Gmail message body available."


# ---------------------------------------------------------------------------
# Template / placeholder utilities
# ---------------------------------------------------------------------------

def _resolve_to_email_from_context(context: dict[str, Any]) -> str:
    for message in (context.get("gmail_messages") or []):
        if not isinstance(message, dict):
            continue
        headers  = _gmail_headers(message)
        from_val = headers.get("from", "")
        addr_m   = re.search(r"<([^>]+@[^>]+)>", from_val)
        addr     = addr_m.group(1).strip() if addr_m else from_val.strip()
        if "@" not in addr:
            continue
        if _RECEIPT_SENDER_PATTERNS.search(addr):
            continue
        return addr
    return ""


def _parse_json(stdout: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(stdout or "{}")
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _gmail_messages(context: dict[str, Any]) -> list[dict[str, Any]]:
    payload  = context.get("gmail_payload") or {}
    messages = payload.get("messages") if isinstance(payload, dict) else []
    if not isinstance(messages, list):
        return []
    return [m for m in messages if isinstance(m, dict)]


def _gmail_message_ids(context: dict[str, Any]) -> list[str]:
    return [str(m.get("id")) for m in _gmail_messages(context) if m.get("id")]


def _gmail_headers(message: dict[str, Any]) -> dict[str, str]:
    payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
    headers = payload.get("headers") if isinstance(payload.get("headers"), list) else []
    parsed: dict[str, str] = {}
    for header in headers:
        if isinstance(header, dict):
            name  = str(header.get("name") or "").lower()
            value = str(header.get("value") or "")
            if name:
                parsed[name] = value
    return parsed


def _company_from_sender(value: str) -> str:
    display = value.split("<", 1)[0].strip().strip('"')
    if display:
        return display
    address = value.strip().strip("<>")
    domain  = address.split("@", 1)[1] if "@" in address else address
    domain  = domain.split(">", 1)[0].split(".", 1)[0]
    return domain.replace("-", " ").replace("_", " ").title()


def _extract_company_candidates(from_value: str, subject: str, body_text: str) -> list[str]:
    candidates: list[str] = []
    sender_company = _company_from_sender(from_value)
    if sender_company and sender_company.lower() not in {"gmail", "googlemail"}:
        candidates.append(sender_company)
    patterns = (
        r"(?:offer|position|role)\s+(?:from|at)\s+([A-Z][A-Za-z0-9&.,' -]{1,60})",
        r"company\s*[:\-]\s*([A-Z][A-Za-z0-9&.,' -]{1,60})",
        r"\bat\s+([A-Z][A-Za-z0-9&.,' -]{1,60})",
    )
    sample_text = f"{subject}\n{body_text}"
    for pattern in patterns:
        for match in re.findall(pattern, sample_text):
            cleaned = str(match).strip(" .,:;")
            if cleaned and len(cleaned) > 1:
                candidates.append(cleaned)
    unique: list[str] = []
    seen:   set[str]  = set()
    for candidate in candidates:
        key = candidate.lower()
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _gmail_body_text(message: dict[str, Any]) -> str:
    snippet = str(message.get("snippet") or "")
    payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
    body_chunks: list[str] = []
    _collect_payload_text(payload, body_chunks)
    raw_body = "\n".join(chunk for chunk in body_chunks if chunk).strip()
    return raw_body or snippet


def _collect_payload_text(payload: dict[str, Any], chunks: list[str]) -> None:
    if not isinstance(payload, dict):
        return
    body = payload.get("body") if isinstance(payload.get("body"), dict) else {}
    data = body.get("data")
    if isinstance(data, str) and data:
        decoded = _decode_base64_urlsafe(data)
        if decoded:
            chunks.append(decoded)
    parts = payload.get("parts")
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, dict):
                _collect_payload_text(part, chunks)


def _decode_base64_urlsafe(value: str) -> str:
    try:
        padded  = value + "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        return decoded.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _is_likely_real_content(value: str) -> bool:
    return len(value) > 120 or "\n" in value


def _is_placeholder(value: str) -> bool:
    stripped = value.strip()
    if _is_likely_real_content(stripped):
        return False
    return (
        stripped.startswith("$")
        or "{{" in stripped
        or "}}" in stripped
        or "_from_task_" in stripped
        or "from_task_" in stripped
        or bool(re.search(r"\{(\d+|task-\d+)\.[\w\.\[\]\*]+\}", stripped))
        or bool(re.search(r"(\d+|task-\d+)\.[\w\.]+", stripped))
    )


def _is_gmail_values_placeholder(value: str) -> bool:
    lowered = value.lower()
    return _is_placeholder(lowered) and any(term in lowered for term in ("gmail", "company", "message", "email"))


def _is_sheet_body_placeholder(value: str) -> bool:
    lowered = value.lower()
    return _is_placeholder(lowered) and any(term in lowered for term in ("sheet", "spreadsheet", "table", "data"))


def _find_unresolved_placeholder(value: Any) -> str | None:
    if isinstance(value, str) and _is_placeholder(value):
        return value
    if isinstance(value, dict):
        for child in value.values():
            placeholder = _find_unresolved_placeholder(child)
            if placeholder:
                return placeholder
    if isinstance(value, list):
        for child in value:
            placeholder = _find_unresolved_placeholder(child)
            if placeholder:
                return placeholder
    return None
