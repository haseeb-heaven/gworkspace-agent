"""CrewAI-backed planning for natural-language Workspace requests."""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

from .file_types import RE_FILE_PATH
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


def _generate_computation_code(lowered: str, text: str) -> str:
    """Generate Python code from natural language computation requests.

    Handles common patterns like fibonacci, prime numbers, sums, etc.
    Returns safe Python code that can run in the RestrictedPython sandbox.
    """
    # Try to extract number from text (e.g., "first 10 fibonacci")
    num_match = re.search(r"(\d+)\s*(?:st|nd|rd|th)?\s*fibonacci", lowered)
    if num_match or "fibonacci" in lowered:
        n = int(num_match.group(1)) if num_match else 10
        return f"""# Calculate first {n} Fibonacci numbers
a, b = 0, 1
result = []
for _ in range({n}):
    result.append(a)
    a, b = b, a + b
print(result)
result = result"""

    # Prime numbers
    if "prime" in lowered:
        num_match = re.search(r"(\d+)\s*(?:st|nd|rd|th)?\s*prime", lowered)
        n = int(num_match.group(1)) if num_match else 10
        return f"""# Find first {n} prime numbers
def is_prime(n):
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True

primes = []
num = 2
while len(primes) < {n}:
    if is_prime(num):
        primes.append(num)
    num += 1
print(primes)
result = primes"""

    # Sum/calculate with numbers
    sum_match = re.search(r"sum\s+of\s+(\d+)\s*(?:to|through|-)\s*(\d+)", lowered)
    if sum_match:
        start, end = int(sum_match.group(1)), int(sum_match.group(2))
        return f"""# Sum of numbers from {start} to {end}
result = sum(range({start}, {end} + 1))
print(result)
result = result"""

    # Factorial
    fact_match = re.search(r"(\d+)!|factorial\s+of\s+(\d+)", lowered)
    if fact_match:
        n = int(fact_match.group(1) or fact_match.group(2))
        return f"""# Calculate factorial of {n}
result = 1
for i in range(1, {n} + 1):
    result *= i
print(result)
result = result"""

    # Default: simple calculator for expressions
    return f"""# Computation request: {text}
# Note: This is a heuristic-generated computation.
# For complex computations, please use the LLM-powered planning mode.
print("Heuristic computation mode")
result = "Computation completed"
result = result"""


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
    "find out",
    "search around",
    "search about",
    "cheapest",
    "best price",
    "available in the market",
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

        # Use Strategy Pattern for heuristic planning
        plan = _plan_with_strategies(text, lowered, services, self.config, self.logger, self)
        if plan:
            return plan

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
        recipient = _extract_email(text, default=self.config.default_recipient_email)

        # Extract the raw search term for a user-friendly email subject
        quoted = RE_DRIVE_QUERY_QUOTED.search(text)
        if quoted:
            search_term = quoted.group(1).strip()
        else:
            match = RE_DRIVE_QUERY_MATCH.search(text)
            if match:
                search_term = RE_DRIVE_QUERY_SPLIT.split(match.group(1).strip())[0].strip()
            else:
                search_term = "Drive files"

        exclusion_words = ("count", "table", "summary", "metadata", "no file content", "do not download", "names only")
        skip_export = any(word in lowered for word in exclusion_words)

        # Check if user wants to attach the file or if it's likely an image
        wants_attach = "attach" in lowered or "image" in lowered or "photo" in lowered or "picture" in lowered

        if skip_export or wants_attach:
            # For attachments or metadata-only requests, email the Drive link
            body_content = """Hi,

Here are the files found:

$drive_metadata_table

You can access the files at:
$drive_file_links"""
        else:
            body_content = """Hi,

Please find the content below:
$last_export_file_content"""

        send_params: dict[str, Any] = {"to_email": recipient, "subject": f"Document: {search_term}", "body": body_content}

        tasks = [
            PlannedTask(
                id="task-1",
                service="drive",
                action="list_files",
                parameters={"q": query, "page_size": 50},
                reason="Search for the requested document.",
            )
        ]

        # Only export if not skipping and not an attachment request
        if not skip_export and not wants_attach:
            tasks.append(
                PlannedTask(
                    id="task-2",
                    service="drive",
                    action="export_file",
                    parameters={"file_id": "{{task-1.files.0.id}}", "mime_type": "text/plain"},
                    reason="Extract content for the email.",
                )
            )

        tasks.append(
            PlannedTask(
                id=f"task-{len(tasks) + 1}",
                service="gmail",
                action="send_message",
                parameters=send_params,
                reason="Email the file information or content.",
            )
        )

        return tasks

    def _drive_metadata_to_gmail_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        """Drive metadata with explicit email intent: list files -> compute table -> send email."""
        query = _drive_query_from_text(text)
        recipient = _extract_email(text, default=self.config.default_recipient_email)
        page_size = _first_int(lowered) or 50

        # Extract the raw search term for a user-friendly email subject
        quoted = RE_DRIVE_QUERY_QUOTED.search(text)
        if quoted:
            search_term = quoted.group(1).strip()
        else:
            match = RE_DRIVE_QUERY_MATCH.search(text)
            if match:
                search_term = RE_DRIVE_QUERY_SPLIT.split(match.group(1).strip())[0].strip()
            else:
                search_term = "Drive files"

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
                    "subject": f"Drive Metadata Summary: {search_term}",
                    "body": "Here is the summary you requested:\n\n{{task-2.stdout}}",
                },
                reason="Email the metadata summary table.",
            ),
        ]

    def _drive_delete_by_name_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        """Drive delete by name: search first, then delete the first match."""
        # Extract the file name from quotes
        file_name = _extract_quoted(lowered) or ""
        query = f"name contains '{file_name}'"

        return [
            PlannedTask(
                id="task-1",
                service="drive",
                action="list_files",
                parameters={"q": query, "page_size": 10},
                reason=f"Search for file named '{file_name}' to get its ID.",
            ),
            PlannedTask(
                id="task-2",
                service="drive",
                action="delete_file",
                parameters={"file_id": "{{task-1.id}}"},
                reason="Delete the found file using its ID.",
            ),
        ]

    def _drive_to_sheets_to_gmail_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        """Drive → Sheets → Gmail workflow: search Drive, export document content to Sheets, email the link."""
        query = _drive_query_from_text(text)
        recipient = _extract_email(text, default=self.config.default_recipient_email)

        # Extract the document name from the query for the sheet title
        sheet_title = "Results"
        if "'" in query:
            doc_name = query.split("'")[1]
            sheet_title = f"Results: {doc_name}"

        # Code to convert document text to table format
        code_script = """# Read the exported document content
content = $last_export_file_content

if not content or len(content.strip()) == 0:
    print('No content found in document.')
    result = []
else:
    # Split content into lines
    lines = content.strip().split('\\n')

    # Create table from lines (each line becomes a row)
    # Split lines by common delimiters (tabs, pipes, commas)
    result = []
    for line in lines:
        if line.strip():
            # Try to split by common delimiters
            if '\\t' in line:
                row = line.split('\\t')
            elif '|' in line:
                row = line.split('|')
            elif ',' in line:
                row = line.split(',')
            else:
                row = [line]
            # Clean up whitespace
            row = [cell.strip() for cell in row if cell.strip()]
            if row:
                result.append(row)

    print(f'Converted {len(result)} rows from document')

print(result)"""

        tasks = [
            PlannedTask(
                id="task-1",
                service="drive",
                action="list_files",
                parameters={"q": query, "page_size": 50},
                reason="Search for the requested document.",
            ),
            PlannedTask(
                id="task-2",
                service="drive",
                action="export_file",
                parameters={
                    "file_id": "{{task-1.files[0].id}}",
                    "mime_type": "text/plain",
                },
                reason="Export the document content as text.",
            ),
            PlannedTask(
                id="task-3",
                service="code",
                action="execute",
                parameters={"code": code_script},
                reason="Convert document content to table format.",
            ),
            PlannedTask(
                id="task-4",
                service="sheets",
                action="create_spreadsheet",
                parameters={"title": sheet_title},
                reason="Create a spreadsheet to store the results.",
            ),
            PlannedTask(
                id="task-5",
                service="sheets",
                action="append_values",
                parameters={
                    "spreadsheet_id": "{{task-4.spreadsheetId}}",
                    "values": "$last_code_result",
                },
                reason="Append the converted table data to the sheet.",
            ),
            PlannedTask(
                id="task-6",
                service="gmail",
                action="send_message",
                parameters={
                    "to_email": recipient,
                    "subject": f"Document Conversion: {sheet_title}",
                    "body": f"Your document has been converted to table format in Google Sheets.\n\nPlease check your Google Drive for the sheet named '{sheet_title}'.\n\nGoogle Sheet: $last_spreadsheet_url",
                },
                reason="Email the results.",
            ),
        ]

        return tasks

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
        wants_email = False  # Will be recomputed after query extraction
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

        # Check for email intent in the text AFTER the search query to avoid
        # false positives when the search topic itself contains email-related
        # phrases (e.g., "Search the web for how to send email").
        # We find the position of the last search intent phrase and check if
        # email intent appears after it.
        search_intent_pos = -1
        for phrase in sorted(_WEB_SEARCH_LEADING_PHRASES, key=len, reverse=True):
            idx = lowered.find(phrase)
            if idx >= 0:
                search_intent_pos = idx + len(phrase)
                break

        if search_intent_pos >= 0:
            text_after_search_intent = text[search_intent_pos:]
            wants_email = any(
                re.search(pattern, text_after_search_intent.lower()) for pattern in (
                    r"\bsend\s+(?:an?\s+)?email\b",
                    r"\bsend\s+mail\b",
                    r"\bemail\s+(?:it\s+)?to\b",
                    r"\bemail\s+(?:me|the\s+results?|the\s+link|them)\b",
                    r"\bto\s+email\b",
                    r"\bto\s+send\s+(?:an?\s+)?email\b",
                    r"\bcompose\s+(?:an?\s+)?email\b",
                    r"\bsend\s+detailed\s+email\b",
                    r"\bmail\s+(?:it\s+)?to\b",
                    r"\bsend_message\b",
                )
            )
        else:
            # Fallback: check entire text if no search intent phrase found
            wants_email = any(
                re.search(pattern, lowered) for pattern in (
                    r"\bsend\s+(?:an?\s+)?email\b",
                    r"\bsend\s+mail\b",
                    r"\bemail\s+(?:it\s+)?to\b",
                    r"\bemail\s+(?:me|the\s+results?|the\s+link|them)\b",
                    r"\bto\s+email\b",
                    r"\bto\s+send\s+(?:an?\s+)?email\b",
                    r"\bcompose\s+(?:an?\s+)?email\b",
                    r"\bsend\s+detailed\s+email\b",
                    r"\bmail\s+(?:it\s+)?to\b",
                    r"\bsend_message\b",
                )
            )

        recipient = _extract_email(text, default=self.config.default_recipient_email)
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
        recipient = _extract_email(text, default=self.config.default_recipient_email)

        # Extract the raw search term for a user-friendly email subject
        quoted = RE_GMAIL_QUERY_QUOTED.search(text)
        if quoted:
            search_term = quoted.group(1).strip()
        else:
            match = RE_GMAIL_QUERY_MATCH.search(text)
            if match:
                search_term = RE_GMAIL_QUERY_SPLIT.split(match.group(1).strip())[0].strip()
            else:
                search_term = "Gmail messages"
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
                parameters={"title": f"Results: {search_term}"},
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
                    "subject": f"Processed: {search_term}",
                    "body": """Hi,

Please find the spreadsheet here: $last_spreadsheet_url""",
                },
                reason="Email the final spreadsheet link.",
            ),
        ]

    def _sheet_to_email_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        s_id = _extract_id(text)
        recipient = _extract_email(text, default=self.config.default_recipient_email)

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
        recipient = _extract_email(text, default=self.config.default_recipient_email)

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

    def _drive_folder_upload_tasks(self, text: str, lowered: str) -> list[PlannedTask]:
        # Extract file path from text using _extract_file_path to handle both quoted and unquoted paths
        file_path_match = RE_FILE_PATH.search(text)
        file_path = ""
        text_without_file = text

        if file_path_match:
            # Extract the matched file path from whichever group matched
            file_path = next((g for g in file_path_match.groups() if g is not None), "")
            # Remove only the matched span from the original text to avoid clobbering other matches
            start, end = file_path_match.span()
            text_without_file = text[:start] + text[end:]

        # Extract folder name from the remaining text (after removing the file path span)
        folder_name = _extract_quoted(text_without_file)

        # Fallback: try to extract quoted strings from original text if no folder name found
        if not folder_name:
            quoted_strings = re.findall(r'["\047]([^"\047]{1,200})["\047]', text)
            # Filter out the file_path if it was quoted
            remaining_quotes = [q for q in quoted_strings if q != file_path]
            if remaining_quotes:
                folder_name = remaining_quotes[0]
            else:
                folder_name = "New Folder"

        # Return tasks even if file_path is empty - verification engine will catch missing file
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
                action="upload_file",
                parameters={"file_path": file_path, "folder_id": "{{task-1.id}}"},
                reason=f"Upload {file_path} to the folder.",
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
        recipient = _extract_email(text, default=self.config.default_recipient_email)
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
        recipient = _extract_email(text, default=self.config.default_recipient_email)
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
        recipient = _extract_email(text, default=self.config.default_recipient_email)
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
        recipient = _extract_email(text, default=self.config.default_recipient_email)

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
        recipient = _extract_email(text, default=self.config.default_recipient_email)

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
            parameters["to_email"] = _extract_email(lowered, default=self.config.default_recipient_email)
            parameters["subject"] = "GWorkspace Notification"
            parameters["body"] = f"Update regarding your request: {lowered[:100]}..."
        elif service == "calendar" and action == "create_event":
            parameters["summary"] = _extract_quoted(lowered) or "New Event"
            parameters["start_date"] = date.today().isoformat()  # Default to today for heuristic
        elif service == "drive" and action == "create_folder":
            parameters["folder_name"] = _extract_quoted(lowered) or "New Folder"
        elif service == "drive" and action == "upload_file":
            parameters["file_path"] = _extract_file_path(lowered) or ""
        elif service == "drive" and action == "copy_file":
            parameters["file_id"] = _extract_id(lowered) or ""
            parameters["name"] = _extract_quoted(lowered) or "Copy"
        elif service == "drive" and action == "move_file":
            ids = RE_EXTRACT_ID.findall(lowered)
            parameters["file_id"] = ids[0] if ids else ""
            if len(ids) > 1:
                parameters["folder_id"] = ids[1]
            else:
                # Try to find folder name in quotes if only one ID is present
                folder_name = _extract_quoted(lowered)
                if folder_name:
                    parameters["folder_id"] = f"name contains '{folder_name}'"
                # If neither a second ID nor a quoted folder name is found,
                # leave folder_id unset so the planner requests clarification.
        elif service == "drive" and action == "update_file_metadata":
            parameters["file_id"] = _extract_id(lowered) or ""
            parameters["name"] = _extract_quoted(lowered) or ""
        elif service == "drive" and action == "delete_file":
            parameters["file_id"] = _extract_id(lowered) or ""
        elif service == "drive" and action == "move_to_trash":
            parameters["file_id"] = _extract_id(lowered) or ""
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
                sort_index = 1  # Default index
                numeric_sort = False

                sort_by_match = re.search(r"sort by (\w+)", lowered)
                if sort_by_match:
                    sort_key_name = sort_by_match.group(1).lower()
                    if sort_key_name in ("name", "title"):
                        sort_index = 0
                    elif sort_key_name == "price":
                        sort_index = 1
                        numeric_sort = True

                code = rf"""
import re

data = {data_str}

def get_sort_key(row, index, is_numeric) -> float | str:
    try:
        if not isinstance(row, (list, tuple)) or not len(row) > index:
            return 0 if is_numeric else ""

        val = row[index]

        if is_numeric:
            match = re.search(r'[-+]?[\d,.]+', str(val))
            if match:
                return float(match.group(0).replace(',', ''))
            return 0.0
        else:
            return str(val).lower()
    except (ValueError, TypeError, IndexError):
        return 0.0 if is_numeric else ""

try:
    sort_index = {sort_index}
    is_numeric = {numeric_sort}

    if isinstance(data, list) and data:
        if isinstance(data[0], (list, tuple)):
             if all(len(r) > sort_index for r in data):
                data = sorted(data, key=lambda r: get_sort_key(r, sort_index, is_numeric), reverse={rev})
             else:
                print(f"Sorting failed: Inconsistent row lengths, cannot sort on index {{sort_index}}.")
        else:
             data = sorted(data, reverse={rev})

except Exception as exc:
    print(f"Sorting failed: {{exc}} — leaving data unsorted")

result = data
print(result)
"""
                parameters["code"] = code
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
    r"\s*(?:,\s*(?:and\s+)?(?:then\s+)?|(?<!\w)(?:then|after\s+that|and)\s+)"
    r"(?:save|write|store|export|add|insert|put|append|email|send|create|make|generate|upload|share)\b",
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


