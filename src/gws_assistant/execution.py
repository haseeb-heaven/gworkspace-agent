"""Plan execution service for ordered Google Workspace tasks."""

from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any

from .exceptions import ValidationError
from .gws_runner import GWSRunner
from .models import ExecutionResult, PlanExecutionReport, PlannedTask, RequestPlan, TaskExecution
from .planner import CommandPlanner
from .relevance import extract_keywords, filter_drive_files, filter_gmail_messages

# Import web_search_tool at module level so tests can patch gws_assistant.execution.web_search_tool
try:
    from .tools.web_search import web_search_tool
except Exception:  # pragma: no cover
    web_search_tool = None  # type: ignore[assignment]

# Sender-address patterns that belong to automated receipt / invoice mailers.
# We must NEVER use these as the reply-to / forward-to address.
_RECEIPT_SENDER_PATTERNS = re.compile(
    r"(noreply|no-reply|invoice|receipt|statements|do-not-reply|donotreply"
    r"|notifications?|billing|payments?|stripe\.com|paypal\.com|x\.com|twitter\.com)",
    re.IGNORECASE,
)


class PlanExecutor:
    """Executes planned gws tasks sequentially and carries context forward."""

    def __init__(self, planner: CommandPlanner, runner: GWSRunner, logger: logging.Logger, config=None) -> None:
        self.planner = planner
        self.runner = runner
        self.logger = logger
        self.config = config

    def execute(self, plan: RequestPlan) -> PlanExecutionReport:
        context: dict[str, Any] = {"request_text": plan.raw_text}

        # ------------------------------------------------------------------ #
        # Extract any explicit to_email embedded in the plan by the planner.  #
        # langchain_agent.py BugFix3 stores it as '__explicit_to_email__' in  #
        # the reason field of the injected send_message task, or directly in  #
        # context via the plan metadata.
        # ------------------------------------------------------------------ #
        for task in plan.tasks:
            if task.service == "gmail" and task.action == "send_message":
                addr = str(task.parameters.get("to_email") or "").strip()
                if addr and "@" in addr and not _RECEIPT_SENDER_PATTERNS.search(addr):
                    context["explicit_to_email"] = addr
                    break

        executions: list[TaskExecution] = []
        thought_trace: list[dict] = []
        task_list = list(plan.tasks)
        current_index = 0

        while current_index < len(task_list):
            task = task_list[current_index]
            for expanded_task in self._expand_task(task, context):
                # THOUGHT
                thought = self._think(
                    goal=plan.raw_text,
                    context=context,
                    next_task=expanded_task
                )
                self.logger.info(f"Thought [step {current_index + 1}]: {thought}")

                # ACTION
                resolved_task = self._resolve_task(expanded_task, context)
                result = self.execute_single_task(resolved_task, context)
                executions.append(TaskExecution(task=resolved_task, result=result))

                # OBSERVATION
                context["last_observation"] = result.stdout
                thought_trace.append({
                    "step": current_index + 1,
                    "thought": thought,
                    "action": f"{resolved_task.service}.{resolved_task.action}",
                    "observation": (result.stdout or "")[:300],
                    "success": result.success,
                })

                # REFLECTION on failure
                if not result.success:
                    reflection = self._reflect_on_failure(resolved_task, result, context)
                    self.logger.warning("Reflection: %s", reflection)
                    context["last_reflection"] = reflection
                    self.logger.warning("Task failed id=%s; continuing to capture full execution trace.", resolved_task.id)

                # RE-PLAN if LLM signals it
                if self._should_replan(thought, result, context):
                    new_tasks = self._replan(plan.raw_text, context)
                    if new_tasks:
                        task_list[current_index + 1:] = new_tasks
                        self.logger.info(f"Re-planned: {len(new_tasks)} new tasks injected.")

            current_index += 1

        report = PlanExecutionReport(
            plan=plan,
            executions=executions,
            thought_trace=thought_trace,
        )

        # Save to memory
        from .memory import save_episode
        task_summaries = [
            {"service": e.task.service, "action": e.task.action, "success": e.result.success}
            for e in executions
        ]
        outcome = "success" if all(e.result.success for e in executions) else "partial_failure"
        save_episode(goal=plan.raw_text, tasks=task_summaries, outcome=outcome)

        return report

    def execute_single_task(self, task: PlannedTask, context: dict[str, Any]) -> ExecutionResult:
        """Executes a single fully-resolved task and updates the context."""
        # Handle virtual 'search' service
        if task.service == "search":
            return self._execute_web_search(task, context)

        # Handle virtual 'code' service (computation/interpreter)
        if task.service == "code" or task.service == "computation":
            return self._execute_code_task(task, context)

        placeholder = _find_unresolved_placeholder(task.parameters)
        if placeholder:
            return ExecutionResult(
                success=False,
                command=[],
                error=f"Plan contained an unresolved placeholder: {placeholder}",
            )

        try:
            args = self.planner.build_command(
                task.service,
                task.action,
                task.parameters,
            )
        except ValidationError as exc:
            self.logger.warning("Task id=%s build_command failed: %s", task.id, exc)
            return ExecutionResult(success=False, command=[], error=str(exc))

        if hasattr(self.runner, "run_with_retry"):
            result = self.runner.run_with_retry(args)
        else:
            result = self.runner.run(args)

        parsed_payload = _parse_json(result.stdout)
        result.output = {
            "command": result.command,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "parsed_payload": parsed_payload,
        }
        self._update_context(task, result.stdout, context)

        # Artifact Verification Step
        verification_error = self._verify_artifact_content(task, result, context)
        if verification_error:
            self.logger.warning("Verification failed for task %s: %s", task.id, verification_error)
            result.success = False
            result.error = f"Verification Failure: {verification_error}"

        return result

    def _verify_artifact_content(self, task: PlannedTask, result: ExecutionResult, context: dict[str, Any]) -> str | None:
        """Fetch the created/updated artifact and ensure it is not empty or filled with placeholders."""
        if not result.success:
            return None

        if task.service == "docs" and task.action == "create_document":
            doc_id = (result.output.get("parsed_payload") or {}).get("documentId")
            if not doc_id: return "No document ID found in output after creation."
            fetch_res = self.runner.run(["docs", "documents", "get", "--params", json.dumps({"documentId": doc_id})])
            if fetch_res.return_code != 0: return f"Failed to fetch document for verification: {fetch_res.stderr}"
            content = fetch_res.stdout
            if len(content.strip()) < 100: return "Newly created document is nearly empty."
            if "{{" in content or "placeholder" in content.lower(): return "Document contains unresolved placeholders."

        if task.service == "sheets" and (task.action == "append_values" or task.action == "create_spreadsheet"):
            sheet_id = context.get("last_spreadsheet_id") or (result.output.get("parsed_payload") or {}).get("spreadsheetId")
            if not sheet_id: return None
            if task.action == "append_values":
                range_val = task.parameters.get("range", "A1:C5")
                check_res = self.runner.run(["sheets", "spreadsheets", "values", "get", "--params", json.dumps({"spreadsheetId": sheet_id, "range": range_val})])
                if "{{" in check_res.stdout or "No data" in check_res.stdout:
                    return "Spreadsheet data contains placeholders or is missing."

        if task.service == "gmail" and task.action == "send_message":
            search_res = self.runner.run(["gmail", "users", "messages", "list", "--params", json.dumps({"userId": "me", "maxResults": 1, "q": "label:SENT"})])
            if search_res.return_code == 0:
                payload = _parse_json(search_res.stdout)
                msgs = payload.get("messages") if isinstance(payload, dict) else []
                if msgs:
                    msg_id = msgs[0]["id"]
                    get_res = self.runner.run(["gmail", "users", "messages", "get", "--params", json.dumps({"userId": "me", "id": msg_id})])
                    content = get_res.stdout
                    if "{{" in content or "{task" in content:
                        return "Sent email contains unresolved placeholders."

        return None

    def _think(self, goal: str, context: dict, next_task: PlannedTask) -> str:
        """ReACT: LLM reasons about whether next planned step is correct."""
        try:
            from .langchain_agent import create_agent
            agent = create_agent(self.config, self.logger)
            if not agent:
                return "No LLM configured — proceeding with planned task."
            prompt = (
                f"Goal: {goal}\n"
                f"Completed steps: {len(context.get('task_results', {}))}\n"
                f"Last observation: {str(context.get('last_observation', 'None'))[:300]}\n"
                f"Last reflection: {str(context.get('last_reflection', 'None'))[:200]}\n"
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
        replan_signals = ("should change", "instead", "wrong step", "incorrect", "skip", "replan")
        return any(signal in lower_thought for signal in replan_signals)

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

    def _reflect_on_failure(self, task: PlannedTask, result: ExecutionResult, context: dict) -> str:
        return (
            f"Task {task.id} ({task.service}.{task.action}) failed. "
            f"Error: {result.error or 'unknown'}. "
            f"Parameters used: {list(task.parameters.keys())}. "
            f"Suggestion: Check if required IDs are resolved in context."
        )

    def _execute_code_task(self, task: PlannedTask, context: dict[str, Any]) -> ExecutionResult:
        """Execute a code computation task and store the result."""
        from .tools.code_execution import execute_generated_code
        code = str(task.parameters.get("code") or "").strip()
        if not code:
            return ExecutionResult(success=False, command=[], error="Missing required parameter: code")

        structured = execute_generated_code(code, config=self.planner.config)
        output = structured.get("output") or {}

        stdout = output.get("stdout") or ""
        parsed_value = output.get("parsed_value")

        # ------------------------------------------------------------------ #
        # BUG A FIX: Expose code output via multiple context keys so that     #
        # downstream sheet append_values tasks can resolve PLACEHOLDER_AMOUNT  #
        # and similar tokens regardless of how the planner referenced them.   #
        # ------------------------------------------------------------------ #
        # 1. Store the full output dict under task_results for {{N.key}} refs
        results_map = context.setdefault("task_results", {})
        results_map[task.id] = output
        if task.id.startswith("task-"):
            results_map[task.id.removeprefix("task-")] = output

        # 2. Flat context keys for $-style and PLACEHOLDER_ resolution
        context["last_code_stdout"] = stdout.strip()
        context["last_code_result"] = str(parsed_value) if parsed_value is not None else stdout.strip()

        # 3. Parse structured lines like "Total USD: $8.00" / "Total INR: 665.50"
        _ingest_code_stdout_into_context(stdout, context)

        result = ExecutionResult(success=structured["success"], command=["code_execution"], stdout=stdout)
        result.output = {
            "command": result.command,
            "stdout": stdout,
            "stderr": output.get("stderr") or "",
            "parsed_payload": output,
            "parsed_value": parsed_value,
        }
        if not structured["success"]:
            result.error = structured.get("error")

        return result

    def _execute_web_search(self, task: PlannedTask, context: dict[str, Any]) -> ExecutionResult:
        """Execute a web search task using the web_search_tool and store results in context."""
        query = str(task.parameters.get("query") or "").strip()
        max_results = int(task.parameters.get("max_results") or 5)
        try:
            payload = web_search_tool.invoke({"query": query, "max_results": max_results})
        except Exception as exc:
            return ExecutionResult(success=False, command=[], error=str(exc))

        results = payload.get("results") or []
        error = payload.get("error")
        if error and not results:
            return ExecutionResult(success=False, command=[], error=error)

        context["web_search_query"] = query
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
            self.logger.info("Skipping gmail.get_message task id=%s because no message IDs were returned.", task.id)
            return []

        limit = 5
        return [
            PlannedTask(
                id=f"{task.id}-{index}",
                service=task.service,
                action=task.action,
                parameters={**task.parameters, "message_id": message_id},
                reason=task.reason,
            )
            for index, message_id in enumerate(message_ids[:limit], start=1)
        ]

    def _resolve_task(self, task: PlannedTask, context: dict[str, Any]) -> PlannedTask:
        parameters = _resolve_template(task.parameters, context)

        # BUG FIX 1 (from previous PR): bare step-ID references like '4.id'
        parameters = _resolve_bare_step_id_params(parameters, context)

        # BUG FIX 2 (from previous PR): natural-language extraction instructions
        if context.get("web_search_results"):
            parameters = _resolve_search_extraction_params(parameters, context, self.logger)

        # ------------------------------------------------------------------ #
        # BUG A FIX: Replace PLACEHOLDER_* tokens and common planner          #
        # placeholder strings with actual values from the code executor.      #
        # ------------------------------------------------------------------ #
        if context.get("last_code_stdout") or context.get("last_code_result"):
            parameters = _resolve_code_output_params(parameters, context, self.logger)

        # Resolve nested $ placeholders inside list/dict values
        parameters = _resolve_nested_dollar(parameters, context, self)

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

            # Inject spreadsheet/doc link into email body
            if key == "body" and isinstance(parameters[key], str):
                link = context.get("last_spreadsheet_url")
                if link and link not in parameters[key] and ("link" in parameters[key].lower() or "sheet" in parameters[key].lower()):
                    parameters[key] = f"{parameters[key]}\n\nLink to spreadsheet: {link}"
                doc_link = context.get("last_document_url")
                if doc_link and doc_link not in parameters[key]:
                    parameters[key] = f"{parameters[key]}\n\nLink to document: {doc_link}"

        # Automatic injection for missing but required IDs
        if "spreadsheet_id" not in parameters and context.get("last_spreadsheet_id"):
            parameters["spreadsheet_id"] = context["last_spreadsheet_id"]
        if "document_id" not in parameters and context.get("last_document_id"):
            parameters["document_id"] = context["last_document_id"]
        if "folder_id" not in parameters and context.get("last_folder_id"):
            parameters["folder_id"] = context["last_folder_id"]
        if "message_id" not in parameters and context.get("last_message_id"):
            parameters["message_id"] = context["last_message_id"]

        # ------------------------------------------------------------------ #
        # BUG C FIX: to_email resolution for gmail.send_message               #
        # Priority order:                                                      #
        #   1. explicit_to_email stored from the plan (user's stated address)  #
        #   2. Already-valid non-receipt address in parameters                 #
        #   3. Fallback: _resolve_to_email_from_context (skips receipt senders)#
        # ------------------------------------------------------------------ #
        if task.service == "gmail" and task.action == "send_message":
            to_email_val = str(parameters.get("to_email") or "").strip()
            explicit = str(context.get("explicit_to_email") or "").strip()

            # Use explicitly known destination first
            if explicit and "@" in explicit:
                parameters["to_email"] = explicit
            elif not to_email_val or _is_placeholder(to_email_val) or _RECEIPT_SENDER_PATTERNS.search(to_email_val):
                # Value is missing, a placeholder, or a receipt sender — resolve from context
                resolved_addr = _resolve_to_email_from_context(context)
                if resolved_addr:
                    self.logger.info("Auto-resolved to_email from context: %s", resolved_addr)
                    parameters["to_email"] = resolved_addr

        # ------------------------------------------------------------------ #
        # BUG B FIX: Range tab-name rewrite must NOT overwrite an explicit    #
        # tab name the planner already put in the range (e.g. 'INR!A1').      #
        # Only rewrite when the range uses a generic 'Sheet1' prefix.         #
        # ------------------------------------------------------------------ #
        if (task.service == "sheets" and task.action == "append_values"
                and "range" in parameters and context.get("last_spreadsheet_tab")):
            rng = str(parameters.get("range") or "")
            tab = context["last_spreadsheet_tab"]
            # Only auto-fix ranges that reference the generic default tab name
            if rng.startswith("Sheet1!") or rng == "Sheet1":
                cell_part = rng.split("!", 1)[1] if "!" in rng else "A1"
                parameters["range"] = f"'{tab}'!{cell_part}" if " " in tab else f"{tab}!{cell_part}"
            elif "!" not in rng:
                # Bare range like 'A1:D10' — prepend the known tab
                parameters["range"] = f"'{tab}'!{rng}" if " " in tab else f"{tab}!{rng}"
            # If the planner already gave us 'TabName!A1:D10', leave it alone.

        return PlannedTask(
            id=task.id,
            service=task.service,
            action=task.action,
            parameters=parameters,
            reason=task.reason,
        )

    def _update_context(self, task: PlannedTask, stdout: str, context: dict[str, Any]) -> None:
        payload = _parse_json(stdout)
        user_keywords = extract_keywords(str(context.get("request_text") or ""))

        if payload and task.id:
            results = context.setdefault("task_results", {})
            results[task.id] = payload
            if task.id.startswith("task-"):
                try:
                    num_id = task.id.removeprefix("task-")
                    results[num_id] = payload
                except Exception:
                    pass

        if task.service == "gmail" and task.action == "list_messages":
            context["gmail_query"] = task.parameters.get("q") or ""
            context["gmail_payload"] = payload or {}
            context["gmail_message_ids"] = _gmail_message_ids(context)
        if task.service == "gmail" and task.action == "get_message" and payload:
            context.setdefault("gmail_messages", []).append(payload)
            all_msgs = context.get("gmail_messages", [])
            if len(all_msgs) > 1:
                context["gmail_messages"] = filter_gmail_messages(all_msgs, user_keywords)
        if task.service == "sheets" and task.action == "create_spreadsheet" and payload:
            context["last_spreadsheet_id"] = payload.get("spreadsheetId") or ""
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
                context["last_document_url"] = f"https://docs.google.com/document/d/{doc_id}/edit"
        if task.service == "drive" and task.action == "list_files" and payload:
            files = payload.get("files") if isinstance(payload, dict) else []
            if isinstance(files, list):
                filtered = filter_drive_files(files, user_keywords)
                payload["files"] = filtered
            context["drive_query"] = task.parameters.get("q") or ""
            context["drive_payload"] = payload
        if task.service == "sheets" and task.action == "get_values" and payload:
            context["sheet_values_payload"] = payload

    @staticmethod
    def _drive_summary_values(context: dict[str, Any]) -> list[list[str]]:
        query = str(context.get("drive_query") or "Drive search")
        payload = context.get("drive_payload") or {}
        files = payload.get("files") if isinstance(payload, dict) else []
        if not isinstance(files, list) or not files:
            return [["Search", "File Name", "File Type", "Link"], [query, "No files found", "", ""]]
        rows = [["Search", "File Name", "File Type", "Link"]]
        for item in files[:50]:
            if isinstance(item, dict):
                rows.append([
                    query,
                    str(item.get("name") or ""),
                    str(item.get("mimeType") or "").split("/")[-1],
                    str(item.get("webViewLink") or "")
                ])
        return rows

    @staticmethod
    def _gmail_summary_values(context: dict[str, Any]) -> list[list[str]]:
        query = str(context.get("gmail_query") or "Gmail search")
        wants_company = "company" in str(context.get("request_text") or "").lower()
        fetched_messages = context.get("gmail_messages")
        if isinstance(fetched_messages, list) and fetched_messages:
            if wants_company:
                rows = [["Search", "Company Name", "Subject", "From", "Message ID"]]
                seen: set[str] = set()
                for message in fetched_messages[:100]:
                    if not isinstance(message, dict):
                        continue
                    headers = _gmail_headers(message)
                    subject = headers.get("subject", "")
                    from_value = headers.get("from", "")
                    body_text = _gmail_body_text(message)
                    companies = _extract_company_candidates(from_value, subject, body_text)
                    if not companies:
                        companies = [_company_from_sender(from_value)]
                    for company in companies:
                        key = company.lower()
                        if key in seen:
                            continue
                        seen.add(key)
                        rows.append([query, company, subject, from_value, str(message.get("id") or "")])
                if len(rows) == 1:
                    rows.append([query, "No company names detected", "", "", ""])
                return rows

            rows = [["Search", "Company", "From", "Subject", "Message ID"]]
            for message in fetched_messages[:50]:
                if isinstance(message, dict):
                    headers = _gmail_headers(message)
                    from_value = headers.get("from", "")
                    rows.append([
                        query,
                        _company_from_sender(from_value),
                        from_value,
                        headers.get("subject", ""),
                        str(message.get("id") or ""),
                    ])
            return rows

        rows = [["Search", "Message ID", "Thread ID"]]
        for message in _gmail_messages(context)[:50]:
            rows.append([query, str(message.get("id") or ""), str(message.get("threadId") or "")])
        if len(rows) == 1:
            rows.append([query, "No messages returned", ""])
        return rows

    @staticmethod
    def _sheet_email_body(context: dict[str, Any]) -> str:
        # Prefer code output for the email body when it contains computed results
        code_stdout = str(context.get("last_code_stdout") or "").strip()
        if code_stdout:
            body_lines = ["Here are your computed results:", "", code_stdout]
            link = context.get("last_spreadsheet_url")
            if link:
                body_lines += ["", f"Full breakdown in spreadsheet: {link}"]
            return "\n".join(body_lines)

        payload = context.get("sheet_values_payload") or {}
        values = payload.get("values") if isinstance(payload, dict) else None
        if not isinstance(values, list) or not values:
            return "No spreadsheet data was found."
        range_name = str(payload.get("range") or "spreadsheet range")
        lines = [f"Spreadsheet data from {range_name}:", ""]
        for row in values[:200]:
            if isinstance(row, list):
                rendered = " | ".join(str(cell) for cell in row)
                lines.append(rendered)
        return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# BUG A helpers — code output placeholder resolution
# ---------------------------------------------------------------------------

# Matches PLACEHOLDER_AMOUNT, PLACEHOLDER_USD, PLACEHOLDER_INR, etc.
_PLACEHOLDER_TOKEN_RE = re.compile(r"^PLACEHOLDER_[A-Z_]+$")

# Matches generic planner-inserted strings like '<total_usd>', '[inr_amount]'
_ANGLE_BRACKET_RE = re.compile(r"^[<\[\{][a-z_\s]+[>\]\}]$")


def _ingest_code_stdout_into_context(stdout: str, context: dict[str, Any]) -> None:
    """Parse structured output lines from code execution into context.

    Looks for patterns like:
      Total USD: $8.00
      Total INR: 665.50
      USD Total: 8.0
    and stores them as context['code_values']['usd'] etc.
    """
    code_values: dict[str, str] = context.setdefault("code_values", {})
    # Pattern: label: value
    line_re = re.compile(
        r"(?P<label>[A-Za-z][\w\s/]+?)\s*[:=]\s*[$₹€£]?\s*(?P<value>[\d,]+(?:\.\d+)?)",
        re.IGNORECASE,
    )
    for line in stdout.splitlines():
        m = line_re.search(line)
        if not m:
            continue
        label = m.group("label").strip().lower()
        value = m.group("value").replace(",", "")
        code_values[label] = value
        # Normalised shortcuts
        if "usd" in label or "dollar" in label:
            code_values["usd"] = value
            code_values["total_usd"] = value
        if "inr" in label or "rupee" in label or "indian" in label:
            code_values["inr"] = value
            code_values["total_inr"] = value
        if "total" in label:
            code_values["total"] = value


def _resolve_code_output_params(
    params: Any,
    context: dict[str, Any],
    logger: logging.Logger,
) -> Any:
    """Replace PLACEHOLDER_* tokens and other stub strings in params with real
    values from code execution output stored in context."""
    if isinstance(params, dict):
        return {k: _resolve_code_output_params(v, context, logger) for k, v in params.items()}
    if isinstance(params, list):
        return [_resolve_code_output_params(item, context, logger) for item in params]
    if not isinstance(params, str):
        return params

    stripped = params.strip()

    # Case 1: exact PLACEHOLDER_* token
    if _PLACEHOLDER_TOKEN_RE.match(stripped):
        return _pick_code_value(stripped, context, logger)

    # Case 2: angle/bracket placeholder like <total_usd>
    if _ANGLE_BRACKET_RE.match(stripped):
        return _pick_code_value(stripped, context, logger)

    # Case 3: $ placeholders referencing code context keys
    if stripped == "$last_code_stdout":
        return context.get("last_code_stdout") or ""
    if stripped == "$last_code_result":
        return context.get("last_code_result") or ""

    return params


def _pick_code_value(token: str, context: dict[str, Any], logger: logging.Logger) -> str:
    """Select the most appropriate scalar value from code_values or fallback to
    last_code_result / last_code_stdout."""
    code_values: dict[str, str] = context.get("code_values") or {}
    token_lower = token.lower().replace("placeholder_", "").replace("_", " ").strip()

    # Try direct match first
    for key, val in code_values.items():
        if key == token_lower or token_lower in key or key in token_lower:
            logger.info("BugA: resolved '%s' -> '%s' via code_values['%s']", token, val, key)
            return val

    # Fall back to the full code stdout (useful for body text)
    fallback = context.get("last_code_result") or context.get("last_code_stdout") or ""
    if fallback:
        logger.info("BugA: resolved '%s' -> last_code_result fallback", token)
        return fallback

    logger.warning("BugA: could not resolve token '%s' — no code output in context", token)
    return token  # leave unchanged; better than crashing


# ---------------------------------------------------------------------------
# BUG FIX 1 helpers — bare step-ID param resolution
# ---------------------------------------------------------------------------

_BARE_STEP_REF_RE = re.compile(r"^(\d+|task-\d+)\.([\w\.]+)$")


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

    step_id = m.group(1)
    key_path = m.group(2)
    results = context.get("task_results", {})
    payload = results.get(step_id)
    if not isinstance(payload, dict):
        return params

    current: Any = payload
    for part in key_path.split("."):
        if not isinstance(current, dict):
            return params
        norm = part.lower().replace("_", "")
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
# BUG FIX 2 helpers — web-search extraction instruction replacement
# ---------------------------------------------------------------------------

_EXTRACTION_KEYWORDS = (
    "extract", "parse", "get rate", "put as", "from search result",
    "from result", "currency rate", "exchange rate",
)


def _looks_like_extraction_instruction(value: str) -> bool:
    lowered = value.lower().strip()
    return any(kw in lowered for kw in _EXTRACTION_KEYWORDS)


def _extract_numeric_from_web_search(context: dict[str, Any]) -> str | None:
    results = context.get("web_search_results") or []
    float_re = re.compile(r"\b(\d{1,4}\.\d{2,6})\b")
    for item in results:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or item.get("snippet") or "")
        for match in float_re.finditer(content):
            candidate = float(match.group(1))
            if 1.0 < candidate < 200.0:
                return str(round(candidate, 4))
    return None


