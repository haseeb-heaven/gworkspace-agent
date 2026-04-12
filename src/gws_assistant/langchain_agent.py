"""LangChain-backed planning and reasoning agent."""

import logging
import time
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from .models import RequestPlan, PlannedTask, AppConfigModel
from .service_catalog import SERVICES

_DEFAULT_CONFIDENCE = 0.9

# Flat JSON schema for RequestPlan that avoids Pydantic default_factory serialization
# warnings and provider incompatibilities with with_structured_output.
_REQUEST_PLAN_SCHEMA = {
    "name": "RequestPlan",
    "description": "A sequential plan of Google Workspace tasks.",
    "parameters": {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "description": "Ordered list of tasks to execute.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "service": {"type": "string"},
                        "action": {"type": "string"},
                        "parameters": {"type": "object"},
                        "reason": {"type": "string"},
                    },
                    "required": ["id", "service", "action"],
                },
            },
            "summary": {"type": "string"},
            "confidence": {"type": "number"},
            "no_service_detected": {"type": "boolean"},
        },
        "required": ["tasks"],
    },
}

# Keywords that signal the user wants an email to be sent.
_EMAIL_SEND_KEYWORDS = (
    "send email", "send invoice", "send mail", "email me", "mail me",
    "send me", "invoice email", "send a mail", "send an email", "email to",
)


def _request_requires_send_email(text: str) -> bool:
    """Return True when the user request clearly asks for an outgoing email."""
    lowered = text.lower()
    return any(kw in lowered for kw in _EMAIL_SEND_KEYWORDS)


def _plan_has_send_task(tasks: list[dict]) -> bool:
    """Return True when at least one task in the raw task list is a gmail send."""
    for t in tasks:
        if not isinstance(t, dict):
            continue
        if t.get("service") == "gmail" and t.get("action") == "send_message":
            return True
    return False


def create_agent(config: AppConfigModel, logger: logging.Logger) -> ChatOpenAI | None:
    try:
        return ChatOpenAI(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=0,
        )
    except Exception as e:
        logger.error(f"Failed to create ChatOpenAI agent: {e}")
        return None