def _extract_email(text: str, default: str | None = None, warn_on_default: bool = True) -> str | None:
    """Extract email address from text.

    Args:
        text: Text to search for email addresses
        default: Default email to return if no email found (None to return None)
        warn_on_default: Whether to log a warning when using the default

    Returns:
        Extracted email address, default if provided and no email found, or None
    """
    matches = RE_EXTRACT_EMAIL.findall(text)
    if matches:
        # Try to find one preceded by 'to ' (case-insensitive)
        for m in matches:
            if re.search(rf"to\s+{re.escape(m)}", text, re.IGNORECASE):
                return m.replace(" ", "")
        # Fallback to last match (usually the recipient)
        return matches[-1].replace(" ", "")
    if default is not None:
        if warn_on_default:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("No email found in text '%s', using default: %s", text[:100], default)
        return default
    return None


def _extract_quoted(text: str) -> str | None:
    match = RE_EXTRACT_QUOTED.search(text)
    return match.group(1) if match else None


def _extract_file_path(text: str) -> str | None:
    """Extract a local file path from natural language for upload operations."""
    match = RE_FILE_PATH.search(text)
    if match:
        return next(g for g in match.groups() if g is not None)
    return None


def _extract_sheet_title(text: str) -> str | None:
    m = re.search(r"(?:named|called|titled|sheet|spreadsheet)\s+[\'\"]([^\'\"]+)[\'\"]", text, re.IGNORECASE)
    if m:
        return m.group(1)
    # Fall back to last quoted string, not first
    matches = RE_EXTRACT_QUOTED.findall(text)
    return matches[-1] if matches else None