def _resolve_search_extraction_params(
    params: Any,
    context: dict[str, Any],
    logger: logging.Logger,
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
    logger.warning("BugFix2: could not extract value for '%s'", params[:80])
    return params


# ---------------------------------------------------------------------------
def _resolve_nested_dollar(value: Any, context: dict[str, Any], executor: "PlanExecutor") -> Any:
    if isinstance(value, dict):
        return {k: _resolve_nested_dollar(v, context, executor) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_nested_dollar(item, context, executor) for item in value]
    if not isinstance(value, str):
        return value
    known_resolvers: dict[str, Any] = {
        "$last_spreadsheet_id": context.get("last_spreadsheet_id") or "",
        "$last_document_id": context.get("last_document_id") or "",
        "$last_code_stdout": context.get("last_code_stdout") or "",
        "$last_code_result": context.get("last_code_result") or "",
        "$gmail_summary_values": executor._gmail_summary_values(context),
        "$sheet_email_body": executor._sheet_email_body(context),
        "$drive_summary_values": executor._drive_summary_values(context),
        "$web_search_markdown": _web_search_markdown(context),
        "$web_search_table_values": _web_search_table_values(context),
        "$gmail_message_body": _gmail_messages_body_text(context),
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
            title = item.get("title") or "Result"
            content = item.get("content") or ""
            link = item.get("link") or item.get("url") or ""
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
        id_lines = [str(m.get("id") or m.get("threadId") or "") for m in stub_messages if m]
        non_empty = [line for line in id_lines if line]
        if non_empty:
            return "\n".join(non_empty)

    return "No Gmail message body available."


# ---------------------------------------------------------------------------
# Template / placeholder utilities
# ---------------------------------------------------------------------------

def _resolve_template(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {k: _resolve_template(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_template(v, context) for v in value]
    if not isinstance(value, str):
        return value

    def replacer(match: re.Match) -> str:
        task_id = match.group(1)
        key_path = match.group(2)
        results = context.get("task_results", {})
        current = results.get(task_id)

        if not isinstance(current, dict):
            return match.group(0)

        parts = key_path.split(".")
        if parts[0] == "output" and len(parts) > 1:
            parts = parts[1:]

        for part in parts:
            if isinstance(current, dict):
                norm_part = part.lower().replace("_", "")
                found = False
                for k, v in current.items():
                    if k.lower().replace("_", "") == norm_part:
                        current = v
                        found = True
                        break

                if not found:
                    if norm_part in ("id", "fileid") and "files" in current and isinstance(current["files"], list) and current["files"]:
                        current = current["files"][0].get("id")
                        if current:
                            found = True
                    elif norm_part in ("id", "messageid") and "messages" in current and isinstance(current["messages"], list) and current["messages"]:
                        current = current["messages"][0].get("id")
                        if current:
                            found = True

                if not found:
                    return match.group(0)
            elif isinstance(current, list):
                try:
                    idx = int(part)
                    if 0 <= idx < len(current):
                        current = current[idx]
                    else:
                        return match.group(0)
                except ValueError:
                    return match.group(0)
            else:
                return match.group(0)

        return str(current)

    resolved = re.sub(r"\{\{([\w\-]+)\.([\w\.]+)\}\}", replacer, value)
    resolved = re.sub(r"\{(\d+|task-\d+)\.([\w\.]+)\}", replacer, resolved)
    return resolved


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _resolve_to_email_from_context(context: dict[str, Any]) -> str:
    """Extract a valid reply-to address from fetched gmail_messages.

    Skips receipt / no-reply sender addresses (Stripe, X, PayPal, etc.).
    Returns the first clean sender address found, or empty string.
    """
    fetched = context.get("gmail_messages") or []
    for message in fetched:
        if not isinstance(message, dict):
            continue
        headers = _gmail_headers(message)
        from_value = headers.get("from", "")
        addr_match = re.search(r"<([^>]+@[^>]+)>", from_value)
        addr = addr_match.group(1).strip() if addr_match else from_value.strip()
        if "@" not in addr:
            continue
        # Skip automated / receipt senders
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
    payload = context.get("gmail_payload") or {}
    messages = payload.get("messages") if isinstance(payload, dict) else []
    if not isinstance(messages, list):
        return []
    return [message for message in messages if isinstance(message, dict)]


def _gmail_message_ids(context: dict[str, Any]) -> list[str]:
    return [str(message.get("id")) for message in _gmail_messages(context) if message.get("id")]


def _gmail_headers(message: dict[str, Any]) -> dict[str, str]:
    payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
    headers = payload.get("headers") if isinstance(payload.get("headers"), list) else []
    parsed: dict[str, str] = {}
    for header in headers:
        if isinstance(header, dict):
            name = str(header.get("name") or "").lower()
            value = str(header.get("value") or "")
            if name:
                parsed[name] = value
    return parsed


def _company_from_sender(value: str) -> str:
    display = value.split("<", 1)[0].strip().strip('"')
    if display:
        return display
    address = value.strip().strip("<>")
    domain = address.split("@", 1)[1] if "@" in address else address
    domain = domain.split(">", 1)[0].split(".", 1)[0]
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
    seen: set[str] = set()
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
        padded = value + "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        return decoded.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _is_placeholder(value: str) -> bool:
    stripped = value.strip()
    return (
        stripped.startswith("$")
        or "{{" in stripped
        or "}}" in stripped
        or "_from_task_" in stripped
        or "from_task_" in stripped
        or bool(re.search(r"\{(\d+|task-\d+)\.[\w\.]+\}", stripped))
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
