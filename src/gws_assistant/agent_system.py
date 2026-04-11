"""CrewAI-backed planning for natural-language Workspace requests."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from .models import AppConfigModel, PlannedTask, RequestPlan
from .service_catalog import SERVICES, normalize_service

os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")

try:  # pragma: no cover - exercised only when crewai is installed and configured
    from crewai import Agent, Crew, LLM, Process, Task as CrewTask
except Exception:  # pragma: no cover
    Agent = None  # type: ignore[assignment]
    Crew = None  # type: ignore[assignment]
    CrewTask = None  # type: ignore[assignment]
    LLM = None  # type: ignore[assignment]
    Process = None  # type: ignore[assignment]


NO_SERVICE_MESSAGE = "No Google Workspace service detected in your request."


class WorkspaceAgentSystem:
    """Plans one or more gws tasks from a natural-language request."""

    def __init__(self, config: AppConfigModel, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self._crew = self._build_crew()

    def plan(self, user_text: str) -> RequestPlan:
        text = (user_text or "").strip()
        if not text:
            return RequestPlan(
                raw_text=user_text,
                summary=NO_SERVICE_MESSAGE,
                no_service_detected=True,
            )

        if self._crew is not None:
            plan = self._plan_with_crewai(text)
            if plan and plan.tasks:
                return plan
            if plan and plan.no_service_detected:
                return plan

        return self._plan_with_heuristics(text)

    def _build_crew(self) -> Any | None:
        if not self.config.api_key:
            self.logger.warning("CrewAI planning disabled because no API key is configured.")
            return None
        if not all((Agent, Crew, CrewTask, LLM, Process)):
            self.logger.warning("CrewAI is not installed, using heuristic planning.")
            return None
        try:
            llm_kwargs: dict[str, Any] = {
                "model": self._crewai_model_name(),
                "api_key": self.config.api_key,
                "temperature": 0,
                "timeout": self.config.timeout_seconds,
            }
            if self.config.base_url:
                llm_kwargs["base_url"] = self.config.base_url
            llm = LLM(**llm_kwargs)
            planner = Agent(
                role="Google Workspace command planner",
                goal="Turn user requests into ordered, executable Google Workspace CLI task plans.",
                backstory=(
                    "You understand Gmail, Drive, Sheets, Calendar, Docs, Slides, and Contacts. "
                    "You produce conservative plans that only use actions from the provided catalog."
                ),
                llm=llm,
                verbose=False,
            )
            planning_task = CrewTask(
                description=(
                    "Plan the Google Workspace CLI work for this user request: {request}\n\n"
                    f"Available action catalog:\n{self._catalog_for_prompt()}\n\n"
                    "Return JSON only. Use this schema:\n"
                    "{\"summary\": \"short human summary\", \"confidence\": 0.0, "
                    "\"no_service_detected\": false, "
                    "\"tasks\": [{\"id\": \"task-1\", \"service\": \"gmail\", "
                    "\"action\": \"list_messages\", \"parameters\": {}, \"reason\": \"why\"}]}\n"
                    f"If no supported service is present, return no_service_detected=true, "
                    f"summary=\"{NO_SERVICE_MESSAGE}\", and tasks=[]. "
                    "For a request like finding Gmail items and saving to Sheets, plan Gmail first, "
                    "then Sheets create_spreadsheet if no spreadsheet ID is supplied, then Sheets append_values. "
                    "Do not invent placeholders like message_id_from_task_1 enclosed in braces. "
                    "If Gmail messages must be fetched after list_messages, set get_message.parameters.message_id "
                    "to \"$gmail_message_ids\" and the executor will expand it. "
                    "For Sheets append_values, only use supported placeholders: "
                    "$last_spreadsheet_id for spreadsheet_id and $gmail_summary_values for values. "
                    "For sending spreadsheet data via Gmail, use sheets.get_values first, then gmail.send_message "
                    "with body set to $sheet_email_body."
                ),
                expected_output="A valid JSON request plan using only the allowed service/action catalog.",
                agent=planner,
            )
            return Crew(agents=[planner], tasks=[planning_task], process=Process.sequential, verbose=False, tracing=False)
        except Exception as exc:
            self.logger.warning("CrewAI initialization failed, using heuristic planning: %s", exc)
            return None

    def _plan_with_crewai(self, text: str) -> RequestPlan | None:
        try:
            result = self._crew.kickoff(inputs={"request": text})
            payload = _json_from_text(str(result))
            return self._plan_from_payload(text, payload, source="crewai")
        except Exception as exc:
            self.logger.warning("CrewAI planning failed, using heuristic planning: %s", exc)
            self._crew = None
            return None

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
        if not services:
            return RequestPlan(
                raw_text=text,
                summary=NO_SERVICE_MESSAGE,
                confidence=0.2,
                no_service_detected=True,
            )

        if "gmail" in services and "sheets" in services and _is_sheet_to_email_request(lowered):
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
        elif service == "contacts" and action == "list_contacts":
            parameters["page_size"] = _first_int(lowered) or 10
        return PlannedTask(
            id=f"task-{index}",
            service=service,
            action=action,
            parameters=parameters,
            reason=f"Detected {SERVICES[service].label} in the request.",
        )

    def _crewai_model_name(self) -> str:
        if self.config.provider == "openrouter" and not self.config.model.startswith("openrouter/"):
            return f"openrouter/{self.config.model}"
        if self.config.provider == "openai" and "/" not in self.config.model:
            return f"openai/{self.config.model}"
        return self.config.model

    @staticmethod
    def _catalog_for_prompt() -> str:
        catalog = {}
        for service, spec in SERVICES.items():
            catalog[service] = {
                "aliases": spec.aliases,
                "actions": {
                    action: [parameter.name for parameter in action_spec.parameters]
                    for action, action_spec in spec.actions.items()
                },
            }
        return json.dumps(catalog, ensure_ascii=True, indent=2)


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


def _json_from_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end >= start:
        cleaned = cleaned[start : end + 1]
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("CrewAI returned JSON that was not an object.")
    return payload
