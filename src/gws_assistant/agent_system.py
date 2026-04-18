"""CrewAI-backed planning for natural-language Workspace requests."""

from __future__ import annotations

import logging
import re
from typing import Any

from .langchain_agent import plan_with_langchain
from .models import AppConfigModel, PlannedTask, RequestPlan
from .service_catalog import SERVICES

NO_SERVICE_MESSAGE = "No Google Workspace service detected in your request."


class WorkspaceAgentSystem:
    """Plans one or more gws tasks from a natural-language request."""

    def __init__(self, config: AppConfigModel, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self._use_langchain = bool(self.config.langchain_enabled and self.config.api_key)
        from .memory import LongTermMemory
        self.memory = LongTermMemory(config, logger)

    def plan(self, user_text: str) -> RequestPlan:
        from .intent_parser import IntentParser
        from .memory import recall_similar

        # Local episodic memory
        past = recall_similar(user_text)
        
        # Long-term semantic memory (Mem0)
        semantic_memories = self.memory.search(user_text)
        
        memory_hint_parts = []
        if past:
            self.logger.info("Local Memory: found %d similar past episodes", len(past))
            memory_hint_parts.append("Recent similar interactions:\n" + "\n".join(
                f"- Goal: '{ep['goal'][:80]}' -> Outcome: {ep['outcome']}"
                for ep in past[:3]
            ))
            
        if semantic_memories:
            # Handle dictionary response from Mem0 v2
            if isinstance(semantic_memories, dict):
                memories_list = semantic_memories.get("results", [])
            else:
                memories_list = semantic_memories

            self.logger.info("Semantic Memory: found %d relevant memories", len(memories_list))
            # Mem0 search results are usually list of dicts with 'memory' or 'text' key
            memory_hint_parts.append("Known facts and preferences:\n" + "\n".join(
                f"- {m.get('memory', m.get('text', str(m)))}"
                for m in memories_list[:5]
            ))

        memory_hint = "\n\n".join(memory_hint_parts)

        text = (user_text or "").strip()
        if not text:
            return RequestPlan(
                raw_text=user_text,
                summary=NO_SERVICE_MESSAGE,
                no_service_detected=True,
            )

        # 1. Check for direct command override (e.g. service action key=value or starting with service key)
        # If the user provides explicit parameters or starts with a service name, prioritize heuristics.
        # service_prefixes = ("web_search", "drive", "gmail", "sheets", "docs", "calendar", "keep", "meet", "code", "computation", "telegram")
        # lowered = text.lower()
        # is_direct = any(lowered.startswith(p) for p in service_prefixes) or "=" in text or ":" in text
        # 
        # if is_direct:
        #     parser = IntentParser(self.config, self.logger)
        #     intent = parser.parse(text, force_heuristic=True)
        #     if intent.service and intent.action and not intent.needs_clarification:
        #         task = PlannedTask(
        #             id="task-1",
        #             service=intent.service,
        #             action=intent.action,
        #             parameters=intent.parameters,
        #             reason=f"Direct command detected: {intent.service}.{intent.action}",
        #         )
        #         return RequestPlan(
        #             raw_text=text,
        #             tasks=[task],
        #             summary=f"Planned direct task: {intent.service}.{intent.action}",
        #             confidence=1.0,
        #             no_service_detected=False,
        #             source="direct_command",
        #         )

        # 2. Primary: LLM Planning
        if self._use_langchain:
            plan = plan_with_langchain(text, self.config, self.logger,
                                         memory_hint=memory_hint)
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

        # 3. Heuristic Fallback
        return self._plan_with_heuristics(text)

    def _plan_with_heuristics(self, text: str) -> RequestPlan:
        lowered = text.lower()
        services = _detect_services_in_order(lowered)
        self.logger.info(f"Heuristic planning: detected services {services}")

        if not services:
            return RequestPlan(
                raw_text=text,
                summary=NO_SERVICE_MESSAGE,
                confidence=0.2,
                no_service_detected=True,
            )

        # MULTI-TASK HEURISTICS (General Patterns)
        
        # Pattern A: Drive -> Gmail (Search & Email)
        if "drive" in services and "gmail" in services and _is_drive_to_email_request(lowered):
             tasks = self._drive_to_gmail_tasks(text, lowered)
             return RequestPlan(
                raw_text=text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: drive.list_files -> drive.export_file -> gmail.send_message",
                confidence=0.7,
                no_service_detected=False,
                source="heuristic",
            )
            
        # Pattern B: Gmail -> Sheets -> Email (Extraction)
        if "gmail" in services and "sheets" in services and _is_sheet_to_email_request(lowered):
             tasks = self._gmail_to_sheets_tasks(text, lowered)
             return RequestPlan(
                raw_text=text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: gmail.list_messages -> sheets.create_spreadsheet -> sheets.append_values -> gmail.send_message",
                confidence=0.7,
                no_service_detected=False,
                source="heuristic",
            )

        # Pattern C: Drive Folder & Move
        if "drive" in services and _is_drive_folder_move_request(lowered):
             tasks = self._drive_folder_move_tasks(text, lowered)
             return RequestPlan(
                raw_text=text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: drive.create_folder -> drive.list_files -> drive.move_file",
                confidence=0.7,
                no_service_detected=False,
                source="heuristic",
            )

        # Pattern D: Sheet Creation & Data
        if "sheets" in services and _is_sheet_creation_request(lowered):
             tasks = self._sheets_creation_tasks(text, lowered)
             return RequestPlan(
                raw_text=text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: sheets.create_spreadsheet -> sheets.append_values -> sheets.get_values -> code.execute",
                confidence=0.8,
                no_service_detected=False,
                source="heuristic",
            )

        # Pattern E: Document Conversion (Docs/Sheets)
        if "docs" in services and "sheets" in services:
             # Add general doc to sheet conversion if needed
             pass

        # Final Fallback: Single Task per Service
        tasks = [self._single_service_task(service, text, index) for index, service in enumerate(services, start=1)]

        return RequestPlan(
            raw_text=text,
            tasks=tasks,
            summary=f"Planned {len(tasks)} task{'s' if len(tasks) != 1 else ''}: "
            + ", ".join(f"{task.service}.{task.action}" for task in tasks),
            confidence=0.4,
            no_service_detected=False,
        )

    def _drive_to_gmail_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        query = _drive_query_from_text(text)
        recipient = _extract_email(text) or self.config.default_recipient_email
        
        send_params: dict[str, Any] = {
            "to_email": recipient,
            "subject": f"Document: {query}",
            "body": "Hi,\n\nPlease find the content below:\n\n$last_export_file_content"
        }
        
        if "attach" in lowered:
            send_params["attachments"] = ["{{task-1.id}}"]

        return [
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
                parameters={"file_id": "{{task-1.id}}", "mime_type": "text/plain"},
                reason="Extract content for the email."
            ),
            PlannedTask(
                id="task-3",
                service="gmail",
                action="send_message",
                parameters=send_params,
                reason="Email the extracted content."
            )
        ]

    def _gmail_to_sheets_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        query = _gmail_query_from_text(text)
        recipient = _extract_email(text) or self.config.default_recipient_email
        return [
            PlannedTask(
                id="task-1",
                service="gmail",
                action="list_messages",
                parameters={"q": query, "max_results": 10},
                reason="Search Gmail messages."
            ),
            PlannedTask(
                id="task-2",
                service="gmail",
                action="get_message",
                parameters={"message_id": "$gmail_message_ids"},
                reason="Fetch full message details."
            ),
            PlannedTask(
                id="task-3",
                service="sheets",
                action="create_spreadsheet",
                parameters={"title": f"Results: {query}"},
                reason="Create spreadsheet for results."
            ),
            PlannedTask(
                id="task-4",
                service="sheets",
                action="append_values",
                parameters={
                    "spreadsheet_id": "$last_spreadsheet_id",
                    "range": "Sheet1!A1",
                    "values": "$gmail_details_values"
                },
                reason="Save detailed results to Sheets."
            ),
            PlannedTask(
                id="task-5",
                service="gmail",
                action="send_message",
                parameters={
                    "to_email": recipient,
                    "subject": f"Processed: {query}",
                    "body": "Hi,\n\nPlease find the spreadsheet here: $last_spreadsheet_url"
                },
                reason="Email the final spreadsheet link."
            )
        ]

    def _drive_folder_move_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        query = _drive_query_from_text(text)
        folder_name = _extract_quoted(text) or "Organized Files"
        recipient = _extract_email(text) or self.config.default_recipient_email
        
        return [
            PlannedTask(
                id="task-1",
                service="drive",
                action="create_folder",
                parameters={"folder_name": folder_name},
                reason=f"Create folder '{folder_name}'."
            ),
            PlannedTask(
                id="task-2",
                service="drive",
                action="list_files",
                parameters={"q": query, "page_size": 20},
                reason=f"List files to move."
            ),
            PlannedTask(
                id="task-3",
                service="drive",
                action="move_file",
                parameters={"file_id": "$drive_file_ids", "folder_id": "{{task-1.id}}"},
                reason="Move files into the folder."
            ),
            PlannedTask(
                id="task-4",
                service="gmail",
                action="send_message",
                parameters={
                    "to_email": recipient,
                    "subject": "Drive Files Organized",
                    "body": f"Hi,\n\nFiles moved to '{folder_name}'. Link: $last_folder_url"
                },
                reason="Notify user."
            )
        ]

    def _sheets_creation_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        title = _extract_quoted(text) or "New Spreadsheet"
        return [
            PlannedTask(
                id="task-1",
                service="sheets",
                action="create_spreadsheet",
                parameters={"title": title},
                reason=f"Create spreadsheet '{title}'."
            ),
            PlannedTask(
                id="task-2",
                service="sheets",
                action="append_values",
                parameters={
                    "spreadsheet_id": "{{task-1.id}}",
                    "values": _extract_data_rows(text)
                },
                reason="Add data rows to the sheet."
            )
        ]

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
            else:
                # Fallback: try to find anything in quotes or after search/find
                query = _extract_quoted(lowered)
                if query:
                    parameters["q"] = f"name contains '{query}'"
        elif service == "drive" and action == "export_file":
            parameters["file_id"] = _extract_id(lowered) or "{{task-1.id}}"
        elif service == "search" and action == "web_search":
            parameters["query"] = lowered
        elif service == "docs" and action == "get_document":
            parameters["document_id"] = _extract_id(lowered) or "{{task-1.id}}"
        elif service == "sheets" and action == "get_values":
            parameters["spreadsheet_id"] = _extract_id(lowered) or "{{task-1.id}}"
            parameters["range"] = "Sheet1!A1"
        elif service == "gmail" and action == "send_message":
            parameters["to_email"] = _extract_email(lowered) or self.config.default_recipient_email
            parameters["subject"] = "GWorkspace Notification"
            parameters["body"] = f"Update regarding your request: {lowered[:100]}..."
        elif service in ("code", "computation"):
            list_match = re.search(r"(\[.+?\])", lowered)
            data_str = list_match.group(1) if list_match else "[]"
            if "sort" in lowered:
                rev = "True" if any(kw in lowered for kw in ("expensive", "descending", "reverse")) else "False"
                parameters["code"] = f"data = {data_str}\nresult = sorted(data, reverse={rev})\nprint(result)"
            else:
                # Try to generate generic processing code for "convert to table" etc
                parameters["code"] = f"# Processed data from previous steps\nprint('Processing task: {lowered}')"

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
        for term in terms:
            pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
            match = pattern.search(text)
            if match:
                hits.append((match.start(), service_key))
                break
    
    found_services = [service for _, service in sorted(hits, key=lambda item: item[0])]
    
    # Priority Fix: If we detected both a workspace service and generic 'search',
    # and they are at the same position or search is just a keyword, prioritize the workspace service.
    if "search" in found_services and len(found_services) > 1:
        # If any other service exists, we likely want that service's search, not web search
        found_services = [s for s in found_services if s != "search"]
        
    return found_services


