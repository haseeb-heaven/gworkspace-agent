"""CrewAI-backed planning for natural-language Workspace requests."""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

from .langchain_agent import plan_with_langchain
from .models import AppConfigModel, PlannedTask, RequestPlan
from .service_catalog import SERVICES

RE_CODE_LIST = re.compile(r"(\[.+?\])")
RE_GMAIL_QUERY_QUOTED = re.compile(r'["\']([^"\']{3,80})["\']')
RE_GMAIL_QUERY_MATCH = re.compile(
    r"(?:about|for|matching|with|named|search|find|search gmail for)\s+([a-z0-9 _.-]{3,60})", re.IGNORECASE
)
RE_GMAIL_QUERY_SPLIT = re.compile(r"\s+(and|then|to|save|write|export|extract|move)\s+", re.IGNORECASE)
RE_DRIVE_QUERY_QUOTED = re.compile(r'["\']([^"\']{3,80})["\']')
RE_DRIVE_QUERY_MATCH = re.compile(
    r"(?:about|for|matching|with|named|search|find)\s+([a-z0-9 _.-]{3,60})", re.IGNORECASE
)
RE_DRIVE_QUERY_SPLIT = re.compile(r"\s+(and|then|to|save|write|export|extract|move)\s+", re.IGNORECASE)
RE_EXTRACT_ID = re.compile(r"\b([a-zA-Z0-9_-]{25,})\b")
RE_EXTRACT_EMAIL = re.compile(r"\b([A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\s*\.\s*[A-Za-z]{2,})\b")
RE_EXTRACT_QUOTED = re.compile(r'["\'](.+?)["\']')
RE_FIRST_INT = re.compile(r"\b(\d{1,3})\b")
RE_EXTRACT_DATA_ROWS = re.compile(r"['\"](.+?)['\"]")
RE_EXTRACT_DATA_PATTERN = re.compile(r"([A-Za-z0-9 _]+)\s*,\s*(\d+)")

NO_SERVICE_MESSAGE = "No Google Workspace service detected in your request."

# Phrases that strongly indicate the user wants a *web* search rather than a
# Drive / Gmail / Sheets lookup. Used to decide whether to keep the ``search``
# pseudo-service when other Workspace services are also detected.
_WEB_SEARCH_INTENT_PHRASES: tuple[str, ...] = (
    "search the web",
    "search web",
    "web search",
    "search online",
    "search the internet",
    "search internet",
    "search google for",
    "google for ",
    "look it up online",
    "look up online",
    "find online",
    "find on the web",
    "browse the web",
    "from the web",
    "from the internet",
    "on the internet",
    "scrape",
)


def _has_explicit_web_search_intent(text: str) -> bool:
    """Return ``True`` when *text* contains an explicit web-search phrase.

    The check is case-insensitive and tolerant of surrounding whitespace; it
    is intentionally narrow so that incidental uses of the verb "search"
    against a Workspace service (``"search drive for X"``) are *not* treated
    as web-search intent.
    """
    if not text:
        return False
    lowered = text.lower()
    return any(
        re.search(r"\b" + re.escape(phrase) + r"\b", lowered) for phrase in _WEB_SEARCH_INTENT_PHRASES
    )