def _extract_doc_title(text: str) -> str | None:
    m = re.search(r"(?:named|called|titled|doc|document)(?:\s+call\s+that)?\s+[\'\"]([^\'\"]+)[\'\"]", text, re.IGNORECASE)
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
    # If user explicitly mentions "sheet" or "spreadsheet" with conversion verbs
    # (convert, save to, export to), route to Drive -> Sheets -> Gmail instead
    sheet_keywords = ("sheet", "spreadsheet")
    conversion_verbs = ("convert", "save to", "export to", "append to", "write to")
    if any(kw in lowered for kw in sheet_keywords) and any(verb in lowered for verb in conversion_verbs):
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
    lowered = text.lower()
    if _has_explicit_web_search_intent(text):
        return False
    # If user explicitly mentions "sheet" or "spreadsheet" with conversion verbs
    # (convert, save to, export to), route to Drive -> Sheets patterns instead
    sheet_keywords = ("sheet", "spreadsheet")
    conversion_verbs = ("convert", "save to", "export to", "append to", "write to")
    if any(kw in lowered for kw in sheet_keywords) and any(verb in lowered for verb in conversion_verbs):
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

    Also reject requests with explicit Drive/document search intent (e.g.
    "Search document X", "find document Y") to avoid misrouting Drive-based
    requests to Gmail.
    """
    lowered = text.lower()
    if _has_explicit_web_search_intent(text):
        return False
    # Reject Drive/document search requests
    if re.search(r"\b(search|find|list|show)\s+(document|drive|file)\b", text, re.IGNORECASE):
        return False
    return (
        ("gmail" in lowered or "email" in lowered)
        and "sheet" in lowered
        and any(t in lowered for t in ("save", "extract", "append", "write"))
    )


def _is_sheet_to_email_request(text: str) -> bool:
    if _has_explicit_web_search_intent(text):
        return False
    return "sheet" in text and any(t in text for t in ("email", "send", "mail"))


def _is_drive_folder_move_request(text: str) -> bool:
    # Exclude upload/copy requests - those should use upload_file, not move_file
    # Use word boundaries to avoid matching substrings like "saved", "copyrighted"
    if re.search(r"\b(?:upload|copy|save)\b", text, re.IGNORECASE):
        return False
    lowered = text.lower()
    return any(t in lowered for t in ("drive", "file")) and any(t in lowered for t in ("move", "folder", "organize"))


def _is_drive_folder_upload_request(text: str) -> bool:
    # Use word boundaries to avoid matching substrings like "saved", "copyrighted"
    has_target = re.search(r"\b(?:drive|folder)\b", text, re.IGNORECASE)
    has_action = re.search(r"\b(?:upload|copy|save)\b", text, re.IGNORECASE)
    # Require explicit folder-creation intent
    has_create = re.search(r"\b(?:create|new|make)(?:\s+folder)?\b", text, re.IGNORECASE)
    return bool(has_target and has_action and has_create)



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


def _is_drive_to_sheets_to_email_request(text: str) -> bool:
    """Detect a Drive → Sheets → Email workflow.

    Matches requests like "Search document X, convert to table in Sheets, send email"
    where the user wants to search Drive, export to Sheets, and email the result.
    """
    lowered = text.lower()
    if _has_explicit_web_search_intent(text):
        return False
    return (
        ("drive" in lowered or "document" in lowered or "file" in lowered)
        and "sheet" in lowered
        and ("email" in lowered or "send" in lowered or "mail" in lowered)
        and any(t in lowered for t in ("search", "find", "list", "show"))
    )


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


# ============================================================================
# STRATEGY PATTERN FOR HEURISTIC PLANNING
# ============================================================================


@dataclass
class PlanningContext:
    """Context data passed to planning strategies."""
    text: str
    lowered: str
    services: list[str]
    config: AppConfigModel
    logger: logging.Logger


class PlanningStrategy(ABC):
    """Base class for heuristic planning strategies."""

    @abstractmethod
    def matches(self, ctx: PlanningContext) -> bool:
        """Return True if this strategy applies to the given context."""
        pass

    @abstractmethod
    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan | None:
        """Execute the strategy and return a plan, or None if not applicable."""
        pass

    @abstractmethod
    def priority(self) -> int:
        """Return priority (higher = checked first)."""
        pass


class WebSearchStrategy(PlanningStrategy):
    """Pattern WS-*: Web Search-driven workflows."""

    def priority(self) -> int:
        return 100  # Highest priority to avoid misrouting to gmail/drive

    def matches(self, ctx: PlanningContext) -> bool:
        return (
            "search" in ctx.services
            and _has_explicit_web_search_intent(ctx.lowered)
        )

    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan | None:
        ws_plan = agent._web_search_pattern_tasks(ctx.text, ctx.lowered, ctx.services)
        if ws_plan is not None:
            tasks, summary_chain = ws_plan
            return RequestPlan(
                raw_text=ctx.text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: {summary_chain}",
                confidence=0.85,
                no_service_detected=False,
                source="heuristic",
            )
        return None


class DriveMetadataOnlyStrategy(PlanningStrategy):
    """Pattern A1: Drive Metadata Only (e.g. counts, tables, summaries)."""

    def priority(self) -> int:
        return 90

    def matches(self, ctx: PlanningContext) -> bool:
        return (
            "drive" in ctx.services
            and _is_metadata_only_request(ctx.lowered)
            and not ("gmail" in ctx.services and _is_drive_to_email_request(ctx.lowered))
            and not _is_drive_folder_move_request(ctx.lowered)
            and not _is_drive_folder_upload_request(ctx.lowered)
        )

    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan:
        tasks = agent._drive_metadata_computation_tasks(ctx.text, ctx.lowered)
        task_chain = " -> ".join(f"{t.service}.{t.action}" for t in tasks)
        return RequestPlan(
            raw_text=ctx.text,
            tasks=tasks,
            summary=f"Planned {len(tasks)} tasks: {task_chain}",
            confidence=0.75,
            no_service_detected=False,
            source="heuristic",
        )


class DriveMetadataToEmailStrategy(PlanningStrategy):
    """Pattern A-Metadata: Drive Metadata -> Code -> Gmail."""

    def priority(self) -> int:
        return 85

    def matches(self, ctx: PlanningContext) -> bool:
        return (
            "drive" in ctx.services
            and "gmail" in ctx.services
            and _is_drive_metadata_to_email_request(ctx.lowered)
        )

    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan:
        tasks = agent._drive_metadata_to_gmail_tasks(ctx.text, ctx.lowered)
        task_chain = " -> ".join(f"{t.service}.{t.action}" for t in tasks)
        return RequestPlan(
            raw_text=ctx.text,
            tasks=tasks,
            summary=f"Planned {len(tasks)} tasks: {task_chain}",
            confidence=0.8,
            no_service_detected=False,
            source="heuristic",
        )


class DriveToSheetsToEmailStrategy(PlanningStrategy):
    """Pattern A2: Drive -> Sheets -> Gmail (Search, Export, Email)."""

    def priority(self) -> int:
        return 80

    def matches(self, ctx: PlanningContext) -> bool:
        return (
            "drive" in ctx.services
            and "sheets" in ctx.services
            and "gmail" in ctx.services
            and _is_drive_to_sheets_to_email_request(ctx.lowered)
        )

    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan:
        tasks = agent._drive_to_sheets_to_gmail_tasks(ctx.text, ctx.lowered)
        task_chain = " -> ".join(f"{t.service}.{t.action}" for t in tasks)
        return RequestPlan(
            raw_text=ctx.text,
            tasks=tasks,
            summary=f"Planned {len(tasks)} tasks: {task_chain}",
            confidence=0.75,
            no_service_detected=False,
            source="heuristic",
        )


class DriveToEmailStrategy(PlanningStrategy):
    """Pattern A: Drive -> Gmail (Search & Email)."""

    def priority(self) -> int:
        return 70

    def matches(self, ctx: PlanningContext) -> bool:
        return (
            "drive" in ctx.services
            and "gmail" in ctx.services
            and _is_drive_to_email_request(ctx.lowered)
        )

    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan:
        tasks = agent._drive_to_gmail_tasks(ctx.text, ctx.lowered)
        task_chain = " -> ".join(f"{t.service}.{t.action}" for t in tasks)
        return RequestPlan(
            raw_text=ctx.text,
            tasks=tasks,
            summary=f"Planned {len(tasks)} tasks: {task_chain}",
            confidence=0.7,
            no_service_detected=False,
            source="heuristic",
        )


class DriveFolderMoveStrategy(PlanningStrategy):
    """Pattern C: Drive Folder & Move."""

    def priority(self) -> int:
        return 65

    def matches(self, ctx: PlanningContext) -> bool:
        return "drive" in ctx.services and _is_drive_folder_move_request(ctx.lowered)

    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan:
        tasks = agent._drive_folder_move_tasks(ctx.text, ctx.lowered)
        return RequestPlan(
            raw_text=ctx.text,
            tasks=tasks,
            summary=f"Planned {len(tasks)} tasks: drive.create_folder -> drive.list_files -> drive.move_file",
            confidence=0.7,
            no_service_detected=False,
            source="heuristic",
        )



class DriveFolderUploadStrategy(PlanningStrategy):
    """Pattern C2: Drive Folder & Upload."""

    def priority(self) -> int:
        return 72  # Higher priority than move strategy (65) and DriveToEmailStrategy (70)

    def matches(self, ctx: PlanningContext) -> bool:
        return "drive" in ctx.services and _is_drive_folder_upload_request(ctx.lowered)

    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan:
        tasks = agent._drive_folder_upload_tasks(ctx.text, ctx.lowered)
        task_chain = " -> ".join(f"{t.service}.{t.action}" for t in tasks)
        return RequestPlan(
            raw_text=ctx.text,
            tasks=tasks,
            summary=f"Planned {len(tasks)} tasks: {task_chain}",
            confidence=0.75,
            no_service_detected=False,
            source="heuristic",
        )



class GmailToSheetsStrategy(PlanningStrategy):
    """Pattern B: Gmail -> Sheets -> Email (Extraction)."""

    def priority(self) -> int:
        return 60

    def matches(self, ctx: PlanningContext) -> bool:
        return (
            "gmail" in ctx.services
            and "sheets" in ctx.services
            and _is_gmail_to_sheets_request(ctx.lowered)
        )

    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan:
        tasks = agent._gmail_to_sheets_tasks(ctx.text, ctx.lowered)
        return RequestPlan(
            raw_text=ctx.text,
            tasks=tasks,
            summary=f"Planned {len(tasks)} tasks: gmail.list_messages -> sheets.create_spreadsheet -> sheets.append_values -> gmail.send_message",
            confidence=0.7,
            no_service_detected=False,
            source="heuristic",
        )


class SheetCreationStrategy(PlanningStrategy):
    """Pattern D: Sheet Creation & Data."""

    def priority(self) -> int:
        return 55

    def matches(self, ctx: PlanningContext) -> bool:
        return "sheets" in ctx.services and _is_sheet_creation_request(ctx.lowered)

    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan:
        tasks = agent._sheets_creation_tasks(ctx.text, ctx.lowered)
        return RequestPlan(
            raw_text=ctx.text,
            tasks=tasks,
            summary=f"Planned {len(tasks)} tasks: sheets.create_spreadsheet -> sheets.append_values -> sheets.get_values -> code.execute",
            confidence=0.8,
            no_service_detected=False,
            source="heuristic",
        )


class GmailListAndGetStrategy(PlanningStrategy):
    """Pattern F: Gmail List & Get (Always fetch details for searches)."""

    def priority(self) -> int:
        return 50

    def matches(self, ctx: PlanningContext) -> bool:
        return (
            len(ctx.services) == 1
            and ctx.services[0] == "gmail"
            and any(kw in ctx.lowered for kw in ("list", "search", "find", "show"))
        )

    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan:
        tasks = agent._gmail_list_and_get_tasks(ctx.text, ctx.lowered)
        return RequestPlan(
            raw_text=ctx.text,
            tasks=tasks,
            summary=f"Planned {len(tasks)} tasks: gmail.list_messages -> gmail.get_message",
            confidence=0.8,
            no_service_detected=False,
            source="heuristic",
        )


class SheetToEmailStrategy(PlanningStrategy):
    """Pattern G: Sheet -> Email."""

    def priority(self) -> int:
        return 45

    def matches(self, ctx: PlanningContext) -> bool:
        return (
            "sheets" in ctx.services
            and "gmail" in ctx.services
            and _is_sheet_to_email_request(ctx.lowered)
        )

    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan:
        tasks = agent._sheet_to_email_tasks(ctx.text, ctx.lowered)
        return RequestPlan(
            raw_text=ctx.text,
            tasks=tasks,
            summary=f"Planned {len(tasks)} tasks: sheets.get_values -> gmail.send_message",
            confidence=0.8,
            no_service_detected=False,
            source="heuristic",
        )


class DocsToEmailStrategy(PlanningStrategy):
    """Pattern H: Docs -> Email."""

    def priority(self) -> int:
        return 40

    def matches(self, ctx: PlanningContext) -> bool:
        return (
            "docs" in ctx.services
            and "gmail" in ctx.services
            and _is_docs_to_email_request(ctx.lowered)
        )

    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan:
        tasks = agent._docs_to_email_tasks(ctx.text, ctx.lowered)
        return RequestPlan(
            raw_text=ctx.text,
            tasks=tasks,
            summary=f"Planned {len(tasks)} tasks: docs.create_document -> docs.get_document -> gmail.send_message",
            confidence=0.8,
            no_service_detected=False,
            source="heuristic",
        )


class DriveDeleteByNameStrategy(PlanningStrategy):
    """Pattern: Drive Delete by Name (Search first, then delete)."""

    def priority(self) -> int:
        return 36  # Higher than FormsSyncStrategy

    def matches(self, ctx: PlanningContext) -> bool:
        if "drive" not in ctx.services:
            return False
        lowered = ctx.lowered
        # Check if this is a delete request
        if not any(kw in lowered for kw in ("delete", "remove")):
            return False
        # Check if we have a name in quotes but no valid file ID (25+ chars)
        has_quoted_name = bool(_extract_quoted(lowered))
        has_file_id = bool(_extract_id(lowered))
        return has_quoted_name and not has_file_id

    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan:
        tasks = agent._drive_delete_by_name_tasks(ctx.text, ctx.lowered)
        return RequestPlan(
            raw_text=ctx.text,
            tasks=tasks,
            summary="Planned 2 tasks: drive.list_files (search by name) -> drive.delete_file",
            confidence=0.75,
            no_service_detected=False,
            source="heuristic",
        )


class FormsSyncStrategy(PlanningStrategy):
    """Pattern I: Forms Sync."""

    def priority(self) -> int:
        return 35

    def matches(self, ctx: PlanningContext) -> bool:
        return "forms" in ctx.services and _is_forms_sync_request(ctx.lowered)

    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan:
        tasks = agent._forms_sync_tasks(ctx.text, ctx.lowered)
        return RequestPlan(
            raw_text=ctx.text,
            tasks=tasks,
            summary=f"Planned {len(tasks)} tasks: forms.create_form -> forms.batch_update",
            confidence=0.8,
            no_service_detected=False,
            source="heuristic",
        )


class CodeExecutionStrategy(PlanningStrategy):
    """Pattern L: Explicit Code Execution / Computation."""

    def priority(self) -> int:
        return 30

    def matches(self, ctx: PlanningContext) -> bool:
        return "code" in ctx.services or "computation" in ctx.services

    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan:
        if any(kw in ctx.lowered for kw in ("calculate", "compute", "prime", "sum", "script", "python")):
            generated_code = _generate_computation_code(ctx.lowered, ctx.text)
            tasks = [
                PlannedTask(
                    id="task-1",
                    service="code",
                    action="execute",
                    parameters={"code": generated_code},
                    reason="Direct computation request."
                )
            ]
            if "email" in ctx.lowered or "send" in ctx.lowered:
                recipient = _extract_email(ctx.text, default=ctx.config.default_recipient_email)
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
                raw_text=ctx.text,
                tasks=tasks,
                summary=f"Planned {len(tasks)} tasks: code.execute" + (" -> gmail.send_message" if len(tasks) > 1 else ""),
                confidence=0.8,
                no_service_detected=False,
                source="heuristic",
            )
        return None


class SlidesToEmailStrategy(PlanningStrategy):
    """Pattern J: Slides -> Email."""

    def priority(self) -> int:
        return 25

    def matches(self, ctx: PlanningContext) -> bool:
        return (
            "slides" in ctx.services
            and "gmail" in ctx.services
            and _is_slides_to_email_request(ctx.lowered)
        )

    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan:
        tasks = agent._slides_to_email_tasks(ctx.text, ctx.lowered)
        return RequestPlan(
            raw_text=ctx.text,
            tasks=tasks,
            summary=f"Planned {len(tasks)} tasks: slides.get_presentation -> gmail.send_message",
            confidence=0.8,
            no_service_detected=False,
            source="heuristic",
        )


class AdminToEmailStrategy(PlanningStrategy):
    """Pattern K: Admin -> Email."""

    def priority(self) -> int:
        return 20

    def matches(self, ctx: PlanningContext) -> bool:
        return (
            "admin" in ctx.services
            and "gmail" in ctx.services
            and any(kw in ctx.lowered for kw in ("reports", "activities", "logs", "audit"))
        )

    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan:
        tasks = agent._admin_to_email_tasks(ctx.text, ctx.lowered)
        return RequestPlan(
            raw_text=ctx.text,
            tasks=tasks,
            summary=f"Planned {len(tasks)} tasks: admin.list_activities -> gmail.send_message",
            confidence=0.8,
            no_service_detected=False,
            source="heuristic",
        )


class ContactsToEmailStrategy(PlanningStrategy):
    """Pattern L: Contacts -> Email."""

    def priority(self) -> int:
        return 15

    def matches(self, ctx: PlanningContext) -> bool:
        return (
            "contacts" in ctx.services
            and "gmail" in ctx.services
            and any(kw in ctx.lowered for kw in ("contacts", "people", "users", "directory", "members"))
        )

    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan:
        tasks = agent._contacts_to_email_tasks(ctx.text, ctx.lowered)
        return RequestPlan(
            raw_text=ctx.text,
            tasks=tasks,
            summary=f"Planned {len(tasks)} tasks: contacts.list_directory_people -> gmail.send_message",
            confidence=0.8,
            no_service_detected=False,
            source="heuristic",
        )


class ChatToEmailStrategy(PlanningStrategy):
    """Pattern M: Chat -> Email (skip when user explicitly wants to send a chat message)."""

    def priority(self) -> int:
        return 10

    def matches(self, ctx: PlanningContext) -> bool:
        _send_kw = ("send a message", "post a message", "send message", "post message")
        _has_send_intent = any(kw in ctx.lowered for kw in _send_kw)
        return (
            "chat" in ctx.services
            and "gmail" in ctx.services
            and any(kw in ctx.lowered for kw in ("spaces", "messages", "chat"))
            and not _has_send_intent
        )

    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan:
        tasks = agent._chat_to_email_tasks(ctx.text, ctx.lowered)
        return RequestPlan(
            raw_text=ctx.text,
            tasks=tasks,
            summary=f"Planned {len(tasks)} tasks: chat.list_spaces -> gmail.send_message",
            confidence=0.8,
            no_service_detected=False,
            source="heuristic",
        )


class ChatSendMessageStrategy(PlanningStrategy):
    """Pattern N: Chat Send Message (Heuristic Search for Space)."""

    def priority(self) -> int:
        return 5

    def matches(self, ctx: PlanningContext) -> bool:
        _send_kw = ("send a message", "post a message", "send message", "post message")
        _has_send_intent = any(kw in ctx.lowered for kw in _send_kw)
        return "chat" in ctx.services and _has_send_intent and "spaces/" not in ctx.lowered

    def execute(self, ctx: PlanningContext, agent: "WorkspaceAgentSystem") -> RequestPlan:
        tasks = agent._chat_send_message_tasks(ctx.text, ctx.lowered)
        return RequestPlan(
            raw_text=ctx.text,
            tasks=tasks,
            summary=f"Planned {len(tasks)} tasks: chat.list_spaces -> chat.send_message",
            confidence=0.8,
            no_service_detected=False,
            source="heuristic",
        )


# Strategy registry - ordered by priority (highest first)
_PLANNING_STRATEGIES: list[PlanningStrategy] = [
    WebSearchStrategy(),
    DriveMetadataOnlyStrategy(),
    DriveMetadataToEmailStrategy(),
    DriveToSheetsToEmailStrategy(),
    DriveToEmailStrategy(),
    DriveFolderUploadStrategy(),
    DriveFolderMoveStrategy(),
    DriveDeleteByNameStrategy(),
    GmailToSheetsStrategy(),
    SheetCreationStrategy(),
    GmailListAndGetStrategy(),
    SheetToEmailStrategy(),
    DocsToEmailStrategy(),
    FormsSyncStrategy(),
    CodeExecutionStrategy(),
    SlidesToEmailStrategy(),
    AdminToEmailStrategy(),
    ContactsToEmailStrategy(),
    ChatToEmailStrategy(),
    ChatSendMessageStrategy(),
]


def _plan_with_strategies(text: str, lowered: str, services: list[str], config: AppConfigModel, logger: logging.Logger, agent: "WorkspaceAgentSystem") -> RequestPlan | None:
    """Execute planning strategies in priority order.

    Returns the first matching strategy's plan, or None if no strategy matches.
    """
    ctx = PlanningContext(text=text, lowered=lowered, services=services, config=config, logger=logger)

    for strategy in sorted(_PLANNING_STRATEGIES, key=lambda s: s.priority(), reverse=True):
        if strategy.matches(ctx):
            logger.debug(f"Planning strategy matched: {strategy.__class__.__name__}")
            plan = strategy.execute(ctx, agent)
            if plan:
                return plan

    return None


# ============================================================================
# TYPE-SAFE PARAMETER HANDLING
# ============================================================================


class ParameterType(Enum):
    """Type-safe parameter types for magic string references."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"
    TASK_REFERENCE = "task_reference"  # e.g., {{task-1.id}}
    CONTEXT_REFERENCE = "context_reference"  # e.g., $last_export_file_content
    EMAIL = "email"
    FILE_ID = "file_id"
    SPREADSHEET_ID = "spreadsheet_id"
    DOCUMENT_ID = "document_id"


