"""LangChain-backed planning and reasoning agent."""

import logging
import re
import time
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

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

# Priority-ordered $-placeholders for the fallback email body.
_EMAIL_BODY_PLACEHOLDERS = (
    "$last_code_stdout",
    "$sheet_email_body",
    "$gmail_summary_values",
    "$web_search_markdown",
)

# ---------------------------------------------------------------------------
# Model fallback chain
# When the primary model is rate-limited (HTTP 429 quota exhausted) the
# planner tries each model in this list in order until one succeeds.
# All models are OpenRouter-compatible free/cheap endpoints.
# ---------------------------------------------------------------------------
_MODEL_FALLBACK_CHAIN: list[str] = [
    "google/gemini-flash-1.5",
    "meta-llama/llama-3.1-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "microsoft/phi-3-mini-128k-instruct:free",
]

# Backoff schedule for 429 retries (seconds).  Index = attempt number (0-based).
_BACKOFF_SCHEDULE: list[float] = [2.0, 4.0, 8.0, 16.0, 30.0]


def _backoff_delay(attempt: int) -> float:
    """Return the back-off delay for the given zero-based attempt index."""
    return _BACKOFF_SCHEDULE[min(attempt, len(_BACKOFF_SCHEDULE) - 1)]


def _is_rate_limit_error(exc: Exception) -> bool:
    """Return True when exc represents an HTTP 429 / quota-exceeded response."""
    msg = str(exc)
    return "429" in msg or "rate limit" in msg.lower() or "quota" in msg.lower()


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
    """Derive a new task ID that matches the naming convention used by the LLM."""
    n = len(tasks_data) + 1
    if tasks_data and isinstance(tasks_data[0].get("id"), str):
        first_id = tasks_data[0]["id"]
        if not first_id.startswith("task-"):
            return str(n)
    return f"task-{n}"