def _detect_action(service: str, text: str) -> str | None:
    best_action = None
    best_score = 0
    lowered = text.lower()
    
    for action_key, action_spec in SERVICES[service].actions.items():
        # Check negative keywords first - if any exist, this action is disqualified
        neg_hit = False
        if hasattr(action_spec, "negative_keywords") and action_spec.negative_keywords:
            for nk in action_spec.negative_keywords:
                if nk in lowered:
                    neg_hit = True
                    break
        if neg_hit:
            continue

        score = sum(1 for keyword in action_spec.keywords if keyword in lowered)
        if score > best_score:
            best_score = score
            best_action = action_key
            
    return best_action


def _gmail_query_from_text(text: str) -> str:
    quoted = re.search(r'[\"\']([^\"\']{3,80})[\"\'\']', text)
    if quoted: return f'subject:"{quoted.group(1).strip()}"'
    match = re.search(r"(?:about|for|matching|with|named|search|find)\s+([a-z0-9 _.-]{3,60})", text, re.IGNORECASE)
    if match:
        query = match.group(1).strip()
        query = re.split(r"\s+(and|then|to|save|write|export|extract|move)\s+", query, flags=re.IGNORECASE)[0].strip()
        return query
    return ""


def _drive_query_from_text(text: str) -> str:
    quoted = re.search(r'[\"\']([^\"\']{3,80})[\"\'\']', text)
    if quoted: return f"fullText contains '{quoted.group(1).strip()}'"
    match = re.search(r"(?:about|for|matching|with|named|search|find)\s+([a-z0-9 _.-]{3,60})", text, re.IGNORECASE)
    if match:
        query = match.group(1).strip()
        query = re.split(r"\s+(and|then|to|save|write|export|extract|move)\s+", query, flags=re.IGNORECASE)[0].strip()
        return f"fullText contains '{query}'"
    return ""


