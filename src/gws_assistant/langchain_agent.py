"""LangChain-backed planning and reasoning agent."""

import logging
import re
import time
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from .models import RequestPlan, PlannedTask, AppConfigModel
from .service_catalog import SERVICES

_DEFAULT_CONFIDENCE = 0.9

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

# Keywords that signal the user wants an outgoing email sent.
_EMAIL_SEND_KEYWORDS = (
    "send email", "send invoice", "send mail", "email me", "mail me",
    "send me", "invoice email", "send a mail", "send an email", "email to",
)


def _request_requires_send_email(text: str) -> bool:
    """Return True if the request text contains an email-send intent keyword."""
    lowered = text.lower()
    return any(kw in lowered for kw in _EMAIL_SEND_KEYWORDS)


def _plan_has_send_task(tasks: list[dict]) -> bool:
    """Return True if any task in the plan is a gmail.send_message action."""
    for t in tasks:
        if not isinstance(t, dict):
            continue
        if t.get("service") == "gmail" and t.get("action") == "send_message":
            return True
    return False


def _extract_explicit_email(text: str) -> str:
    """Return the first explicit e-mail address present in the user request text."""
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    return m.group(0) if m else ""


def _derive_next_task_id(tasks_data: list[dict]) -> str:
    """Derive a new task ID that matches the naming convention used by the LLM.

    If the LLM used plain numeric IDs (``'1'``, ``'2'``, ...) the new ID will
    also be numeric.  If it used ``'task-N'`` prefixes, the new ID matches that
    form.  Falls back to ``'task-N'`` when the list is empty or the first ID
    is in an unexpected format.
    """
    n = len(tasks_data) + 1
    if tasks_data and isinstance(tasks_data[0].get("id"), str):
        first_id = tasks_data[0]["id"]
        if not first_id.startswith("task-"):
            # LLM used plain numeric IDs — match that convention
            return str(n)
    return f"task-{n}"


def create_agent(config: AppConfigModel, logger: logging.Logger) -> ChatOpenAI | None:
    """Create and return a ChatOpenAI agent, or None on failure."""
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
    """Generate a RequestPlan from the user's natural-language request via LangChain."""
    model = create_agent(config, logger)
    if not model:
        return None

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
        "   natural-language extraction instructions as cell values.\n"
        "5. PARAMETER BINDING: The system automatically links 'id', 'spreadsheet_id', and 'document_id' between sequential tasks.\n"
        "6. DO NOT invent services or actions that are not in the catalog.\n"
        "7. If a request asks for both supported and unsupported services, create tasks ONLY for the supported ones.\n"
        "8. PIPELINE ENFORCEMENT: For complex workflows, prefer the sequence: web_search -> code -> sheets.append_values -> gmail.send_message.\n"
        "9. CODE EXECUTOR OUTPUT: When a 'code' task computes values (e.g. USD/INR totals), the next sheets.append_values\n"
        "   task MUST use the token $last_code_result (for a single scalar) or PLACEHOLDER_AMOUNT as the cell value.\n"
        "   Do NOT write literal strings like 'PLACEHOLDER_AMOUNT' — the executor resolves them automatically.\n"
        "   For the email body referencing code output, use $last_code_stdout.\n"
        "10. MULTIPLE SHEET TABS: If writing USD results to one tab and INR results to another, name the ranges\n"
        "   explicitly: 'USD!A1:C10' and 'INR!A1:C10'. Do NOT reuse 'Sheet1!A1' for both writes.\n"
        "11. SEND EMAIL REQUIREMENT: If the user request mentions sending an email, you MUST include a\n"
        "   gmail.send_message task as the LAST step. Set 'to_email' to the EXACT address the user stated\n"
        "   (e.g. 'haseebmir.hm@gmail.com'). Do NOT use a receipt/invoice sender address. Use $last_code_stdout\n"
        "   as the body. This step is MANDATORY and must not be omitted."
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

    if isinstance(plan_data, dict):
        tasks_data = plan_data.get("tasks")
        if not isinstance(tasks_data, list):
            tasks_data = []

        explicit_email = _extract_explicit_email(text)

        # Fix any existing send_message tasks that have a bad to_email
        for t in tasks_data:
            if not isinstance(t, dict):
                continue
            if t.get("service") == "gmail" and t.get("action") == "send_message":
                params = t.get("parameters") or {}
                to_addr = str(params.get("to_email") or "").strip()
                if explicit_email and (not to_addr or "@" not in to_addr or
                        re.search(r"(noreply|no-reply|invoice|receipt|stripe|paypal|x\.com|twitter)",
                                  to_addr, re.IGNORECASE)):
                    params["to_email"] = explicit_email
                    t["parameters"] = params
                    logger.info("BugFixC: corrected to_email in planned task to '%s'", explicit_email)

        # CR-2 / CR-3: Only inject the fallback send task when we have a valid address.
        # Skipping injection entirely is safer than passing an unresolvable '$user_email'.
        if _request_requires_send_email(text) and not _plan_has_send_task(tasks_data):
            if explicit_email:
                logger.warning(
                    "BugFix3: gmail.send_message missing from plan. Injecting fallback task to '%s'.",
                    explicit_email,
                )
                # CR-3: match the ID convention of the existing tasks
                next_id = _derive_next_task_id(tasks_data)
                tasks_data.append({
                    "id": next_id,
                    "service": "gmail",
                    "action": "send_message",
                    "parameters": {
                        "to_email": explicit_email,
                        "subject": "Your Twitter/X Subscription Invoice Summary",
                        "body": "$last_code_stdout",
                    },
                    "reason": "User explicitly requested sending an email — auto-injected by BugFix3.",
                })
            else:
                logger.warning(
                    "BugFix3: send email intent detected but no explicit address found in request; "
                    "skipping gmail.send_message injection to avoid unresolvable $user_email."
                )

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

    if hasattr(plan_data, "confidence") and plan_data.confidence == 0.0:
        plan_data.confidence = _DEFAULT_CONFIDENCE

    return plan_data
