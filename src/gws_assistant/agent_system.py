"""CrewAI-backed planning for natural-language Workspace requests."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from .models import AppConfigModel, PlannedTask, RequestPlan
from .service_catalog import SERVICES, normalize_service

from .langchain_agent import plan_with_langchain


NO_SERVICE_MESSAGE = "No Google Workspace service detected in your request."

# Keywords that signal the user wants to search/find external information first.
_WEB_SEARCH_TRIGGERS = (
    "find top",
    "search for",
    "look up",
    "find best",
    "find latest",
    "what are the top",
    "top 3",
    "top 5",
    "top 10",
    "best ",
    "list of",
)


class WorkspaceAgentSystem:
    """Plans one or more gws tasks from a natural-language request."""

    def __init__(self, config: AppConfigModel, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self._use_langchain = bool(self.config.langchain_enabled and self.config.api_key)

    def plan(self, user_text: str) -> RequestPlan:
        from .memory import recall_similar
        past = recall_similar(user_text)
        if past:
            self.logger.info("Memory: found %d similar past episodes", len(past))
            # Inject past context into LLM prompt if available

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
            if not self.config.use_heuristic_fallback:
                return RequestPlan(
                    raw_text=text,
                    summary="LLM planning failed and USE_HEURISTIC_FALLBACK is disabled.",
                    confidence=0.0,
                    no_service_detected=True,
                )
        elif not self.config.use_heuristic_fallback:
            return RequestPlan(
                raw_text=text,
                summary="No LLM configured and USE_HEURISTIC_FALLBACK is disabled.",
                confidence=0.0,
                no_service_detected=True,
            )

        return self._plan_with_heuristics(text)

    def _plan_from_payload(self, text: str, payload: dict[str, Any], source: str) -> RequestPlan:
        tasks: list[PlannedTask] = []
        for index, item in enumerate(payload.get("tasks") or [], start=1):
            if not isinstance(item, dict):
                continue
            service = normalize_service(str(item.get("service") or ""))
            action = str(item.get("action") or "").strip()
            if not service or action not in SERVICES[service].actions:
                continue
            parameters = item.get("parameters") if isinstance(item.get("parameters"), dict) else {}
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
            raw_text=text,
            tasks=tasks,
            summary=summary,
            confidence=float(payload.get("confidence") or 0.0),
            no_service_detected=no_service_detected,
            source=source,
        )

    def _plan_with_heuristics(self, text: str) -> RequestPlan:
        lowered = text.lower()
        services = _detect_services_in_order(lowered)
        self.logger.info(f"Heuristic planning: detected services {services}")

        if not services:
            # If query looks like a web search + save intent, mark for web_search routing.
            if _is_web_search_and_save(lowered):
                return RequestPlan(
                    raw_text=text,
                    summary="Web search and save intent detected — routing to web search.",
                    confidence=0.4,
                    no_service_detected=True,
                    needs_web_search=True,
                )
            return RequestPlan(
                raw_text=text,
                summary=NO_SERVICE_MESSAGE,
                confidence=0.2,
                no_service_detected=True,
            )

        has_save_intent = _has_any(lowered, ("save", "write", "store", "export", "append", "document", "doc"))

        # Pattern: find/search + save to docs + sheets (e.g. "Find top 3 AI frameworks and save to Docs and Sheets")
        if _is_web_search_and_save(lowered) and "docs" in services and "sheets" in services:
            tasks = self._web_search_to_docs_and_sheets_tasks(text, lowered)
            return RequestPlan(
                raw_text=text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: web search → docs.create_document + sheets.create_spreadsheet + sheets.append_values",
                confidence=0.7,
                no_service_detected=False,
                source="heuristic",
            )

        # Pattern: find/search + save to sheets only
        if _is_web_search_and_save(lowered) and "sheets" in services and "docs" not in services:
            tasks = self._web_search_to_sheets_tasks(text, lowered)
            return RequestPlan(
                raw_text=text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: web search → sheets.create_spreadsheet + sheets.append_values",
                confidence=0.65,
                no_service_detected=False,
                source="heuristic",
            )

        # Pattern: find/search + save to docs only
        if _is_web_search_and_save(lowered) and "docs" in services and "sheets" not in services:
            tasks = self._web_search_to_docs_tasks(text, lowered)
            return RequestPlan(
                raw_text=text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: web search → docs.create_document",
                confidence=0.65,
                no_service_detected=False,
                source="heuristic",
            )

        if "drive" in services and "sheets" in services and "gmail" in services:
            tasks = self._drive_to_sheets_email_tasks(text, lowered)
        elif "gmail" in services and "sheets" in services and _is_sheet_to_email_request(lowered):
            tasks = self._sheet_to_email_tasks(text, lowered)
        elif "gmail" in services and "sheets" in services and _has_any(lowered, ("save", "write", "export", "append")):
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

    def _web_search_to_docs_and_sheets_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        """Plan tasks: web_search result → create Docs document + create Sheets + append data."""
        topic = _extract_search_topic(lowered) or "Research Results"
        title = topic.title()
        return [
            PlannedTask(
                id="task-1",
                service="docs",
                action="create_document",
                parameters={"title": title, "content": "$web_search_summary"},
                reason="Create a Google Doc to store the research findings.",
            ),
            PlannedTask(
                id="task-2",
                service="sheets",
                action="create_spreadsheet",
                parameters={"title": title},
                reason="Create a Google Sheet to store the structured data.",
            ),
            PlannedTask(
                id="task-3",
                service="sheets",
                action="append_values",
                parameters={
                    "spreadsheet_id": "$last_spreadsheet_id",
                    "range": "Sheet1!A1",
                    "values": "$web_search_rows",
                },
                reason="Append the search results as rows in the spreadsheet.",
            ),
        ]

    def _web_search_to_sheets_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        topic = _extract_search_topic(lowered) or "Research Results"
        title = topic.title()
        return [
            PlannedTask(
                id="task-1",
                service="sheets",
                action="create_spreadsheet",
                parameters={"title": title},
                reason="Create a Google Sheet for the search results.",
            ),
            PlannedTask(
                id="task-2",
                service="sheets",
                action="append_values",
                parameters={
                    "spreadsheet_id": "$last_spreadsheet_id",
                    "range": "Sheet1!A1",
                    "values": "$web_search_rows",
                },
                reason="Append search results as rows.",
            ),
        ]

    def _web_search_to_docs_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        topic = _extract_search_topic(lowered) or "Research Results"
        title = topic.title()
        return [
            PlannedTask(
                id="task-1",
                service="docs",
                action="create_document",
                parameters={"title": title, "content": "$web_search_summary"},
                reason="Create a Google Doc with the research findings.",
            ),
        ]

    def _drive_to_sheets_email_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        query = _drive_query_from_text(lowered)
        recipient = _extract_email(text) or "haseebmir.hm@gmail.com"
        tasks = [
            PlannedTask(
                id="task-1",
                service="drive",
                action="list_files",
                parameters={"q": query, "page_size": 1},
                reason="Search for the requested document."
            ),
            PlannedTask(
                id="task-2",
                service="drive",
                action="export_file",
                parameters={"file_id": "{{task-1.output.id}}", "mime_type": "text/plain"},
                reason="Extract text content from the document."
            ),
            PlannedTask(
                id="task-3",
                service="sheets",
                action="create_spreadsheet",
                parameters={"title": f"Data from {query}"},
                reason="Prepare a new Sheet for the extracted data."
            ),
            PlannedTask(
                id="task-4",
                service="sheets",
                action="append_values",
                parameters={"spreadsheet_id": "{{task-3.output.spreadsheetId}}", "values": "{{task-2.output}}"},
                reason="Save extracted data to the new Sheet."
            ),
            PlannedTask(
                id="task-5",
                service="gmail",
                action="send_message",
                parameters={
                    "to_email": recipient,
                    "subject": "Processed Document Data",
                    "body": "Hi,\n\nPlease find the spreadsheet here: {{task-3.output.spreadsheetUrl}}"
                },
                reason="Send the results link to the user."
            )
        ]
        return tasks

    def _gmail_to_sheets_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        query = _gmail_query_from_text(lowered)
        max_results = _first_int(lowered) or 10
        spreadsheet_id = _extract_google_id(text)
        wants_company = _has_any(lowered, ("company", "companies", "organization", "employer"))
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
                    id="task-2",
                    service="sheets",
                    action="create_spreadsheet",
                    parameters={"title": _spreadsheet_title_from_query(query)},
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
        return tasks

    def _sheet_to_email_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        spreadsheet_id = _extract_google_id(text) or ""
        recipient = _extract_email(text) or ""
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
        elif service == "contacts" and action == "list_contacts":
            parameters["page_size"] = _first_int(lowered) or 10
        elif service == "docs" and action == "create_document":
            topic = _extract_search_topic(lowered) or "Document"
            parameters["title"] = topic.title()
            parameters["content"] = "$web_search_summary"
        elif service == "sheets" and action == "create_spreadsheet":
            topic = _extract_search_topic(lowered) or "Data"
            parameters["title"] = topic.title()
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
    if "ticket" in text:
        return "ticket OR tickets"
    if "unread" in text:
        return "is:unread"
    match = re.search(r"(?:about|for|matching|with)\s+([a-z0-9 _.-]{3,60})", text)
    if match:
        return _trim_follow_on_instruction(match.group(1))
    return ""


def _drive_query_from_text(text: str) -> str:
    """Extract a Drive API query filter from user text."""
    quoted = re.findall(r"""['"]([^'"]{2,80})['"]""", text)
    if quoted:
        parts = [f"fullText contains '{q.strip()}'" for q in quoted[:2]]
        return " or ".join(parts)

    match = re.search(r"(?:search|find|for|about)\s+([a-z0-9 _.-]{3,60})", text)
    if match:
        term = _trim_follow_on_instruction(match.group(1)).strip()
        if term and len(term) > 2:
            return f"fullText contains '{term}'"
    return ""


def _extract_search_topic(text: str) -> str | None:
    """Extract the main search topic from a 'find X and save' style query."""
    patterns = [
        r"find\s+(?:top\s+\d+\s+)?(.+?)(?:\s+and\s+save|\s+and\s+write|\s+and\s+store|\s+and\s+export|$)",
        r"search\s+(?:for\s+)?(.+?)(?:\s+and\s+save|\s+and\s+write|\s+and\s+store|$)",
        r"top\s+\d+\s+(.+?)(?:\s+and\s+save|\s+and\s+write|\s+and\s+store|$)",
        r"best\s+(.+?)(?:\s+and\s+save|\s+and\s+write|\s+and\s+store|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            topic = match.group(1).strip(" .")
            # Strip trailing workspace service keywords
            topic = re.sub(
                r"\s+(to\s+(google\s+)?(docs|sheets|documents|document|spreadsheet).*|and\s+(save|write|store).*)$",
                "",
                topic,
                flags=re.IGNORECASE,
            ).strip()
            if len(topic) > 2:
                return topic
    return None


def _is_web_search_and_save(text: str) -> bool:
    """Return True if the query is a 'find/search X and save to Workspace' intent."""
    has_search = any(trigger in text for trigger in _WEB_SEARCH_TRIGGERS)
    has_save = _has_any(text, ("save", "write", "store", "export", "document", "doc", "sheet", "spreadsheet"))
    return has_search and has_save


def _spreadsheet_title_from_query(query: str) -> str:
    suffix = query.replace(" OR ", " ").strip() or "Gmail"
    return f"{suffix.title()} Search Results"


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