def _derive_email_subject(request_text: str) -> str:
    """Infer a concise, generic email subject from the user's request text."""
    cleaned = re.sub(
        r"(?i)^(please\s+)?(send|email|mail|forward|share|get|fetch|find|show|give\s+me)\s+(an?\s+)?",
        "",
        request_text.strip(),
    )
    cleaned = re.sub(r"\s+to\s+[\w.+-]+@[\w-]+\.[\w.]+.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" .,;:")
    if not cleaned:
        return "Your Requested Summary"
    subject = cleaned[0].upper() + cleaned[1:]
    if len(subject) > 60:
        subject = subject[:57].rstrip() + "..."
    return subject


def _derive_email_body_placeholder(tasks_data: list[dict]) -> str:
    """Choose the most appropriate $-placeholder for the fallback email body."""
    services_used = {t.get("service", "") for t in tasks_data if isinstance(t, dict)}
    if "code" in services_used or "computation" in services_used:
        return "$last_code_stdout"
    if "sheets" in services_used:
        return "$sheet_email_body"
    if "gmail" in services_used:
        return "$gmail_summary_values"
    if "search" in services_used:
        return "$web_search_markdown"
    return "Here are the results of your Google Workspace request."


def _safe_invoke_structured_output(
    chain: Any,
    request: dict,
    logger: logging.Logger,
) -> Any:
    """Invoke a structured-output chain, returning None on parse failures.

    IMPORTANT: HTTP 429 rate-limit errors are RE-RAISED so the caller's
    retry/fallback loop can handle them with proper back-off.  All other
    unexpected errors are swallowed and None is returned.
    """
    try:
        return chain.invoke(request)
    except TypeError as exc:
        logger.warning("Structured output parse error (TypeError): %s", exc)
        return None
    except ValueError as exc:
        logger.warning("Structured output parse error (ValueError): %s", exc)
        return None
    except Exception as exc:
        if _is_rate_limit_error(exc):
            # Re-raise so the outer retry loop can back off and/or switch models.
            raise
        logger.warning("Structured output unexpected error: %s", exc)
        return None


def create_agent(config: AppConfigModel, logger: logging.Logger, model_override: str | None = None) -> ChatOpenAI | None:
    """Create and return a ChatOpenAI agent for the given config, or None on failure.

    Args:
        config: Application config (contains api_key, base_url, default model).
        logger: Logger instance.
        model_override: If provided, use this model name instead of config.model.
    """
    try:
        return ChatOpenAI(
            model=model_override or config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=0,
        )
    except Exception as e:
        logger.error("Failed to create ChatOpenAI agent: %s", e)
        return None


def _invoke_with_backoff(
    model_name: str,
    config: AppConfigModel,
    prompt: Any,
    request_text: str,
    logger: logging.Logger,
    max_retries: int = 3,
) -> Any:
    """Try to invoke the planner chain on a specific model with exponential back-off.

    Returns the raw plan_data dict on success, or None if all retries fail due
    to parse errors.  Raises the last exception if all retries hit 429.
    """
    last_exc: Exception | None = None
    model = create_agent(config, logger, model_override=model_name)
    if not model:
        return None

    for attempt in range(max_retries):
        try:
            chain = prompt | model.with_structured_output(_REQUEST_PLAN_SCHEMA)
            result = _safe_invoke_structured_output(chain, {"request": request_text}, logger)
            if result is not None:
                return result
            # Parse returned None (not a 429) — retry up to max_retries
            if attempt < max_retries - 1:
                logger.warning(
                    "Model '%s': structured output None on attempt %d/%d — retrying.",
                    model_name, attempt + 1, max_retries,
                )
                time.sleep(1)
        except Exception as exc:
            last_exc = exc
            if _is_rate_limit_error(exc):
                delay = _backoff_delay(attempt)
                logger.warning(
                    "Model '%s' rate-limited (attempt %d/%d, HTTP 429). "
                    "Backing off %.0fs before retry.",
                    model_name, attempt + 1, max_retries, delay,
                )
                if attempt < max_retries - 1:
                    time.sleep(delay)
                    continue
                # All retries exhausted on this model — propagate so caller switches.
                raise
            logger.error("Model '%s' planning failed: %s", model_name, exc)
            return None

    return None


def plan_with_langchain(
    text: str,
    config: AppConfigModel,
    logger: logging.Logger,
    memory_hint: str = "",
) -> RequestPlan | None:
    """Generate a RequestPlan via LangChain with automatic model fallback on 429.

    Execution order:
    1. Try primary model (config.model) with up to 3 retries + exponential back-off.
    2. On exhaustion, iterate through _MODEL_FALLBACK_CHAIN, trying each with the
       same retry/back-off policy.
    3. If every model is exhausted, return None so the heuristic planner takes over.
    """
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
        "9. CODE EXECUTOR OUTPUT: When a 'code' task computes values (e.g. totals, conversions), the next sheets.append_values\n"
        "   task MUST use the token $last_code_result (for a single scalar) or PLACEHOLDER_AMOUNT as the cell value.\n"
        "   Do NOT write literal strings like 'PLACEHOLDER_AMOUNT' — the executor resolves them automatically.\n"
        "   For the email body referencing code output, use $last_code_stdout.\n"
        "10. MULTIPLE SHEET TABS: If writing results to multiple tabs, name the ranges explicitly (e.g. 'Tab1!A1:C10',\n"
        "   'Tab2!A1:C10'). Do NOT reuse 'Sheet1!A1' for multiple writes targeting different tabs.\n"
        "11. SEND EMAIL REQUIREMENT: If the user request mentions sending an email, you MUST include a\n"
        "   gmail.send_message task as the LAST step. Set 'to_email' to the EXACT address the user stated\n"
        "   (e.g. <recipient@example.com>). Do NOT use a receipt/invoice sender address. Choose the most\n"
        "   appropriate body placeholder ($last_code_stdout, $sheet_email_body, $gmail_summary_values, or\n"
        "   $web_search_markdown) based on the preceding tasks. This step is MANDATORY and must not be omitted."
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

    # Build the ordered list of models to try: primary first, then fallbacks.
    primary_model = config.model or ""
    models_to_try: list[str] = [primary_model] + [
        m for m in _MODEL_FALLBACK_CHAIN if m != primary_model
    ]

    plan_data: Any = None
    for model_idx, model_name in enumerate(models_to_try):
        is_fallback = model_idx > 0
        if is_fallback:
            logger.warning(
                "Primary model '%s' exhausted. Trying fallback model %d/%d: '%s'.",
                primary_model, model_idx, len(models_to_try) - 1, model_name,
            )
        try:
            plan_data = _invoke_with_backoff(
                model_name=model_name,
                config=config,
                prompt=prompt,
                request_text=text,
                logger=logger,
            )
        except Exception as exc:
            if _is_rate_limit_error(exc):
                logger.warning(
                    "Model '%s' rate-limited and all retries exhausted. "
                    "Moving to next fallback.", model_name,
                )
                continue
            logger.error("Model '%s' raised unexpected error: %s", model_name, exc)
            continue

        if plan_data is not None:
            if is_fallback:
                logger.warning(
                    "Plan generated successfully using fallback model '%s'.", model_name
                )
            break

    if plan_data is None:
        logger.warning(
            "LLM planning returned None after trying %d model(s): %s",
            len(models_to_try),
            ", ".join(models_to_try),
        )
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

        # Only inject the fallback send task when we have a valid explicit address.
        if _request_requires_send_email(text) and not _plan_has_send_task(tasks_data):
            if explicit_email:
                subject = _derive_email_subject(text)
                body_placeholder = _derive_email_body_placeholder(tasks_data)
                logger.warning(
                    "BugFix3: gmail.send_message missing from plan. "
                    "Injecting fallback task to '%s' (subject='%s', body='%s').",
                    explicit_email, subject, body_placeholder,
                )
                next_id = _derive_next_task_id(tasks_data)
                tasks_data.append({
                    "id": next_id,
                    "service": "gmail",
                    "action": "send_message",
                    "parameters": {
                        "to_email": explicit_email,
                        "subject": subject,
                        "body": body_placeholder,
                    },
                    "reason": "User explicitly requested sending an email — auto-injected by BugFix3.",
                })
            else:
                logger.warning(
                    "BugFix3: send email intent detected but no explicit address found in request; "
                    "skipping gmail.send_message injection to avoid unresolvable placeholder."
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