class TypedParameter:
    """Type-safe wrapper for parameters with validation.

    This class provides type safety for magic string references like
    $last_export_file_content, {{task-1.files[0].id}}, etc.
    """

    def __init__(
        self,
        value: Any,
        param_type: ParameterType,
        required: bool = True,
        default: Any = None,
        description: str = ""
    ):
        self.value = value
        self.param_type = param_type
        self.required = required
        self.default = default
        self.description = description

    def validate(self) -> bool:
        """Validate the parameter value against its type."""
        if self.value is None:
            if not self.required:
                self.value = self.default
                return True
            return False

        # Type validation
        if self.param_type == ParameterType.STRING:
            return isinstance(self.value, str)
        elif self.param_type == ParameterType.INTEGER:
            return isinstance(self.value, int)
        elif self.param_type == ParameterType.FLOAT:
            return isinstance(self.value, (int, float))
        elif self.param_type == ParameterType.BOOLEAN:
            return isinstance(self.value, bool)
        elif self.param_type == ParameterType.LIST:
            return isinstance(self.value, list)
        elif self.param_type == ParameterType.DICT:
            return isinstance(self.value, dict)
        elif self.param_type == ParameterType.EMAIL:
            return isinstance(self.value, str) and "@" in self.value
        elif self.param_type in (ParameterType.FILE_ID, ParameterType.SPREADSHEET_ID, ParameterType.DOCUMENT_ID):
            return isinstance(self.value, str) and len(self.value) >= 20
        elif self.param_type in (ParameterType.TASK_REFERENCE, ParameterType.CONTEXT_REFERENCE):
            # These are template strings that will be resolved at runtime
            return isinstance(self.value, str)

        return True

    def resolve(self, context: dict[str, Any]) -> Any:
        """Resolve template references against the provided context.

        Args:
            context: Dictionary containing task results and context variables

        Returns:
            Resolved value with proper type coercion
        """
        if not isinstance(self.value, str):
            return self.value

        # Resolve task references like {{task-1.id}}
        if "{{" in self.value and "}}" in self.value:
            from .execution.resolver import ResolverMixin
            # Create a temporary resolver instance to handle placeholder resolution
            class TempResolver(ResolverMixin):
                def __init__(self):
                    self.logger = logging.getLogger(__name__)
                    self.config = None
                    self.runner = None

            resolver = TempResolver()
            resolved = resolver._resolve_placeholders(self.value, context)
            self.value = resolved

        # Resolve context references like $last_export_file_content
        elif self.value.startswith("$"):
            key = self.value[1:]  # Remove $ prefix
            if key in context:
                self.value = context[key]
            elif self.required and self.default is not None:
                self.value = self.default
                logging.getLogger(__name__).warning(
                    "Context key '%s' not found, using default value", key
                )

        return self.value


