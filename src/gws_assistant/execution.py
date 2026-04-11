"""Plan execution service for ordered Google Workspace tasks."""

from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any

from .gws_runner import GWSRunner
from .models import ExecutionResult, PlanExecutionReport, PlannedTask, RequestPlan, TaskExecution
from .planner import CommandPlanner
from .relevance import extract_keywords, filter_drive_files, filter_gmail_messages

# Import web_search_tool at module level so tests can patch gws_assistant.execution.web_search_tool
try:
    from .tools.web_search import web_search_tool
except Exception:  # pragma: no cover
    web_search_tool = None  # type: ignore[assignment]


class PlanExecutor:
    """Executes planned gws tasks sequentially and carries context forward."""

    def __init__(self, planner: CommandPlanner, runner: GWSRunner, logger: logging.Logger) -> None:
        self.planner = planner
        self.runner = runner
        self.logger = logger

    def execute(self, plan: RequestPlan) -> PlanExecutionReport:
        context: dict[str, Any] = {"request_text": plan.raw_text}
        executions: list[TaskExecution] = []
        for task in plan.tasks:
            for expanded_task in self._expand_task(task, context):
                self.logger.info(
                    "Executing planned task id=%s service=%s action=%s reason=%s",
                    expanded_task.id,
                    expanded_task.service,
                    expanded_task.action,
                    expanded_task.reason,
                )
                resolved_task = self._resolve_task(expanded_task, context)
                result = self.execute_single_task(resolved_task, context)
                executions.append(TaskExecution(task=resolved_task, result=result))
                if not result.success:
                    self.logger.warning("Task failed id=%s; continuing to capture full execution trace.", resolved_task.id)
        return PlanExecutionReport(plan=plan, executions=executions)

    def execute_single_task(self, task: PlannedTask, context: dict[str, Any]) -> ExecutionResult:
        """Executes a single fully-resolved task and updates the context."""
        # Handle virtual 'search' service — calls web_search_tool directly, no gws binary needed.
        if task.service == "search":
            return self._execute_web_search(task, context)

        placeholder = _find_unresolved_placeholder(task.parameters)
        if placeholder:
            return ExecutionResult(
                success=False,
                command=[],
                error=f"Plan contained an unresolved placeholder: {placeholder}",
            )

        args = self.planner.build_command(
            task.service,
            task.action,
            task.parameters,
        )
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

        # Store under task_results for {{task_id.key}} resolution
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

        # Resolve nested $ placeholders inside list/dict values (e.g. [["$gmail_message_body"]])
        parameters = _resolve_nested_dollar(parameters, context, self)

        # Legacy $ resolution for backward compatibility
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

        # Fix range to use correct tab name when using a just-created spreadsheet
        if (task.service == "sheets" and task.action == "append_values"
                and "range" in parameters and context.get("last_spreadsheet_tab")):
            rng = str(parameters.get("range") or "")
            tab = context["last_spreadsheet_tab"]
            if rng.startswith("Sheet1!"):
                cell_part = rng.split("!", 1)[1]
                parameters["range"] = f"'{tab}'!{cell_part}" if " " in tab else f"{tab}!{cell_part}"
            elif "!" not in rng:
                parameters["range"] = f"'{tab}'!{rng}" if " " in tab else f"{tab}!{rng}"

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
# Nested $ placeholder resolver
# ---------------------------------------------------------------------------

def _resolve_nested_dollar(value: Any, context: dict[str, Any], executor: "PlanExecutor") -> Any:
    """Recursively resolve $-style placeholders that may appear inside lists/dicts."""
    if isinstance(value, dict):
        return {k: _resolve_nested_dollar(v, context, executor) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_nested_dollar(item, context, executor) for item in value]
    if not isinstance(value, str):
        return value
    # Only resolve known $ tokens — leave unknown ones to be caught by _find_unresolved_placeholder
    known_resolvers: dict[str, Any] = {
        "$last_spreadsheet_id": context.get("last_spreadsheet_id") or "",
        "$last_document_id": context.get("last_document_id") or "",
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
    """Format web search results as a Markdown document body."""
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
    """Format web search results as a 2-D list suitable for Sheets append."""
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
    """Return body text of fetched full messages, or fall back to listing message IDs.

    Fallback path: when no gmail.get_message tasks were executed (only list_messages),
    the raw stub objects {id, threadId} carry no body. We return the message IDs so
    callers (and tests) can still verify the data made it into the output.
    """
    # --- Priority 1: fully-fetched message objects (from get_message tasks) ---
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

    # --- Priority 2: raw list stubs from list_messages (id + threadId only) ---
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
    """Recursively resolves {{task_id.key}} placeholders in parameters."""
    if isinstance(value, dict):
        return {k: _resolve_template(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_template(v, context) for v in value]
    if not isinstance(value, str):
        return value

    def replacer(match: re.Match) -> str:
        task_id = match.group(1)
        key = match.group(2)
        results = context.get("task_results", {})
        task_payload = results.get(task_id)

        if not isinstance(task_payload, dict):
            return match.group(0)

        val = task_payload.get(key)
        if val is not None:
            return str(val)

        normalized_key = key.lower().replace("_", "")
        for p_key, p_val in task_payload.items():
            if p_key.lower().replace("_", "") == normalized_key:
                return str(p_val)

        return match.group(0)

    return re.sub(r"\{\{([\w\-]+)\.(\w+)\}\}", replacer, value)


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