def plan_with_langchain(text: str, config: AppConfigModel, logger: logging.Logger,
                        memory_hint: str = "") -> RequestPlan | None:
    """Uses a Chat model with structured output to plan Workspace tasks.

    Uses a hand-crafted JSON schema instead of Pydantic model introspection to
    avoid 'NoneType not iterable' errors caused by default_factory fields that
    some providers cannot serialize.
    """
    model = create_agent(config, logger)
    if not model:
        return None

    # Convert catalog to a concise summary for the prompt
    catalog_lines = []
    for s_key, s_spec in SERVICES.items():
        actions_str = ", ".join(s_spec.actions.keys())
        catalog_lines.append(f"- {s_key} ({s_spec.label}): {actions_str}")
    catalog_summary = "\n".join(catalog_lines)

    system_prompt = (
        "You are an expert Google Workspace automation planner. "
        "Break down the user's request into a sequential plan of discrete tasks using the available services.\n\n"
        "AVAILABLE SERVICES AND ACTIONS:\n"
        f"{catalog_summary}\n\n"
        "RULES:\n"
        "1. SEQUENTIAL PLAN: Provide a list of tasks. Tasks can refer to previous outputs using {{task_id.key}}.\n"
        "   IMPORTANT: Always use the double-brace form {{task_id.key}} (e.g. {{4.spreadsheetId}}) for cross-step\n"
        "   references. NEVER write bare step references like '4.id' as a literal parameter value.\n"
        "2. EMAIL DETAILS: For Gmail, ALWAYS follow gmail.list_messages with gmail.get_message if details are needed. "
        "Pass 'q' to list_messages, then omit 'id' on get_message (the executor will automatically resolve it).\n"
        "3. EXPORTS: For Drive exports (Docs/Sheets), ALWAYS call drive.export_file. Do NOT use Docs/Sheets APIs for exporting.\n"
        "4. WEB SEARCH: If the user asks for information not in their Workspace (e.g. 'Top 3 AI frameworks'), use search.web_search first.\n"
        "   After a web search, ALWAYS use the $web_search_table_values placeholder for cell values — do NOT write\n"
        "   natural-language extraction instructions (e.g. 'extract rate from search result 6') as cell values.\n"
        "   Use only concrete values or the $web_search_* placeholder tokens.\n"
        "5. PARAMETER BINDING: The system automatically links 'id', 'spreadsheet_id', and 'document_id' between sequential tasks.\n"
        "6. DO NOT invent services or actions that are not in the catalog. Use ONLY what is provided.\n"
        "7. If a request asks for both supported and unsupported services, create tasks ONLY for the supported ones, and ignore the unsupported ones. Do NOT set no_service_detected=true if AT LEAST ONE supported service can be used.\n"
        "8. PIPELINE ENFORCEMENT: For complex workflows, prefer the sequence: web_search -> summarize_results -> docs.create_document -> sheets.append_values -> gmail.send_message.\n"
        "9. SEND EMAIL REQUIREMENT: If the user request contains any intent to send an email (keywords: send email,\n"
        "   send invoice, email me, mail me, send me, invoice email, email to), you MUST include a gmail.send_message\n"
        "   task as the LAST step. Its 'to_email' should be the address mentioned by the user. Its 'body' should\n"
        "   reference $sheet_email_body or $web_search_markdown as appropriate. This step is MANDATORY and must\n"
        "   not be omitted."
    )

    if memory_hint:
        system_prompt = (
            "Relevant past task context:\n"
            f"{memory_hint}\n\n"
            f"{system_prompt}"
        )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "{request}")
    ])

    max_retries = 3
    plan_data: Any = None
    for attempt in range(max_retries):
        try:
            # Use the hand-crafted schema to avoid Pydantic default_factory
            # serialization issues ('NoneType' not iterable on some providers).
            chain = prompt | model.with_structured_output(_REQUEST_PLAN_SCHEMA)
            plan_data = chain.invoke(
                 {"request": text},
                 config=RunnableConfig(metadata={"timeout": config.timeout_seconds})
            )
            break
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                logger.warning(f"LLM rate limited (attempt {attempt+1}/{max_retries}). Retrying in 2s...")
                time.sleep(2)
                continue
            logger.error("LangChain planning failed: %s", e)
            return None

    if plan_data is None:
        logger.warning("LLM planning returned None.")
        return None

    # The schema always returns a dict — normalise it into a RequestPlan.
    if isinstance(plan_data, dict):
        tasks_data = plan_data.get("tasks")
        if not isinstance(tasks_data, list):
            tasks_data = []

        # ------------------------------------------------------------------ #
        # BUG FIX 3: Ensure gmail.send_message is present when the user       #
        # explicitly requested sending an email.  The LLM sometimes drops it  #
        # silently.  We inject a minimal fallback task when it is missing.    #
        # ------------------------------------------------------------------ #
        if _request_requires_send_email(text) and not _plan_has_send_task(tasks_data):
            logger.warning(
                "BugFix3: gmail.send_message missing from plan despite send-email intent. "
                "Injecting fallback send_message task."
            )
            # Determine next task ID
            next_id = f"task-{len(tasks_data) + 1}"
            # Try to extract destination address from the request text
            email_re = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
            match = email_re.search(text)
            to_addr = match.group(0) if match else "$user_email"
            tasks_data.append({
                "id": next_id,
                "service": "gmail",
                "action": "send_message",
                "parameters": {
                    "to_email": to_addr,
                    "subject": "Your Workspace Summary",
                    "body": "$sheet_email_body",
                },
                "reason": "User explicitly requested sending an email — auto-injected by BugFix3.",
            })

        tasks = []
        for t in tasks_data:
            if isinstance(t, dict):
                tasks.append(PlannedTask(
                    id=str(t.get("id", f"task-{len(tasks)+1}")),
                    service=str(t.get("service", "")),
                    action=str(t.get("action", "")),
                    parameters=t.get("parameters") or {},
                    reason=str(t.get("reason", ""))
                ))
        return RequestPlan(
            raw_text=text,
            tasks=tasks,
            summary=str(plan_data.get("summary", "Generated Workspace Plan")),
            confidence=float(plan_data.get("confidence") or _DEFAULT_CONFIDENCE),
            no_service_detected=bool(plan_data.get("no_service_detected", False)),
            source="langchain"
        )

    # Pydantic object path (some providers return a typed object despite the schema).
    if hasattr(plan_data, "confidence") and plan_data.confidence == 0.0:
        plan_data.confidence = _DEFAULT_CONFIDENCE

    return plan_data


import re  # noqa: E402  (needed for BugFix3 email regex above)