def _extract_id(text: str) -> str | None:
    """Extract a Google Workspace ID (alphanumeric string with underscores/dashes) from text."""
    # Look for common ID pattern: ~44 characters, alphanumeric, includes - and _
    # Often found after 'ID:', 'id ', or in quotes.
    match = re.search(r"\b([a-zA-Z0-9_-]{25,})\b", text)
    return match.group(1) if match else None


def _extract_email(text: str) -> str | None:
    match = re.search(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b", text)
    return match.group(1) if match else None


def _extract_quoted(text: str) -> str | None:
    match = re.search(r"['\"](.+?)['\"]", text)
    return match.group(1) if match else None


def _first_int(text: str) -> int | None:
    match = re.search(r"\b(\d{1,3})\b", text)
    if match:
        val = int(match.group(1))
        return val if val > 0 else None
    return None


def _is_drive_to_email_request(text: str) -> bool:
    return any(t in text for t in ("drive", "file", "document")) and any(t in text for t in ("email", "send", "mail"))


def _is_sheet_to_email_request(text: str) -> bool:
    return "sheet" in text and any(t in text for t in ("email", "send", "mail"))


def _is_drive_folder_move_request(text: str) -> bool:
    return any(t in text for t in ("drive", "file")) and any(t in text for t in ("move", "folder", "organize"))


def _is_sheet_creation_request(text: str) -> bool:
    return "sheet" in text and any(t in text for t in ("create", "add", "new"))


def _extract_data_rows(text: str) -> list[list[Any]]:
    """Extract rows from text like 'Score1, 100' or similar csv-like patterns."""
    rows = []
    # Look for header and data rows in quotes
    matches = re.findall(r"['\"](.+?)['\"]", text)
    for m in matches:
        if "," in m:
            rows.append([item.strip() for item in m.split(",")])
    
    # If no rows found in quotes, try to find patterns like 'Score1, 100'
    if not rows:
         pattern = re.compile(r"([A-Za-z0-9 _]+)\s*,\s*(\d+)")
         for m in pattern.finditer(text):
             rows.append([m.group(1).strip(), m.group(2).strip()])
             
    return rows if rows else [["Data", "Value"], ["Item1", "10"]]
