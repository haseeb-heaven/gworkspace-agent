"""Hybrid LangChain/LangGraph planning for natural-language Workspace requests."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from .langchain_agent import plan_with_langchain
from .models import AppConfigModel, PlannedTask, RequestPlan
from .service_catalog import SERVICES, normalize_service


NO_SERVICE_MESSAGE = "No Google Workspace service detected in your request."


class WorkspaceAgentSystem:
    """Plans one or more gws tasks from a natural-language request."""

    def __init__(self, config: AppConfigModel, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self._use_langchain = bool(self.config.api_key)

    def plan(self, user_text: str) -> RequestPlan:
        text = (user_text or "").strip()
        if not text:
            return RequestPlan(
                raw_text=user_text,
                summary=NO_SERVICE_MESSAGE,
                no_service_detected=True,
            )

        if self._use_langchain:
            plan = plan_with_langchain(text, self.config, self.logger)
            if plan and plan.tasks:
                return plan
            if plan and plan.no_service_detected:
                return plan

        return self._plan_with_heuristics(text)

    def _plan_from_payload(self, text: str, payload: dict[str, Any], source: str) -> RequestPlan:
        tasks: list[PlannedTask] = []
        raw_tasks = payload.get("tasks") or payload.get("plan") or payload.get("steps") or []
        if not isinstance(raw_tasks, list):
            raw_tasks = []

        for index, item in enumerate(raw_tasks, start=1):
            if not isinstance(item, dict):
                continue
            service = normalize_service(str(item.get("service") or ""))
            action = str(item.get("action") or "").strip()
            parameters = item.get("parameters") or item.get("params")
            if not isinstance(parameters, dict):
                parameters = {}
            if not service or action not in SERVICES[service].actions:
                self.logger.warning("Skipping unknown service/action in plan: %s.%s", service, action)
                continue
            tasks.append(
                PlannedTask(
                    id=str(item.get("id") or f"task-{index}"),
                    service=service,
                    action=action,
                    parameters=parameters,
                    reason=str(item.get("reason") or "").strip(),
                )
            )

        no_service_detected = bool(payload.get("no_service_detected"))
        summary = str(payload.get("summary") or "").strip()
        if no_service_detected:
            summary = NO_SERVICE_MESSAGE

        return RequestPlan(
            raw_text=payload.get("raw_text") or text,
            tasks=tasks,
            summary=summary,
            confidence=float(payload.get("confidence") or (0.9 if tasks else 0.0)),
            no_service_detected=no_service_detected,
            source=source,
        )

    def _plan_with_heuristics(self, text: str) -> RequestPlan:
        lowered = text.lower()
        services = _detect_services_in_order(lowered)
        if "search" in services and any(service in services for service in ("gmail", "drive")):
            services = [service for service in services if service != "search"]
        if not services:
            return RequestPlan(
                raw_text=text,
                summary=NO_SERVICE_MESSAGE,
                confidence=0.2,
                no_service_detected=True,
            )

        if _is_external_research_request(lowered, services):
            tasks = self._web_research_to_docs_and_sheets_tasks(text)
        elif _is_drive_docs_to_sheet_request(lowered, services):
            tasks = self._drive_docs_to_sheet_email_tasks(text, lowered)
        elif "gmail" in services and "sheets" in services and _is_sheet_to_email_request(lowered):
            tasks = self._sheet_to_email_tasks(text)
        elif "gmail" in services and "sheets" in services:
            tasks = self._gmail_to_sheets_tasks(text, lowered)
        elif services == ["gmail"]:
            tasks = self._gmail_read_tasks(lowered)
        else:
            tasks = [self._single_service_task(service, lowered, index) for index, service in enumerate(services, start=1)]

        return RequestPlan(
            raw_text=text,
            tasks=tasks,
            summary=f"Planned {len(tasks)} task{'s' if len(tasks) != 1 else ''}: "
            + ", ".join(f"{task.service}.{task.action}" for task in tasks),
            confidence=0.55,
            no_service_detected=False,
        )

    def _gmail_to_sheets_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        query = _gmail_query_from_text(lowered)
        max_results = _first_int(lowered) or 10
        spreadsheet_id = _extract_google_id(text)
        wants_company = _has_any(lowered, ("company", "companies", "organization", "employer", "extract"))
        desired_title = _sheet_title_from_text(text)
        sheet_title = desired_title or _spreadsheet_title_from_query(query)
        tasks = [
            PlannedTask(
                id="task-1",
                service="gmail",
                action="list_messages",
                parameters={"q": query, "max_results": max_results},
                reason="Search Gmail before writing the results anywhere else.",
            )
        ]
        if wants_company:
            tasks.append(
                PlannedTask(
                    id=f"task-{len(tasks) + 1}",
                    service="gmail",
                    action="get_message",
                    parameters={"message_id": "$gmail_message_ids"},
                    reason="Fetch full message content so company names can be extracted.",
                )
            )
        if spreadsheet_id:
            target_spreadsheet = spreadsheet_id
        else:
            target_spreadsheet = "$last_spreadsheet_id"
            tasks.append(
                PlannedTask(
                    id=f"task-{len(tasks) + 1}",
                    service="sheets",
                    action="create_spreadsheet",
                    parameters={"title": sheet_title},
                    reason="Create a spreadsheet because the request asked to save results to Sheets.",
                )
            )
        tasks.append(
            PlannedTask(
                id=f"task-{len(tasks) + 1}",
                service="sheets",
                action="append_values",
                parameters={
                    "spreadsheet_id": target_spreadsheet,
                    "range": "Sheet1!A1",
                    "values": "$gmail_summary_values",
                },
                reason="Append a readable summary of the Gmail search results.",
            )
        )
        recipient = _recipient_from_text(text)
        if _wants_email_link(lowered) and recipient:
            tasks.append(
                PlannedTask(
                    id=f"task-{len(tasks) + 1}",
                    service="gmail",
                    action="send_message",
                    parameters={
                        "to_email": recipient,
                        "subject": sheet_title,
                        "body": "Here is the requested spreadsheet link for the generated sheet.",
                    },
                    reason="Email the generated sheet link to the user.",
                )
            )
        return tasks

    def _sheet_to_email_tasks(self, text: str) -> list[PlannedTask]:
        spreadsheet_id = _extract_google_id(text) or ""
        recipient = _recipient_from_text(text)
        subject = _email_subject_from_text(text) or "Spreadsheet data export"
        return [
            PlannedTask(
                id="task-1",
                service="sheets",
                action="get_values",
                parameters={"spreadsheet_id": spreadsheet_id, "range": "Sheet1!A1:Z500"},
                reason="Read the requested spreadsheet values first.",
            ),
            PlannedTask(
                id="task-2",
                service="gmail",
                action="send_message",
                parameters={"to_email": recipient, "subject": subject, "body": "$sheet_email_body"},
                reason="Compose and send an email using spreadsheet data.",
            ),
        ]

    def _gmail_read_tasks(self, lowered: str) -> list[PlannedTask]:
        list_task = PlannedTask(
            id="task-1",
            service="gmail",
            action="list_messages",
            parameters={"q": _gmail_query_from_text(lowered), "max_results": _first_int(lowered) or 10},
            reason="Find matching Gmail messages first.",
        )
        if _wants_email_details(lowered):
            return [
                list_task,
                PlannedTask(
                    id="task-2",
                    service="gmail",
                    action="get_message",
                    parameters={"message_id": "$gmail_message_ids"},
                    reason="Read message headers and snippets so the output is human-readable.",
                ),
            ]
        return [list_task]

    def _web_research_to_docs_and_sheets_tasks(self, text: str) -> list[PlannedTask]:
        query = _web_search_query_from_text(text)
        title = _title_from_query(query, fallback="Research Summary")
        return [
            PlannedTask(
                id="task-1",
                service="search",
                action="web_search",
                parameters={"query": query},
                reason="Gather external information before saving it to Workspace.",
            ),
            PlannedTask(
                id="task-2",
                service="docs",
                action="create_document",
                parameters={"title": title},
                reason="Create a Google Doc for the research summary.",
            ),
            PlannedTask(
                id="task-3",
                service="docs",
                action="batch_update",
                parameters={"document_id": "$last_document_id", "text": "$web_search_markdown"},
                reason="Write the web research summary into the new document.",
            ),
            PlannedTask(
                id="task-4",
                service="sheets",
                action="create_spreadsheet",
                parameters={"title": title},
                reason="Create a spreadsheet for the structured research table.",
            ),
            PlannedTask(
                id="task-5",
                service="sheets",
                action="append_values",
                parameters={
                    "spreadsheet_id": "$last_spreadsheet_id",
                    "range": "Sheet1!A1",
                    "values": "$web_search_table_values",
                },
                reason="Store the web research in a tabular format.",
            ),
        ]

    def _drive_docs_to_sheet_email_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        search_term = _document_search_term(text)
        drive_query = f"fullText contains '{search_term}'" if search_term else _drive_query_from_text(lowered)
        title = _title_from_query(search_term or _first_quoted_or_topic(text), fallback="Document Summary")
        recipient = _recipient_from_text(text)
        slug = _slugify(title)
        tasks = [
            PlannedTask(
                id="task-1",
                service="drive",
                action="list_files",
                parameters={"q": drive_query, "page_size": 10},
                reason="Find the matching Google Document in Drive first.",
            ),
            PlannedTask(
                id="task-2",
                service="docs",
                action="get_document",
                parameters={"document_id": "$last_drive_file_id"},
                reason="Read the source document content.",
            ),
            PlannedTask(
                id="task-3",
                service="docs",
                action="create_document",
                parameters={"title": title},
                reason="Create a new Google Doc for the converted table output.",
            ),
            PlannedTask(
                id="task-4",
                service="docs",
                action="batch_update",
                parameters={"document_id": "$last_document_id", "text": "$document_table_text"},
                reason="Save the converted document content in a table-like text format.",
            ),
            PlannedTask(
                id="task-5",
                service="sheets",
                action="create_spreadsheet",
                parameters={"title": title},
                reason="Create a spreadsheet for the structured table output.",
            ),
            PlannedTask(
                id="task-6",
                service="sheets",
                action="append_values",
                parameters={
                    "spreadsheet_id": "$last_spreadsheet_id",
                    "range": "Sheet1!A1",
                    "values": "$document_table_values",
                },
                reason="Write the converted document rows to the spreadsheet.",
            ),
            PlannedTask(
                id="task-7",
                service="drive",
                action="export_file",
                parameters={
                    "file_id": "$last_document_id",
                    "mime_type": "application/pdf",
                    "output_path": f"scratch/exports/{slug}.pdf",
                },
                reason="Export the generated Google Doc for attachment.",
            ),
            PlannedTask(
                id="task-8",
                service="drive",
                action="export_file",
                parameters={
                    "file_id": "$last_spreadsheet_id",
                    "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "output_path": f"scratch/exports/{slug}.xlsx",
                },
                reason="Export the generated Google Sheet for attachment.",
            ),
        ]
        if recipient:
            tasks.append(
                PlannedTask(
                    id=f"task-{len(tasks) + 1}",
                    service="gmail",
                    action="send_message",
                    parameters={
                        "to_email": recipient,
                        "subject": f"{title} links and attachments",
                        "body": "Attached are the exported Google Doc and Google Sheet. The corresponding links are included below.",
                        "attachments": "$exported_file_paths",
                    },
                    reason="Email the created assets with links and local attachments.",
                )
            )
        return tasks

    def _single_service_task(self, service: str, lowered: str, index: int) -> PlannedTask:
        action = _detect_action(service, lowered) or next(iter(SERVICES[service].actions))
        parameters: dict[str, Any] = {}
        if service == "gmail" and action == "list_messages":
            parameters["q"] = _gmail_query_from_text(lowered)
            parameters["max_results"] = _first_int(lowered) or 10
        elif service == "drive" and action == "list_files":
            parameters["page_size"] = _first_int(lowered) or 10
            drive_query = _drive_query_from_text(lowered)
            if drive_query:
                parameters["q"] = drive_query
        elif service == "search" and action == "web_search":
            parameters["query"] = _web_search_query_from_text(lowered)
        elif service == "contacts" and action == "list_contacts":
            parameters["page_size"] = _first_int(lowered) or 10
        return PlannedTask(
            id=f"task-{index}",
            service=service,
            action=action,
            parameters=parameters,
            reason=f"Detected {SERVICES[service].label} in the request.",
        )


def _detect_services_in_order(text: str) -> list[str]:
    hits: list[tuple[int, str]] = []
    for service_key, spec in SERVICES.items():
        terms = (service_key, *spec.aliases)
        positions = [text.find(term) for term in terms if term in text]
        if positions:
            hits.append((min(position for position in positions if position >= 0), service_key))
    return [service for _, service in sorted(hits, key=lambda item: item[0])]


def _detect_action(service: str, text: str) -> str | None:
    best_action = None
    best_score = 0
    for action_key, action_spec in SERVICES[service].actions.items():
        score = sum(1 for keyword in action_spec.keywords if keyword in text)
        if score > best_score:
            best_score = score
            best_action = action_key
    return best_action


def _gmail_query_from_text(text: str) -> str:
    quoted = _first_quoted_or_topic(text)
    query = quoted.strip() if quoted else ""
    if "ticket" in text:
        query = "ticket OR tickets"
    elif "unread" in text:
        query = "is:unread"
    elif not query:
        match = re.search(r"(?:about|for|matching|with)\s+([a-z0-9 _.-]{3,80})", text)
        if match:
            query = _trim_follow_on_instruction(match.group(1))
    if not query and "job offer" in text:
        query = "job offer"
    if "last week" in text and "newer_than:" not in query and "after:" not in query:
        query = f"{query} newer_than:7d".strip()
    return query


def _drive_query_from_text(text: str) -> str:
    quoted = re.findall(r"""['"]([^'"]{2,80})['"]""", text)
    if quoted:
        parts = [f"fullText contains '{q.strip()}'" for q in quoted[:2]]
        return " or ".join(parts)
    match = re.search(r"(?:search|find|for|about)\s+([a-z0-9 _.-]{3,80})", text)
    if match:
        term = _trim_follow_on_instruction(match.group(1)).strip()
        if term and len(term) > 2:
            return f"fullText contains '{term}'"
    return ""


def _document_search_term(text: str) -> str:
    quoted = _first_quoted_or_topic(text)
    if quoted:
        return quoted
    match = re.search(
        r"(?:google\s+documents?|google\s+docs|documents?|docs)\s+for\s+(.+?)(?:\s+and\s+(?:convert|save|create|send|email|append)\b|$)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1).strip(" .")
    return ""


def _web_search_query_from_text(text: str) -> str:
    quoted = _first_quoted_or_topic(text)
    if quoted:
        return quoted
    match = re.search(
        r"(?:find|search|lookup|research)\s+(.+?)(?:\s+and\s+(?:save|create|send|email|convert)\b|$)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1).strip(" .")
    return text.strip()


def _spreadsheet_title_from_query(query: str) -> str:
    suffix = query.replace(" OR ", " ").strip() or "Gmail"
    return f"{suffix.title()} Search Results"


def _sheet_title_from_text(text: str) -> str:
    explicit = re.search(r"(?:sheet|spreadsheet)\s+['\"]([^'\"]{2,120})['\"]", text, flags=re.IGNORECASE)
    if explicit:
        return explicit.group(1).strip()
    return ""


def _title_from_query(query: str, fallback: str) -> str:
    cleaned = re.sub(r"\b(top\s+\d+|find|search|lookup|research)\b", "", query, flags=re.IGNORECASE).strip(" .")
    if not cleaned:
        return fallback
    return " ".join(word.capitalize() for word in cleaned.split())


def _first_quoted_or_topic(text: str) -> str:
    quoted = re.findall(r"""['"]([^'"]{2,80})['"]""", text)
    return quoted[0].strip() if quoted else ""


def _extract_google_id(text: str) -> str | None:
    match = re.search(r"\b([a-zA-Z0-9_-]{25,})\b", text)
    return match.group(1) if match else None


def _extract_email(text: str) -> str | None:
    match = re.search(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b", text)
    return match.group(1) if match else None


def _email_subject_from_text(text: str) -> str | None:
    quoted = re.search(r"subject\s*[:=]\s*['\"]([^'\"]+)['\"]", text, flags=re.IGNORECASE)
    if quoted:
        return quoted.group(1).strip()
    return None


def _recipient_from_text(text: str) -> str:
    explicit = _extract_email(text)
    if explicit:
        return explicit
    return (
        os.getenv("DEFAULT_RECIPIENT_EMAIL")
        or os.getenv("DEFAULT_TO_EMAIL")
        or os.getenv("ASSISTANT_USER_EMAIL")
        or ""
    ).strip()


def _first_int(text: str) -> int | None:
    match = re.search(r"\b(\d{1,3})\b", text)
    if not match:
        return None
    value = int(match.group(1))
    return value if value > 0 else None


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _trim_follow_on_instruction(value: str) -> str:
    cleaned = value.strip(" .")
    stop_patterns = (
        r"\s+and\s+save\b",
        r"\s+and\s+write\b",
        r"\s+and\s+export\b",
        r"\s+and\s+create\b",
        r"\s+and\s+convert\b",
        r"\s+and\s+send\b",
        r"\s+and\s+email\b",
        r"\s+into\s+google\s+sheets\b",
        r"\s+into\s+sheets\b",
        r"\s+to\s+google\s+sheets\b",
        r"\s+to\s+sheets\b",
    )
    for pattern in stop_patterns:
        match = re.search(pattern, cleaned)
        if match:
            cleaned = cleaned[: match.start()].strip(" .")
            break
    return cleaned


def _is_sheet_to_email_request(text: str) -> bool:
    send_terms = (
        "send it",
        "send this",
        "send to",
        "send email",
        "create email",
        "compose email",
        "email this",
        "email it",
    )
    return any(term in text for term in send_terms)


def _wants_email_details(text: str) -> bool:
    terms = (
        "list all",
        "show all",
        "view emails",
        "read emails",
        "received emails",
        "emails from",
        "show emails",
    )
    return any(term in text for term in terms)


def _wants_email_link(text: str) -> bool:
    return any(term in text for term in ("email me", "send me", "email the link", "send the link", "send email"))


def _is_external_research_request(text: str, services: list[str]) -> bool:
    return (
        ("search" in services or "drive" in services)
        and ("docs" in services or "sheets" in services)
        and "gmail" not in services
        and ("top " in text or "framework" in text or "frameworks" in text or text.startswith("find "))
        and "search google documents" not in text
        and "search google docs" not in text
    )


def _is_drive_docs_to_sheet_request(text: str, services: list[str]) -> bool:
    return (
        "drive" in services
        and "sheets" in services
        and _has_any(text, ("search google documents", "search google docs"))
        and _has_any(text, ("convert", "table", "sheet", "spreadsheet"))
    )


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned or "export"