# Common context keys with their expected types
CONTEXT_KEY_TYPES: dict[str, ParameterType] = {
    "last_export_file_content": ParameterType.STRING,
    "gmail_message_ids": ParameterType.LIST,
    "last_spreadsheet_id": ParameterType.SPREADSHEET_ID,
    "last_document_id": ParameterType.DOCUMENT_ID,
    "last_file_id": ParameterType.FILE_ID,
    "drive_file_ids": ParameterType.LIST,
    "last_spreadsheet_url": ParameterType.STRING,
    "last_document_url": ParameterType.STRING,
    "last_code_result": ParameterType.STRING,
    "code_output": ParameterType.STRING,
    "drive_summary_values": ParameterType.LIST,
    "gmail_summary_values": ParameterType.LIST,
    "search_summary_rows": ParameterType.LIST,
}


def validate_typed_parameters(parameters: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Validate and resolve typed parameters.

    Args:
        parameters: Dictionary of parameter names to TypedParameter instances or raw values
        context: Execution context containing task results and variables

    Returns:
        Validated and resolved parameters dictionary

    Raises:
        ValueError: If a required parameter fails validation
    """
    resolved_params = {}
    logger = logging.getLogger(__name__)

    for key, value in parameters.items():
        if isinstance(value, TypedParameter):
            # Resolve template references
            resolved_value = value.resolve(context)

            # Validate type
            if not value.validate():
                if value.required:
                    raise ValueError(
                        f"Parameter '{key}' failed validation. "
                        f"Expected type: {value.param_type.value}, "
                        f"Got: {type(resolved_value).__name__}. "
                        f"Description: {value.description}"
                    )
                else:
                    logger.warning(
                        "Optional parameter '%s' failed validation, using default", key
                    )
                    resolved_value = value.default

            resolved_params[key] = resolved_value
        else:
            # Raw value - pass through as-is (backward compatibility)
            resolved_params[key] = value

    return resolved_params