class WorkspaceAgentSystem:
    """Plans one or more gws tasks from a natural-language request."""

    def __init__(self, config: AppConfigModel, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self._use_langchain = bool(self.config.langchain_enabled and self.config.api_key)
        self.logger.debug("agent_system initialized (langchain_enabled=%s)", self._use_langchain)
        from .memory_backend import get_memory_backend

        self.memory = get_memory_backend(config, logger)

    def summarize(self, text: str) -> str:
        """Summarize text using the configured LLM."""
        if not text or not self._use_langchain:
            return text

        try:
            from .langchain_agent import create_agent

            model = create_agent(self.config, self.logger)
            if not model:
                return text

            prompt = (
                "Summarize the following information into a concise, well-structured, and informative summary. "
                "Focus on the key facts, dates, and changes. Do NOT include raw snippets like dates prefixing the text (e.g. 'Jan 1, 2024 ...'). "
                "Use bullet points for lists. Output ONLY the summary.\n\n"
                f"Information to summarize:\n{text}"
            )
            response = model.invoke(prompt)
            return getattr(response, "content", str(response)).strip()
        except Exception as exc:
            self.logger.warning("Summarization failed: %s", exc)
            return text

    def plan(self, user_text: str) -> RequestPlan:
        from .memory import recall_similar

        # Local episodic memory
        past = recall_similar(user_text)

        # Long-term semantic memory (Mem0)
        semantic_memories = self.memory.search(user_text)

        memory_hint_parts = []
        if past:
            self.logger.info("Local Memory: found %d similar past episodes", len(past))
            interactions = "\n".join([f"- Goal: '{ep['goal'][:80]}' -> Outcome: {ep['outcome']}" for ep in past[:5]])
            memory_hint_parts.append(f"Recent similar interactions:\n{interactions}")

        if semantic_memories:
            # Handle dictionary response from Mem0 v2
            if isinstance(semantic_memories, dict):
                memories_list = semantic_memories.get("results", [])
            else:
                memories_list = semantic_memories

            if memories_list:
                self.logger.info("Semantic Memory: found %d relevant memories", len(memories_list))
                # Mem0 search results are usually list of dicts with 'memory' or 'text' key
                facts = "\n".join([f"- {m.get('memory', m.get('text', str(m)))}" for m in memories_list[:5]])
                memory_hint_parts.append(f"Known facts and preferences:\n{facts}")

        memory_hint = ""
        for part in memory_hint_parts:
            memory_hint += part + "\n\n"

        text = (user_text or "").strip()
        if not text:
            return RequestPlan(
                raw_text=user_text,
                summary=NO_SERVICE_MESSAGE,
                no_service_detected=True,
            )

        # 2. Primary: LLM Planning
        if self._use_langchain:
            plan = plan_with_langchain(text, self.config, self.logger, memory_hint=memory_hint)
            if plan and plan.tasks:
                from .safety_guard import SafetyGuard

                SafetyGuard.check_plan(plan, force_dangerous=self.config.force_dangerous)
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
        plan = self._plan_with_heuristics(text)
        if plan and plan.tasks:
            from .safety_guard import SafetyGuard

            SafetyGuard.check_plan(plan, force_dangerous=self.config.force_dangerous)
        return plan

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

        # Pattern WS-*: Web Search-driven workflows.
        # These run BEFORE the gmail-/drive-led patterns so that requests like
        # "Search the web for X, save to Sheet, send email" do not get routed
        # to gmail.list_messages or drive.list_files.
        if "search" in services and _has_explicit_web_search_intent(lowered):
            ws_plan = self._web_search_pattern_tasks(text, lowered, services)
            if ws_plan is not None:
                tasks, summary_chain = ws_plan
                return RequestPlan(
                    raw_text=text,
                    tasks=tasks,
                    summary=f"Planned {len(tasks)} tasks: {summary_chain}",
                    confidence=0.85,
                    no_service_detected=False,
                    source="heuristic",
                )

        # Pattern B: Gmail -> Sheets -> Email (Extraction)
        if "gmail" in services and "sheets" in services and _is_gmail_to_sheets_request(lowered):
            tasks = self._gmail_to_sheets_tasks(text, lowered)
            return RequestPlan(
                raw_text=text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: gmail.list_messages -> sheets.create_spreadsheet -> sheets.append_values -> gmail.send_message",
                confidence=0.7,
                no_service_detected=False,
                source="heuristic",
            )

        # Pattern A1: Drive Metadata Only (e.g. counts, tables, summaries)
        if (
            "drive" in services
            and _is_metadata_only_request(lowered)
            and not ("gmail" in services and _is_drive_to_email_request(lowered))
            and not _is_drive_folder_move_request(lowered)
        ):
            tasks = self._drive_metadata_computation_tasks(text, lowered)
            task_chain = " -> ".join(f"{t.service}.{t.action}" for t in tasks)
            return RequestPlan(
                raw_text=text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: {task_chain}",
                confidence=0.75,
                no_service_detected=False,
                source="heuristic",
            )

        # Pattern A-Metadata: Drive Metadata -> Code -> Gmail
        if "drive" in services and "gmail" in services and _is_drive_metadata_to_email_request(lowered):
            tasks = self._drive_metadata_to_gmail_tasks(text, lowered)
            task_chain = " -> ".join(f"{t.service}.{t.action}" for t in tasks)
            return RequestPlan(
                raw_text=text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: {task_chain}",
                confidence=0.8,
                no_service_detected=False,
                source="heuristic",
            )

        # Pattern A: Drive -> Gmail (Search & Email)
        if "drive" in services and "gmail" in services and _is_drive_to_email_request(lowered):
            tasks = self._drive_to_gmail_tasks(text, lowered)
            task_chain = " -> ".join(f"{t.service}.{t.action}" for t in tasks)
            return RequestPlan(
                raw_text=text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: {task_chain}",
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

        # Pattern F: Gmail List & Get (Always fetch details for searches)
        if (
            len(services) == 1
            and services[0] == "gmail"
            and any(kw in lowered for kw in ("list", "search", "find", "show"))
        ):
            tasks = self._gmail_list_and_get_tasks(text, lowered)
            return RequestPlan(
                raw_text=text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: gmail.list_messages -> gmail.get_message",
                confidence=0.8,
                no_service_detected=False,
                source="heuristic",
            )

        # Pattern G: Sheet -> Email
        if "sheets" in services and "gmail" in services and _is_sheet_to_email_request(lowered):
            tasks = self._sheet_to_email_tasks(text, lowered)
            return RequestPlan(
                raw_text=text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: sheets.get_values -> gmail.send_message",
                confidence=0.8,
                no_service_detected=False,
                source="heuristic",
            )

        # Pattern H: Docs -> Email
        if "docs" in services and "gmail" in services and _is_docs_to_email_request(lowered):
            tasks = self._docs_to_email_tasks(text, lowered)
            return RequestPlan(
                raw_text=text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: docs.create_document -> docs.get_document -> gmail.send_message",
                confidence=0.8,
                no_service_detected=False,
                source="heuristic",
            )

        # Pattern I: Forms Sync
        if "forms" in services and _is_forms_sync_request(lowered):
            tasks = self._forms_sync_tasks(text, lowered)
            return RequestPlan(
                raw_text=text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: forms.create_form -> forms.batch_update",
                confidence=0.8,
                no_service_detected=False,
                source="heuristic",
            )

        # Pattern L: Explicit Code Execution / Computation
        if "code" in services or "computation" in services:
            if any(kw in lowered for kw in ("calculate", "compute", "prime", "sum", "script", "python")):
                tasks = [
                    PlannedTask(
                        id="task-1",
                        service="code",
                        action="execute",
                        parameters={"code": text},
                        reason="Direct computation request."
                    )
                ]
                if "email" in lowered or "send" in lowered:
                    recipient = _extract_email(text) or self.config.default_recipient_email
                    tasks.append(
                        PlannedTask(
                            id="task-2",
                            service="gmail",
                            action="send_message",
                            parameters={
                                "to_email": recipient,
                                "subject": "Computation Results",
                                "body": "Here are the results of the computation:\n\n{{task-1.stdout}}",
                            },
                            reason="Email the computation results."
                        )
                    )
                return RequestPlan(
                    raw_text=text,
                    tasks=tasks,
                    summary=f"Planned {len(tasks)} tasks: code.execute" + (" -> gmail.send_message" if len(tasks) > 1 else ""),
                    confidence=0.8,
                    no_service_detected=False,
                    source="heuristic",
                )

        # Pattern J: Slides -> Email
        if "slides" in services and "gmail" in services and _is_slides_to_email_request(lowered):
            tasks = self._slides_to_email_tasks(text, lowered)
            return RequestPlan(
                raw_text=text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: slides.get_presentation -> gmail.send_message",
                confidence=0.8,
                no_service_detected=False,
                source="heuristic",
            )

        # Pattern K: Admin -> Email
        if "admin" in services and "gmail" in services and any(kw in lowered for kw in ("reports", "activities", "logs", "audit")):
            tasks = self._admin_to_email_tasks(text, lowered)
            return RequestPlan(
                raw_text=text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: admin.list_activities -> gmail.send_message",
                confidence=0.8,
                no_service_detected=False,
                source="heuristic",
            )

        # Pattern L: Contacts -> Email
        if "contacts" in services and "gmail" in services and any(kw in lowered for kw in ("contacts", "people", "users", "directory", "members")):
            tasks = self._contacts_to_email_tasks(text, lowered)
            return RequestPlan(
                raw_text=text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: contacts.list_directory_people -> gmail.send_message",
                confidence=0.8,
                no_service_detected=False,
                source="heuristic",
            )

        # Pattern M: Chat -> Email (skip when user explicitly wants to send a chat message)
        _send_kw = ("send a message", "post a message", "send message", "post message")
        _has_send_intent = any(kw in lowered for kw in _send_kw)
        if "chat" in services and "gmail" in services and any(kw in lowered for kw in ("spaces", "messages", "chat")) and not _has_send_intent:
            tasks = self._chat_to_email_tasks(text, lowered)
            return RequestPlan(
                raw_text=text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: chat.list_spaces -> gmail.send_message",
                confidence=0.8,
                no_service_detected=False,
                source="heuristic",
            )

        # Pattern N: Chat Send Message (Heuristic Search for Space)
        if "chat" in services and _has_send_intent and "spaces/" not in lowered:
            tasks = self._chat_send_message_tasks(text, lowered)
            return RequestPlan(
                raw_text=text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: chat.list_spaces -> chat.send_message",
                confidence=0.8,
                no_service_detected=False,
                source="heuristic",
            )

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

    def _drive_metadata_computation_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        query = _drive_query_from_text(text)

        # Determine the action required
        code_script = "print('Processing metadata:\\n' + str($drive_summary_values))"
        if "count" in lowered:
            code_script = "data = $drive_summary_values\nprint(f'Counted {len(data)} files matching the query.')"
        elif "table" in lowered or "summary" in lowered:
            code_script = "data = $drive_summary_values\nif len(data) == 0:\n    print('No files found.')\nelse:\n    print('Files Summary:')\n    for row in data:\n        print('- ' + str(row[0]) + ' (' + str(row[1]) + ')')"

        tasks = [
            PlannedTask(
                id="task-1",
                service="drive",
                action="list_files",
                parameters={"q": query, "page_size": 50},
                reason="Search for files to retrieve metadata.",
            ),
            PlannedTask(
                id="task-2",
                service="code",
                action="execute",
                parameters={"code": code_script},
                reason="Compute over metadata.",
            ),
        ]

        return tasks

    def _drive_to_gmail_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        query = _drive_query_from_text(text)
        recipient = _extract_email(text) or self.config.default_recipient_email

        exclusion_words = ("count", "table", "summary", "metadata", "no file content", "do not download", "names only")
        skip_export = any(word in lowered for word in exclusion_words)

        if skip_export:
            body_content = """Hi,

Here are the files found:

$drive_metadata_table"""
        else:
            body_content = """Hi,

Please find the content below:
$last_export_file_content"""

        send_params: dict[str, Any] = {"to_email": recipient, "subject": f"Document: {query}", "body": body_content}

        if "attach" in lowered:
            send_params["attachments"] = ["{{task-1.id}}"]

        tasks = [
            PlannedTask(
                id="task-1",
                service="drive",
                action="list_files",
                parameters={"q": query, "page_size": 50},
                reason="Search for the requested document.",
            )
        ]

        if not skip_export:
            tasks.append(
                PlannedTask(
                    id="task-2",
                    service="drive",
                    action="export_file",
                    parameters={"file_id": "{{task-1.id}}", "mime_type": "text/plain"},
                    reason="Extract content for the email.",
                )
            )

        tasks.append(
            PlannedTask(
                id=f"task-{len(tasks) + 1}",
                service="gmail",
                action="send_message",
                parameters=send_params,
                reason="Email the extracted content.",
            )
        )

        return tasks

    def _drive_metadata_to_gmail_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        """Drive metadata with explicit email intent: list files -> compute table -> send email."""
        query = _drive_query_from_text(text)
        recipient = _extract_email(text) or self.config.default_recipient_email
        page_size = _first_int(lowered) or 50

        code = (
            "files = {{task-1.files}}\n"
            "count = len(files)\n"
            'table = "Name | ID | MimeType\\n"\n'
            'table += "-" * 50 + "\\n"\n'
            "for f in files:\n"
            "    table += f\"{f.get('name', 'N/A')} | {f.get('id', 'N/A')} | {f.get('mimeType', 'N/A')}\\n\"\n"
            "\n"
            'summary = f"Total matching files: {count}\\n\\n{table}"\n'
            "print(summary)"
        )

        return [
            PlannedTask(
                id="task-1",
                service="drive",
                action="list_files",
                parameters={"q": query, "page_size": page_size},
                reason="Search for the requested document metadata.",
            ),
            PlannedTask(
                id="task-2",
                service="code",
                action="execute",
                parameters={"code": code},
                reason="Compute summary table from drive metadata.",
            ),
            PlannedTask(
                id="task-3",
                service="gmail",
                action="send_message",
                parameters={
                    "to_email": recipient,
                    "subject": f"Drive Metadata Summary: {query}",
                    "body": "Here is the summary you requested:\n\n{{task-2.stdout}}",
                },
                reason="Email the metadata summary table.",
            ),
        ]

    def _web_search_pattern_tasks(
        self,
        text: str,
        lowered: str,
        services: list[str],
    ) -> tuple[list[PlannedTask], str] | None:
        """Build a plan for "Search the web → ..." style requests.

        Returns ``None`` when the pattern doesn't apply (caller falls
        through to the next heuristic). Otherwise returns a tuple of
        ``(tasks, summary_chain)`` where *summary_chain* is the
        ``service.action -> ...`` string used in the plan summary.
        """
        wants_sheets = "sheets" in services or "sheet" in lowered or "spreadsheet" in lowered
        wants_docs = "docs" in services or any(
            kw in lowered for kw in ("create document", "create a doc", "google doc", "save to a document", "to a document")
        )
        wants_email = (
            "send_message" in lowered
            or any(kw in lowered for kw in (
                "send email", "send mail", "email to", "to email",
                "send detailed email", "send an email", "compose email",
                "email it", "email me", "email the", "email this", "email that",
                "mail it", "mail me", "mail the", "mail this", "mail that",
            ))
        )
        wants_code = "code" in services or "computation" in services or any(
            kw in lowered for kw in (
                "code executor",
                "code execution",
                "use code",
                "run a script",
                "run python",
                "compute ",
                "calculate ",
            )
        )

        # If the user does not actually want any downstream artefact, fall
        # through to the simple single-task path so the existing single-task
        # search heuristic can handle it.
        if not (wants_sheets or wants_docs or wants_email or wants_code):
            return None

        query = _web_search_query_from_text(text)
        recipient = _extract_email(text) or self.config.default_recipient_email
        sheet_title = _extract_sheet_title(text) or "Web Search Results"
        doc_title = _extract_doc_title(text) or "Web Search Notes"
        chain: list[str] = []
        tasks: list[PlannedTask] = []

        # Step 1: web search.
        tasks.append(
            PlannedTask(
                id="task-1",
                service="search",
                action="web_search",
                parameters={"query": query, "max_results": 5},
                reason="Run a web search for the requested information.",
            )
        )
        chain.append("search.web_search")

        # Step 2: optional code transform (sort/format/extract).
        if wants_code:
            code = (
                "rows = $search_summary_rows\n"
                "# rows is a list of [title, snippet, url] entries.\n"
                "result = rows\n"
            )
            tasks.append(
                PlannedTask(
                    id=f"task-{len(tasks) + 1}",
                    service="code",
                    action="execute",
                    parameters={"code": code},
                    reason="Process / sort the search results before saving.",
                )
            )
            chain.append("code.execute")

        # Step 3: persistence — Sheets and/or Docs.
        if wants_sheets:
            tasks.append(
                PlannedTask(
                    id=f"task-{len(tasks) + 1}",
                    service="sheets",
                    action="create_spreadsheet",
                    parameters={"title": sheet_title},
                    reason="Create a spreadsheet to hold the search results.",
                )
            )
            chain.append("sheets.create_spreadsheet")

            tasks.append(
                PlannedTask(
                    id=f"task-{len(tasks) + 1}",
                    service="sheets",
                    action="append_values",
                    parameters={
                        "spreadsheet_id": "$last_spreadsheet_id",
                        "range": "Sheet1!A1",
                        "values": "$last_code_result" if wants_code else "$search_summary_rows",
                    },
                    reason="Save the search results to the spreadsheet.",
                )
            )
            chain.append("sheets.append_values")

        if wants_docs:
            tasks.append(
                PlannedTask(
                    id=f"task-{len(tasks) + 1}",
                    service="docs",
                    action="create_document",
                    parameters={
                        "title": doc_title,
                        "content": "$last_code_result_table" if wants_code else "$search_summary_table",
                    },
                    reason="Save the search summary into a Google Doc.",
                )
            )
            chain.append("docs.create_document")

        # Step 4: optional email.
        if wants_email:
            subject = sheet_title if wants_sheets else (doc_title if wants_docs else "Web Search Results")
            _table_ref = "$last_code_result_table" if wants_code else "$search_summary_table"
            if wants_sheets:
                body = (
                    "Hi,\n\n"
                    "Please find the search results spreadsheet here: "
                    "$last_spreadsheet_url\n\n"
                    "Top results:\n" + _table_ref
                )
            elif wants_docs:
                body = (
                    "Hi,\n\n"
                    "Please find the search results document here: "
                    "$last_document_url\n\n"
                    "Top results:\n" + _table_ref
                )
            else:
                body = "Hi,\n\nHere are the top web search results:\n\n" + _table_ref

            tasks.append(
                PlannedTask(
                    id=f"task-{len(tasks) + 1}",
                    service="gmail",
                    action="send_message",
                    parameters={
                        "to_email": recipient,
                        "subject": subject,
                        "body": body,
                    },
                    reason="Email the search results to the requested recipient.",
                )
            )
            chain.append("gmail.send_message")

        return tasks, " -> ".join(chain)

    def _gmail_to_sheets_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        query = _gmail_query_from_text(text)
        recipient = _extract_email(text) or self.config.default_recipient_email
        return [
            PlannedTask(
                id="task-1",
                service="gmail",
                action="list_messages",
                parameters={"q": query, "max_results": 10},
                reason="Search Gmail messages.",
            ),
            PlannedTask(
                id="task-2",
                service="gmail",
                action="get_message",
                parameters={"message_id": "$gmail_message_ids"},
                reason="Fetch full message details.",
            ),
            PlannedTask(
                id="task-3",
                service="sheets",
                action="create_spreadsheet",
                parameters={"title": f"Results: {query}"},
                reason="Create spreadsheet for results.",
            ),
            PlannedTask(
                id="task-4",
                service="sheets",
                action="append_values",
                parameters={
                    "spreadsheet_id": "$last_spreadsheet_id",
                    "range": "Sheet1!A1",
                    "values": "$gmail_details_values",
                },
                reason="Save detailed results to Sheets.",
            ),
            PlannedTask(
                id="task-5",
                service="gmail",
                action="send_message",
                parameters={
                    "to_email": recipient,
                    "subject": f"Processed: {query}",
                    "body": """Hi,

Please find the spreadsheet here: $last_spreadsheet_url""",
                },
                reason="Email the final spreadsheet link.",
            ),
        ]

    def _sheet_to_email_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        s_id = _extract_id(text)
        recipient = _extract_email(text) or self.config.default_recipient_email

        tasks = []
        if not s_id:
            # Try to extract sheet name from quotes
            name = _extract_quoted(text)
            query = f"name = '{name}'" if name else "mimeType = 'application/vnd.google-apps.spreadsheet'"
            tasks.append(
                PlannedTask(
                    id="task-1",
                    service="drive",
                    action="list_files",
                    parameters={"q": query, "page_size": 1},
                    reason="Search for the spreadsheet ID.",
                )
            )
            s_id = "{{task-1.id}}"

        tasks.append(
            PlannedTask(
                id=f"task-{len(tasks) + 1}",
                service="sheets",
                action="get_values",
                parameters={"spreadsheet_id": s_id, "range": "Sheet1!A1:Z500"},
                reason="Read data from the spreadsheet.",
            )
        )
        tasks.append(
            PlannedTask(
                id=f"task-{len(tasks) + 1}",
                service="gmail",
                action="send_message",
                parameters={
                    "to_email": recipient,
                    "subject": "Spreadsheet Data",
                    "body": "Hi,\n\nPlease find the spreadsheet data below:\n\n$last_spreadsheet_values",
                },
                reason="Email the spreadsheet data.",
            )
        )
        return tasks

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
                reason=f"Create folder '{folder_name}'.",
            ),
            PlannedTask(
                id="task-2",
                service="drive",
                action="list_files",
                parameters={"q": query, "page_size": 20},
                reason="List files to move.",
            ),
            PlannedTask(
                id="task-3",
                service="drive",
                action="move_file",
                parameters={"file_id": "$drive_file_ids", "folder_id": "{{task-1.id}}"},
                reason="Move files into the folder.",
            ),
            PlannedTask(
                id="task-4",
                service="gmail",
                action="send_message",
                parameters={
                    "to_email": recipient,
                    "subject": "Drive Files Organized",
                    "body": f"""Hi,

Files moved to '{folder_name}'. Link: $last_folder_url""",
                },
                reason="Notify user.",
            ),
        ]

    def _sheets_creation_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        title = _extract_quoted(text) or "New Spreadsheet"
        tasks = [
            PlannedTask(
                id="task-1",
                service="sheets",
                action="create_spreadsheet",
                parameters={"title": title},
                reason=f"Create spreadsheet '{title}'.",
            )
        ]
        values = _extract_data_rows(text)
        if values:
            tasks.append(
                PlannedTask(
                    id="task-2",
                    service="sheets",
                    action="append_values",
                    parameters={"spreadsheet_id": "{{task-1.id}}", "values": values},
                    reason="Add data rows to the sheet.",
                )
            )
        return tasks

    def _admin_to_email_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        recipient = _extract_email(text) or self.config.default_recipient_email
        if not recipient:
            raise ValueError(
                "No recipient email found in _admin_to_email_tasks; cannot plan gmail.send_message with to_email=None. "
                "Please provide an email address or configure default_recipient_email."
            )
        _admin_keywords = ("admin", "audit", "reports", "logs", "login", "activities")
        app_name = "admin" if any(kw in lowered for kw in _admin_keywords) else "drive"
        return [
            PlannedTask(
                id="task-1",
                service="admin",
                action="list_activities",
                parameters={"application_name": app_name, "max_results": 5},
                reason="Fetch activity logs.",
            ),
            PlannedTask(
                id="task-2",
                service="gmail",
                action="send_message",
                parameters={
                    "to_email": recipient,
                    "subject": "Activity Report",
                    "body": f"Hi,\n\nPlease find the {app_name} activity report below:\n\n$last_admin_activities",
                },
                reason="Email the report.",
            ),
        ]

    def _contacts_to_email_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        recipient = _extract_email(text) or self.config.default_recipient_email
        if not recipient:
            raise ValueError(
                "No recipient email found in _contacts_to_email_tasks; cannot plan gmail.send_message with to_email=None. "
                "Please provide an email address or configure default_recipient_email."
            )
        action = "list_directory_people" if any(kw in lowered for kw in ("directory", "users", "members", "workspace")) else "list_contacts"
        return [
            PlannedTask(
                id="task-1",
                service="contacts",
                action=action,
                parameters={"page_size": 5},
                reason=f"Fetch {action}.",
            ),
            PlannedTask(
                id="task-2",
                service="gmail",
                action="send_message",
                parameters={
                    "to_email": recipient,
                    "subject": "Contacts/Users List",
                    "body": "Hi,\n\nPlease find the requested list below:\n\n$last_contacts_list",
                },
                reason="Email the list.",
            ),
        ]

    def _chat_to_email_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        recipient = _extract_email(text) or self.config.default_recipient_email
        if not recipient:
            raise ValueError(
                "No recipient email found in _chat_to_email_tasks; cannot plan gmail.send_message with to_email=None. "
                "Please provide an email address or configure default_recipient_email."
            )
        return [
            PlannedTask(
                id="task-1",
                service="chat",
                action="list_spaces",
                parameters={"page_size": 10},
                reason="List available chat spaces.",
            ),
            PlannedTask(
                id="task-2",
                service="gmail",
                action="send_message",
                parameters={
                    "to_email": recipient,
                    "subject": "Chat Spaces List",
                    "body": "Hi,\n\nPlease find the list of chat spaces below:\n\n$last_chat_spaces",
                },
                reason="Email the list.",
            ),
        ]

    def _chat_send_message_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        msg_text = _extract_quoted(text) or "Hello from GWorkspace Agent!"
        return [
            PlannedTask(
                id="task-1",
                service="chat",
                action="list_spaces",
                parameters={"page_size": 10},
                reason="Find available chat spaces.",
            ),
            PlannedTask(
                id="task-2",
                service="chat",
                action="send_message",
                parameters={"space": "{{task-1.name}}", "text": msg_text},
                reason="Send the message to the detected space.",
            ),
        ]

    def _docs_to_email_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        d_id = _extract_id(text)
        title = _extract_quoted(text) or "New Document"
        recipient = _extract_email(text) or self.config.default_recipient_email

        tasks = []
        if "create" in lowered or "new" in lowered:
            tasks.append(
                PlannedTask(
                    id="task-1",
                    service="docs",
                    action="create_document",
                    parameters={"title": title},
                    reason=f"Create document '{title}'.",
                )
            )
            d_id = "{{task-1.id}}"
        elif not d_id:
            # Search for existing
            tasks.append(
                PlannedTask(
                    id="task-1",
                    service="drive",
                    action="list_files",
                    parameters={"q": f"name = '{title}'", "page_size": 1},
                    reason="Search for the document ID.",
                )
            )
            d_id = "{{task-1.id}}"

        tasks.append(
            PlannedTask(
                id=f"task-{len(tasks) + 1}",
                service="docs",
                action="get_document",
                parameters={"document_id": d_id},
                reason="Fetch document content.",
            )
        )
        tasks.append(
            PlannedTask(
                id=f"task-{len(tasks) + 1}",
                service="gmail",
                action="send_message",
                parameters={
                    "to_email": recipient,
                    "subject": f"Document Information: {title}",
                    "body": "Hi,\n\nPlease find the document link here: $last_document_url",
                },
                reason="Email the document link.",
            )
        )
        return tasks

    def _forms_sync_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        title = _extract_quoted(text) or "New Form"
        return [
            PlannedTask(
                id="task-1",
                service="forms",
                action="create_form",
                parameters={"title": title},
                reason=f"Create form '{title}'.",
            ),
            PlannedTask(
                id="task-2",
                service="forms",
                action="batch_update",
                parameters={"form_id": "{{task-1.id}}", "requests": []},
                reason="Initialize form structure.",
            ),
        ]

    def _slides_to_email_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        p_id = _extract_id(text)
        recipient = _extract_email(text) or self.config.default_recipient_email

        tasks = []
        if not p_id:
            tasks.append(
                PlannedTask(
                    id="task-1",
                    service="drive",
                    action="list_files",
                    parameters={"q": "mimeType='application/vnd.google-apps.presentation'", "page_size": 1},
                    reason="Search for the latest presentation.",
                )
            )
            p_id = "{{task-1.id}}"

        tasks.append(
            PlannedTask(
                id=f"task-{len(tasks) + 1}",
                service="slides",
                action="get_presentation",
                parameters={"presentation_id": p_id},
                reason="Fetch presentation metadata.",
            )
        )

        tasks.append(
            PlannedTask(
                id=f"task-{len(tasks) + 1}",
                service="gmail",
                action="send_message",
                parameters={
                    "to_email": recipient,
                    "subject": "Slides Presentation Information",
                    "body": "Hi,\n\nPlease find the presentation link here: $last_presentation_url",
                },
                reason="Email the presentation link.",
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
        elif service == "calendar" and action == "create_event":
            parameters["summary"] = _extract_quoted(lowered) or "New Event"
            parameters["start_date"] = date.today().isoformat()  # Default to today for heuristic
        elif service == "drive" and action == "create_folder":
            parameters["folder_name"] = _extract_quoted(lowered) or "New Folder"
        elif service == "docs" and action == "create_document":
            parameters["title"] = _extract_quoted(lowered) or "New Document"
        elif service == "sheets" and action == "create_spreadsheet":
            parameters["title"] = _extract_quoted(lowered) or "New Spreadsheet"
        elif service == "tasks" and action == "create_task":
            parameters["title"] = _extract_quoted(lowered) or "New Task"
        elif service in ("code", "computation"):
            list_match = RE_CODE_LIST.search(lowered)
            data_str = list_match.group(1) if list_match else "[]"
            if "sort" in lowered:
                rev = "True" if any(kw in lowered for kw in ("expensive", "descending", "reverse")) else "False"
                parameters["code"] = f"""data = {data_str}
result = sorted(data, reverse={rev})
print(result)"""
            else:
                # Try to generate generic processing code for "convert to table" etc
                parameters["code"] = f"""# Processed data from previous steps
print('Processing task: {lowered}')"""

        return PlannedTask(
            id=f"task-{index}",
            service=service,
            action=action,
            parameters=parameters,
            reason=f"Detected {SERVICES[service].label} in the request.",
        )

    def _gmail_list_and_get_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        query = _gmail_query_from_text(text)
        return [
            PlannedTask(
                id="task-1",
                service="gmail",
                action="list_messages",
                parameters={"q": query, "max_results": 10},
                reason="Search Gmail messages.",
            ),
            PlannedTask(
                id="task-2",
                service="gmail",
                action="get_message",
                parameters={"message_id": "$gmail_message_ids"},
                reason="Fetch full message details.",
            ),
        ]


def _detect_services_in_order(text: str) -> list[str]:
    hits: list[tuple[int, str]] = []
    strict_services = {"modelarmor", "admin", "script", "events"}

    for service_key, spec in SERVICES.items():
        if service_key in strict_services:
            pattern = re.compile(rf"\b{re.escape(service_key)}\b", re.IGNORECASE)
            match = pattern.search(text)
            if match:
                hits.append((match.start(), service_key))
            continue

        terms = (service_key, *spec.aliases)
        for term in terms:
            pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
            match = pattern.search(text)
            if match:
                hits.append((match.start(), service_key))
                break

    found_services = [service for _, service in sorted(hits, key=lambda item: item[0])]

    # Priority Fix: when the verb "search" is detected alongside one or more
    # Workspace services, decide between *web* search and Workspace-side
    # search.
    #
    # * If the request contains an explicit web-search phrase
    #   (``"search the web"``, ``"web search"``, ``"search online"`` …) keep
    #   ``search`` and instead drop ``drive`` if it was only matched via the
    #   loose ``"document"`` / ``"file"`` aliases — those words are usually
    #   referring to the Doc the user wants to *create*, not an existing
    #   Drive resource.
    # * Otherwise drop ``search`` (the user asked to search a Workspace
    #   service, not the web).
    if "search" in found_services and len(found_services) > 1:
        if _has_explicit_web_search_intent(text):
            # Keep "search". If "drive" was only matched via the generic
            # "document"/"file" aliases (i.e. neither the literal "drive"
            # word nor "google drive" appears in the text), strip it so the
            # heuristic doesn't trigger drive_to_email patterns by mistake.
            if "drive" in found_services and not re.search(
                r"\b(drive|google drive|in my drive|from my drive)\b", text, re.IGNORECASE
            ):
                found_services = [s for s in found_services if s != "drive"]
        else:
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
    quoted = RE_GMAIL_QUERY_QUOTED.search(text)
    if quoted:
        q = quoted.group(1).strip()
        # If the user says "subject:...", keep it. Otherwise, just use the keywords.
        if "subject:" in q.lower() or "from:" in q.lower() or "to:" in q.lower():
            return q
        return q
    match = RE_GMAIL_QUERY_MATCH.search(text)
    if match:
        query = match.group(1).strip()
        query = RE_GMAIL_QUERY_SPLIT.split(query)[0].strip()
        return query
    return ""


def _drive_query_from_text(text: str) -> str:
    quoted = RE_DRIVE_QUERY_QUOTED.search(text)
    if quoted:
        return f"fullText contains '{quoted.group(1).strip()}'"
    match = RE_DRIVE_QUERY_MATCH.search(text)
    if match:
        query = match.group(1).strip()
        query = RE_DRIVE_QUERY_SPLIT.split(query)[0].strip()
        return f"fullText contains '{query}'"
    return ""


# Phrases used when isolating the actual web-search query — these are stripped
# from the start of a request so that the search query passed to the
# web_search tool is concise and on-topic.
_WEB_SEARCH_LEADING_PHRASES: tuple[str, ...] = (
    "search the web for",
    "search web for",
    "search online for",
    "search the internet for",
    "search internet for",
    "search google for",
    "look up online for",
    "look up online",
    "look it up online",
    "find online",
    "find on the web",
    "browse the web for",
    "search for",
)

_WEB_SEARCH_TRAILING_SPLITS = re.compile(
    r"(?:"
    r"\s+(?:and|then)\s+(?:save|store|write|append|create|send|email|share|extract)\b|"
    r"[;,]\s*(?:save|store|write|append|create|send|email|share|extract)\b|"
    r"\s+(?:save|store|write|append|create)\s+to\s+(?:a|the|my)\b|"
    r"\s+send\s+(?:an?\s+)?email\b"
    r")",
    re.IGNORECASE,
)


def _web_search_query_from_text(text: str) -> str:
    """Extract a focused web-search query from a natural-language request.

    Strips a leading "search the web for"/"search online for" prefix and
    trims the result before any task-chaining clause (``"and save"``,
    ``"then email"`` …) so the query passed to the search engine is concise
    and topical. Falls back to a quoted span or the trimmed full text.

    Prefix-stripping is preferred over quoted strings because requests
    typically contain a quoted *artefact name* (e.g. the destination Sheet
    or Doc title) that should NOT be used as the search query.
    """
    if not text:
        return ""

    lowered = text.lower()
    candidate: str | None = None

    # 1. Strip a leading "search the web for ..." prefix.
    for phrase in sorted(_WEB_SEARCH_LEADING_PHRASES, key=len, reverse=True):
        idx = lowered.find(phrase)
        if idx >= 0:
            candidate = text[idx + len(phrase):].lstrip()
            break

    # 2. Truncate at the first chaining clause so we don't pass the entire
    #    "save to Sheet … send email …" tail to the search engine.
    if candidate is not None:
        match = _WEB_SEARCH_TRAILING_SPLITS.search(candidate)
        if match:
            candidate = candidate[: match.start()].rstrip(" .,;:")
        candidate = candidate.strip(" .,;:")

    # 3. Fall back to a quoted span only if prefix-stripping failed to
    #    yield something sensible.
    if not candidate or len(candidate) < 3:
        quoted = re.search(r"['\"]([^'\"\n]{3,200})['\"]", text)
        if quoted:
            candidate = quoted.group(1).strip()

    if not candidate:
        candidate = text.strip()

    # 4. Cap the length so we don't pass essay-length queries to the engine.
    if len(candidate) > 200:
        candidate = candidate[:200].rstrip()
    return candidate


def _extract_id(text: str) -> str | None:
    """Extract a Google Workspace ID (alphanumeric string with underscores/dashes) from text."""
    # Look for common ID pattern: ~44 characters, alphanumeric, includes - and _
    # Often found after 'ID:', 'id ', or in quotes.
    match = RE_EXTRACT_ID.search(text)
    return match.group(1) if match else None


def _extract_email(text: str) -> str | None:
    matches = RE_EXTRACT_EMAIL.findall(text)
    if matches:
        # Try to find one preceded by 'to ' (case-insensitive)
        for m in matches:
            if re.search(rf"to\s+{re.escape(m)}", text, re.IGNORECASE):
                return m.replace(" ", "")
        # Fallback to last match (usually the recipient)
        return matches[-1].replace(" ", "")
    return None


def _extract_quoted(text: str) -> str | None:
    match = RE_EXTRACT_QUOTED.search(text)
    return match.group(1) if match else None


def _extract_sheet_title(text: str) -> str | None:
    m = re.search(r"(?:named|called|titled|sheet|spreadsheet)\s+[\'\"]([^\'\"]+)[\'\"]", text, re.IGNORECASE)
    if m:
        return m.group(1)
    # Fall back to last quoted string, not first
    matches = RE_EXTRACT_QUOTED.findall(text)
    return matches[-1] if matches else None


def _extract_doc_title(text: str) -> str | None:
    m = re.search(r"(?:named|called|titled|doc|document)\s+[\'\"]([^\'\"]+)[\'\"]", text, re.IGNORECASE)
    if m:
        return m.group(1)
    # Fall back to last quoted string, not first
    matches = RE_EXTRACT_QUOTED.findall(text)
    return matches[-1] if matches else None


def _first_int(text: str) -> int | None:
    match = RE_FIRST_INT.search(text)
    if match:
        val = int(match.group(1))
        return val if val > 0 else None
    return None


def _is_drive_to_email_request(text: str) -> bool:
    lowered = text.lower()
    exclusion_words = (
        "metadata only",
        "names only",
        "no file content",
        "do not download",
    )
    if any(word in lowered for word in exclusion_words):
        return False
    # When the user explicitly asks for a web search the words "document" /
    # "file" usually describe the artefact they want *created*, not a
    # Drive resource to look up. Punt to the dedicated web-search patterns.
    if _has_explicit_web_search_intent(lowered):
        return False
    return any(t in lowered for t in ("drive", "file", "document")) and any(
        t in lowered for t in ("email", "send", "mail")
    )


def _is_drive_metadata_to_email_request(text: str) -> bool:
    lowered = text.lower()
    if _has_explicit_web_search_intent(lowered):
        return False
    intent_words = (
        "count", "table", "summary", "metadata", "sizes", "group",
        "metadata only", "names only", "no file content", "do not download",
    )
    if not any(word in lowered for word in intent_words):
        return False
    return any(t in lowered for t in ("drive", "file", "document")) and any(
        t in lowered for t in ("email", "send", "mail")
    )


def _is_metadata_only_request(text: str) -> bool:
    """Detect Drive metadata-only requests that do NOT require emailing (counts, tables, summaries)."""
    if _has_explicit_web_search_intent(text):
        return False
    has_drive_intent = any(t in text for t in ("drive", "file", "document", "folder"))
    has_metadata_intent = any(
        t in text
        for t in (
            "metadata only",
            "no file content",
            "names only",
            "do not download",
            "metadata",
            "summary",
            "table",
            "count",
            "list",
            "sizes",
            "group",
        )
    )
    has_email_intent = any(t in text for t in ("email", "send", "mail"))
    return has_drive_intent and has_metadata_intent and not has_email_intent


def _is_gmail_to_sheets_request(text: str) -> bool:
    """Detect a Gmail → Sheets workflow.

    The previous implementation matched any request that contained
    ``"email"`` + ``"sheet"`` + a save verb, which incorrectly captured web
    search requests like ``"Search the web ... save to Google Sheet ... send
    email"`` and routed them to ``gmail.list_messages``. We now reject
    requests that carry an explicit web-search intent so they fall through
    to the dedicated web-search heuristics.
    """
    if _has_explicit_web_search_intent(text):
        return False
    return (
        ("gmail" in text or "email" in text)
        and "sheet" in text
        and any(t in text for t in ("save", "extract", "append", "write"))
    )


def _is_sheet_to_email_request(text: str) -> bool:
    if _has_explicit_web_search_intent(text):
        return False
    return "sheet" in text and any(t in text for t in ("email", "send", "mail"))


def _is_drive_folder_move_request(text: str) -> bool:
    return any(t in text for t in ("drive", "file")) and any(t in text for t in ("move", "folder", "organize"))


def _is_docs_to_email_request(text: str) -> bool:
    if _has_explicit_web_search_intent(text):
        return False
    return any(t in text for t in ("doc", "document")) and any(t in text for t in ("email", "send", "mail"))


def _is_forms_sync_request(text: str) -> bool:
    return any(t in text for t in ("form", "survey")) and any(t in text for t in ("sync", "save", "data", "upload"))


def _is_slides_to_email_request(text: str) -> bool:
    return any(t in text for t in ("slide", "presentation", "deck")) and any(t in text for t in ("email", "send", "mail"))


def _is_sheet_creation_request(text: str) -> bool:
    if _has_explicit_web_search_intent(text):
        return False
    # Avoid matching "create email" or "create doc"
    if "email" in text or "doc" in text or "folder" in text:
        # If it's "create a sheet", it's fine. If it's "create an email", it's not.
        return (
            "create" in text
            and ("sheet" in text or "spreadsheet" in text)
            and not any(phrase in text for phrase in ("create email", "create a doc", "create document"))
        )
    return "sheet" in text and any(t in text for t in ("create", "add", "new"))


def _extract_data_rows(text: str) -> list[list[Any]]:
    """Extract rows from text like 'Score1, 100' or similar csv-like patterns."""
    rows = []
    # Look for header and data rows in quotes
    matches = RE_EXTRACT_DATA_ROWS.findall(text)
    for m in matches:
        if "," in m:
            rows.append([item.strip() for item in m.split(",")])

    # If no rows found in quotes, try to find patterns like 'Score1, 100'
    if not rows:
        for m in RE_EXTRACT_DATA_PATTERN.finditer(text):
            rows.append([m.group(1).strip(), m.group(2).strip()])

    return rows
