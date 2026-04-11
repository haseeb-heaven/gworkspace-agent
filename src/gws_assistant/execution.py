"""Plan execution service for ordered Google Workspace tasks."""

from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path
from typing import Any

from .gws_runner import GWSRunner
from .models import ExecutionResult, PlanExecutionReport, PlannedTask, RequestPlan, TaskExecution
from .planner import CommandPlanner
from .relevance import extract_keywords, filter_drive_files, filter_gmail_messages
from .tools import code_execution_tool, web_search_tool


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
                    self.logger.warning("Stopping plan after failed task id=%s", resolved_task.id)
                    return PlanExecutionReport(plan=plan, executions=executions)
        return PlanExecutionReport(plan=plan, executions=executions)

    def execute_single_task(self, task: PlannedTask, context: dict[str, Any]) -> ExecutionResult:
        """Executes a single fully-resolved task and updates the context."""
        placeholder = _find_unresolved_placeholder(task.parameters)
        if placeholder:
            return ExecutionResult(
                success=False,
                command=[],
                error=f"Plan contained an unresolved placeholder: {placeholder}",
            )
            
        cmd = self.planner.build_command(
            task.service,
            task.action,
            task.parameters,
        )

        # Handle INTERNAL pseudo-commands
        if task.service == "drive" and task.action == "export_file":
            output_path = str(task.parameters.get("output_path") or "").strip()
            if output_path:
                Path(output_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

        if cmd and cmd[0] == "INTERNAL":
            result = self._handle_internal_command(cmd, task, context)
        else:
            if hasattr(self.runner, "run_with_retry"):
                result = self.runner.run_with_retry(cmd)
            else:
                result = self.runner.run(cmd)
            
        self._update_context(task, result, context)
        return result

    def _handle_internal_command(self, cmd: list[str], task: PlannedTask, context: dict[str, Any]) -> ExecutionResult:
        """Handles commands that are executed internally by Python tools rather than gws binary."""
        self.logger.info("Handling internal command: %s", cmd)
        service = cmd[1]
        params = task.parameters
        task_id = task.id
        
        if service == "search":
            query = str(params.get("query") or "").strip()
            try:
                search_res = web_search_tool.invoke({"query": query})
            except Exception as exc:
                return ExecutionResult(success=False, command=cmd, error=f"Web search failed: {exc}")
            if search_res.get("error"):
                return ExecutionResult(success=False, command=cmd, stdout=json.dumps(search_res), error=str(search_res["error"]))

            context["web_search_payload"] = search_res
            context["web_search_summary"] = _render_web_search_text(search_res)
            return ExecutionResult(
                success=True,
                command=["INTERNAL", "search", query],
                stdout=json.dumps(search_res),
            )

        if service == "code":
            code = str(params.get("code") or "")
            code_res = code_execution_tool.invoke({"code": code})
            return ExecutionResult(
                success=bool(code_res.get("success")),
                command=["INTERNAL", "code", code[:50] + "..."],
                stdout=json.dumps(code_res),
                error=code_res.get("error"),
            )
            
        return ExecutionResult(success=False, command=cmd, error=f"Unknown internal command: {cmd[1]}")

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
        
        # Limit details to the first 5 messages to keep output readable and execution fast.
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
        parameters = dict(task.parameters)
        for key, value in list(parameters.items()):
            parameters[key] = self._resolve_parameter_value(task, key, value, context)
            
            # Additional context injection: if body wants a link and we have one
            if key == "body" and isinstance(parameters[key], str):
                links = [
                    context.get("last_spreadsheet_url"),
                    context.get("last_document_url"),
                    context.get("last_drive_file_url"),
                ]
                links = [str(link) for link in links if link]
                if links and any(term in parameters[key].lower() for term in ("link", "sheet", "doc", "file", "attach")):
                    missing = [link for link in links if link not in parameters[key]]
                    if missing:
                        parameters[key] = f"{parameters[key]}\n\nLinks:\n" + "\n".join(missing)
                    
        # Fix range to use correct tab name when using a just-created spreadsheet
        if (task.service == "sheets" and task.action == "append_values" 
                and "range" in parameters and context.get("last_spreadsheet_tab")):
            rng = str(parameters.get("range") or "")
            tab = context["last_spreadsheet_tab"]
            # Replace default "Sheet1" with the actual tab name
            if rng.startswith("Sheet1!"):
                cell_part = rng.split("!", 1)[1]
                if " " in tab:
                    parameters["range"] = f"'{tab}'!{cell_part}"
                else:
                    parameters["range"] = f"{tab}!{cell_part}"
            elif "!" not in rng:
                # Just a cell ref like "A1" — prefix with tab name
                if " " in tab:
                    parameters["range"] = f"'{tab}'!{rng}"
                else:
                    parameters["range"] = f"{tab}!{rng}"
                    
        return PlannedTask(
            id=task.id,
            service=task.service,
            action=task.action,
            parameters=parameters,
            reason=task.reason,
        )

    def _resolve_parameter_value(self, task: PlannedTask, key: str, value: Any, context: dict[str, Any]) -> Any:
        if isinstance(value, dict):
            return {inner_key: self._resolve_parameter_value(task, inner_key, inner_value, context) for inner_key, inner_value in value.items()}
        if isinstance(value, list):
            if task.service == "sheets" and task.action == "append_values" and key == "values":
                if self._contains_placeholder(value, "$gmail_message_body"):
                    return self._gmail_summary_values(context)
            return [self._resolve_parameter_value(task, key, item, context) for item in value]
        if not isinstance(value, str):
            return value

        if value == "$last_spreadsheet_id":
            return context.get("last_spreadsheet_id") or ""
        if value == "$last_document_id":
            return context.get("last_document_id") or ""
        if value == "$last_drive_file_id":
            return context.get("last_drive_file_id") or ""
        if value == "$last_folder_id":
            return context.get("last_folder_id") or ""
        if value == "$gmail_summary_values":
            return self._gmail_summary_values(context)
        if value == "$sheet_email_body":
            return self._sheet_email_body(context)
        if value == "$drive_summary_values":
            return self._drive_summary_values(context)
        if value == "$document_table_values":
            return self._document_table_values(context)
        if value == "$document_table_text":
            return self._document_table_text(context)
        if value == "$web_search_results":
            return context.get("web_search_summary") or "No search results found."
        if value == "$web_search_table_values":
            return self._web_search_table_values(context)
        if value == "$web_search_markdown":
            return self._web_search_markdown(context)
        if value == "$gmail_message_body":
            if task.service == "sheets" and task.action == "append_values" and key == "values":
                return self._gmail_summary_values(context)
            return context.get("last_message_body") or ""
        if value == "$exported_file_paths":
            return [item["path"] for item in context.get("exported_files", []) if item.get("path")]
        if _is_gmail_values_placeholder(value) and key in ("body", "values"):
            return self._gmail_summary_values(context)
        if _is_sheet_body_placeholder(value) and key in ("body", "values"):
            return self._sheet_email_body(context)
        if "$drive_summary" in value.lower() and key in ("body", "values"):
            return self._drive_summary_values(context)
        return value

    @staticmethod
    def _contains_placeholder(value: Any, token: str) -> bool:
        if isinstance(value, str):
            return token in value
        if isinstance(value, dict):
            return any(PlanExecutor._contains_placeholder(child, token) for child in value.values())
        if isinstance(value, list):
            return any(PlanExecutor._contains_placeholder(child, token) for child in value)
        return False

    def _update_context(self, task: PlannedTask, result: ExecutionResult, context: dict[str, Any]) -> None:
        stdout = result.stdout
        payload = _parse_json(stdout)
        user_keywords = extract_keywords(str(context.get("request_text") or ""))
        
        if task.service == "gmail" and task.action == "list_messages":
            context["gmail_query"] = task.parameters.get("q") or ""
            context["gmail_payload"] = payload or {}
            context["gmail_message_ids"] = _gmail_message_ids(context)
        
        if task.service == "gmail" and task.action == "get_message" and payload:
            context.setdefault("gmail_messages", []).append(payload)
            # Fetch message body/snippet for later tasks
            context["last_message_body"] = payload.get("snippet", "")
            if "payload" in payload and "body" in payload["payload"]:
                 # More complex body extraction
                 pass
            
            # Apply relevance filtering to accumulated messages
            all_msgs = context.get("gmail_messages", [])
            if len(all_msgs) > 1:
                context["gmail_messages"] = filter_gmail_messages(all_msgs, user_keywords)
        
        if task.service == "sheets" and task.action == "create_spreadsheet" and payload:
            context["last_spreadsheet_id"] = payload.get("spreadsheetId") or ""
            context["last_spreadsheet_url"] = payload.get("spreadsheetUrl") or ""
            # Track the tab name for range resolution
            sheets_list = payload.get("sheets")
            if isinstance(sheets_list, list) and sheets_list:
                first_sheet = sheets_list[0]
                if isinstance(first_sheet, dict):
                    props = first_sheet.get("properties") or {}
                    context["last_spreadsheet_tab"] = props.get("title") or ""
            if not context.get("last_spreadsheet_tab"):
                title = (payload.get("properties") or {}).get("title") or ""
                context["last_spreadsheet_tab"] = title

        if task.service == "drive" and task.action == "list_files" and payload:
            # Apply relevance filtering to Drive files
            files = payload.get("files") if isinstance(payload, dict) else []
            if isinstance(files, list):
                filtered = filter_drive_files(files, user_keywords)
                payload["files"] = filtered
                if filtered:
                    preferred = next(
                        (
                            item
                            for item in filtered
                            if item.get("mimeType") == "application/vnd.google-apps.document"
                        ),
                        filtered[0],
                    )
                    context["last_drive_file_id"] = preferred.get("id") or ""
                    context["last_drive_file_url"] = preferred.get("webViewLink") or ""
                    context["last_drive_file_name"] = preferred.get("name") or ""
                    # Track last folder found if any
                    folders = [f for f in filtered if f.get("mimeType") == "application/vnd.google-apps.folder"]
                    if folders:
                        context["last_folder_id"] = folders[0].get("id")
            context["drive_query"] = task.parameters.get("q") or ""
            context["drive_payload"] = payload

        if task.service == "drive" and task.action == "export_file" and result.success:
            output_path = str(task.parameters.get("output_path") or "").strip()
            if output_path:
                context.setdefault("exported_files", []).append(
                    {
                        "file_id": str(task.parameters.get("file_id") or ""),
                        "mime_type": str(task.parameters.get("mime_type") or ""),
                        "path": output_path,
                    }
                )
                context["last_export_path"] = output_path

        if task.service == "drive" and task.action == "create_folder" and payload:
            context["last_folder_id"] = payload.get("id") or ""

        if task.service == "docs" and task.action == "create_document" and payload:
             context["last_document_id"] = payload.get("documentId") or ""
             doc_id = payload.get("documentId") or ""
             if doc_id:
                context["last_document_url"] = f"https://docs.google.com/document/d/{doc_id}/edit"

        if task.service == "docs" and task.action == "get_document" and payload:
             context["last_document_id"] = payload.get("documentId") or ""
             context["last_document_title"] = payload.get("title") or ""
             context["last_document_body"] = payload.get("body") or ""
             context["document_payload"] = payload

        if task.service == "search" and task.action == "web_search" and result.success:
             parsed = _parse_json(result.stdout)
             if parsed:
                 context["web_search_payload"] = parsed
                 context["web_search_summary"] = _render_web_search_text(parsed)
             else:
                 context["web_search_summary"] = result.stdout

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
                        rows.append(
                            [
                                query,
                                company,
                                subject,
                                from_value,
                                str(message.get("id") or ""),
                            ]
                        )
                if len(rows) == 1:
                    rows.append([query, "No company names detected", "", "", ""])
                return rows

            rows = [["Search", "Company", "From", "Subject", "Message ID"]]
            for message in fetched_messages[:50]:
                if isinstance(message, dict):
                    headers = _gmail_headers(message)
                    from_value = headers.get("from", "")
                    rows.append(
                        [
                            query,
                            _company_from_sender(from_value),
                            from_value,
                            headers.get("subject", ""),
                            str(message.get("id") or ""),
                        ]
                    )
            return rows

        rows = [["Search", "Message ID", "Thread ID"]]
        for message in _gmail_messages(context)[:50]:
            rows.append(
                [
                    query,
                    str(message.get("id") or ""),
                    str(message.get("threadId") or ""),
                ]
            )
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

    @staticmethod
    def _document_table_values(context: dict[str, Any]) -> list[list[str]]:
        payload = context.get("document_payload") or {}
        title = str(payload.get("title") or context.get("last_drive_file_name") or "Document")
        text_blocks = _docs_text_blocks(payload)
        rows: list[list[str]] = [["Line", "Text"]]
        if not text_blocks:
            rows.append(["1", f"No document text found for {title}."])
            return rows
        for index, block in enumerate(text_blocks[:100], start=1):
            rows.append([str(index), block])
        return rows

    @staticmethod
    def _document_table_text(context: dict[str, Any]) -> str:
        rows = PlanExecutor._document_table_values(context)
        if not rows:
            return "No document content was found."
        header = " | ".join(rows[0])
        divider = " | ".join("---" for _ in rows[0])
        body = [" | ".join(row) for row in rows[1:]]
        return "\n".join([header, divider, *body]).strip()

    @staticmethod
    def _web_search_table_values(context: dict[str, Any]) -> list[list[str]]:
        payload = context.get("web_search_payload") or {}
        results = payload.get("results") if isinstance(payload, dict) else []
        rows: list[list[str]] = [["Title", "Snippet", "Link"]]
        if not isinstance(results, list) or not results:
            rows.append(["No results", str(payload.get("query") or ""), ""])
            return rows
        for item in results[:20]:
            if isinstance(item, dict):
                rows.append([
                    str(item.get("title") or "Result"),
                    str(item.get("content") or item.get("snippet") or ""),
                    str(item.get("link") or ""),
                ])
        return rows

    @staticmethod
    def _web_search_markdown(context: dict[str, Any]) -> str:
        rows = PlanExecutor._web_search_table_values(context)
        if len(rows) <= 1:
            return "No web search results were found."
        lines = ["Top results:", ""]
        for row in rows[1:]:
            title, snippet, link = row
            lines.append(f"- {title}: {snippet}")
            if link:
                lines.append(f"  {link}")
        return "\n".join(lines).strip()


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


def _render_web_search_text(payload: dict[str, Any]) -> str:
    results = payload.get("results") if isinstance(payload, dict) else []
    if not isinstance(results, list) or not results:
        return "No web search results found."
    lines: list[str] = []
    for item in results[:10]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "Result")
        content = str(item.get("content") or item.get("snippet") or "").strip()
        link = str(item.get("link") or "").strip()
        line = f"{title}: {content}".strip(": ")
        if link:
            line = f"{line} ({link})"
        lines.append(line)
    return "\n".join(lines).strip() or "No web search results found."


def _docs_text_blocks(payload: dict[str, Any]) -> list[str]:
    body = payload.get("body") if isinstance(payload.get("body"), dict) else {}
    content = body.get("content") if isinstance(body.get("content"), list) else []
    blocks: list[str] = []
    current: list[str] = []

    for section in content:
        if not isinstance(section, dict):
            continue
        paragraph = section.get("paragraph") if isinstance(section.get("paragraph"), dict) else {}
        elements = paragraph.get("elements") if isinstance(paragraph.get("elements"), list) else []
        current.clear()
        for element in elements:
            text_run = element.get("textRun") if isinstance(element, dict) and isinstance(element.get("textRun"), dict) else {}
            text = str(text_run.get("content") or "").replace("\n", " ").strip()
            if text:
                current.append(text)
        merged = " ".join(current).strip()
        if merged:
            blocks.append(merged)
    return blocks
