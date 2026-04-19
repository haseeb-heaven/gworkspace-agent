"""LangChain-backed planning and reasoning agent."""

import datetime
import logging
import re
import time
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from .models import AppConfigModel, PlannedTask, RequestPlan
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
                        "service": {
                            "type": "string",
                            "description": "The service key (e.g. 'gmail', 'sheets').",
                        },
                        "action": {
                            "type": "string",
                            "description": "The action key (e.g. 'send_message').",
                        },
                        "parameters": {
                            "type": "object",
                            "description": "Key-value pairs for the action. MUST include all required parameters from the catalog.",
                            "additionalProperties": True
                        },
                        "reason": {"type": "string"},
                    },
                    "required": ["id", "service", "action", "parameters"],
                },
            },
            "summary": {"type": "string"},
            "confidence": {"type": "number"},
            "no_service_detected": {"type": "boolean"},
        },
        "required": ["tasks"],
    },
}

_EMAIL_SEND_KEYWORDS = (
    "send email", "send invoice", "send mail", "email me", "mail me",
    "send me", "invoice email", "send a mail", "send an email", "email to",
)

_EMAIL_BODY_PLACEHOLDERS = (
    "$last_code_stdout",
    "$sheet_email_body",
    "$gmail_summary_values",
    "$web_search_markdown",
)

# ---------------------------------------------------------------------------
# Model fallback chain — updated to currently-available OpenRouter endpoints.
# ---------------------------------------------------------------------------
_MODEL_FALLBACK_CHAIN: list[str] = [
    "qwen/qwen3-coder:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemini-2.0-flash-exp:free",
    "deepseek/deepseek-r1:free",
    "openrouter/free",
]

_BACKOFF_SCHEDULE: list[float] = [2.0, 4.0, 8.0, 16.0, 30.0]


def _backoff_delay(attempt: int) -> float:
    return _BACKOFF_SCHEDULE[min(attempt, len(_BACKOFF_SCHEDULE) - 1)]


def _is_rate_limit_error(exc: Exception) -> bool:
    msg = str(exc)
    return "429" in msg or "rate limit" in msg.lower() or "quota" in msg.lower()


def _is_endpoint_missing_error(exc: Exception) -> bool:
    """Return True for HTTP 404 'No endpoints found' from OpenRouter."""
    msg = str(exc)
    return "404" in msg or "no endpoints found" in msg.lower()


def _request_requires_send_email(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in _EMAIL_SEND_KEYWORDS)


def _plan_has_send_task(tasks: list[dict]) -> bool:
    for t in tasks:
        if not isinstance(t, dict):
            continue
        if t.get("service") == "gmail" and t.get("action") == "send_message":
            return True
    return False


def _extract_explicit_email(text: str) -> str:
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    return m.group(0) if m else ""


def _derive_next_task_id(tasks_data: list[dict]) -> str:
    n = len(tasks_data) + 1
    if tasks_data and isinstance(tasks_data[0].get("id"), str):
        first_id = tasks_data[0]["id"]
        if not first_id.startswith("task-"):
            return str(n)
    return f"task-{n}"


def _derive_email_subject(request_text: str) -> str:
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


def is_valid_plan(plan_data: Any) -> bool:
    """Validate that every task in the LLM plan has a known service and action,
    and that all required parameters are present.

    Returns False (invalid) if:
    - plan_data is not a dict
    - 'tasks' is missing, None, or not a list
    - any task has a service/action not present in the catalog
    - any task is missing a REQUIRED parameter from the catalog
    """
    if not isinstance(plan_data, dict):
        return False
    tasks = plan_data.get("tasks")
    if not isinstance(tasks, list) or len(tasks) == 0:
        return False

    for t in tasks:
        if not isinstance(t, dict):
            return False
        service = str(t.get("service") or "").strip().lower()
        action = str(t.get("action") or "").strip()

        if service not in SERVICES:
            return False

        if "." in action:
            prefix, actual_action = action.split(".", 1)
            if prefix.lower() == service:
                action = actual_action
                t["action"] = action

        action_spec = SERVICES[service].actions.get(action)
        if not action_spec:
            return False

        # Validate required parameters.
        # We check both the 'parameters' dict and the task root (LLM often flattens).
        provided_keys = set((t.get("parameters") or {}).keys())
        provided_keys.update(k for k in t.keys() if k not in ("id", "service", "action", "parameters", "reason"))

        for p_spec in action_spec.parameters:
            if p_spec.required:
                # Check for exact match or common case/underscore variations.
                norm_p_name = p_spec.name.lower().replace("_", "")
                found = False
                for k in provided_keys:
                    if k.lower().replace("_", "") == norm_p_name:
                        found = True
                        break
                if not found:
                    logging.info("Plan invalid: task %s.%s missing required parameter '%s'", service, action, p_spec.name)
                    return False
    return True


def _safe_invoke_structured_output(
    chain: Any,
    request: dict,
    logger: logging.Logger,
) -> Any:
    """Invoke a structured-output chain, returning None on parse failures.

    HTTP 429 and HTTP 404 are RE-RAISED so the caller's retry/fallback loop
    can handle them. All other unexpected errors are swallowed -> None.
    """
    try:
        return chain.invoke(request)
    except TypeError as exc:
        logger.info("Structured output parse error (TypeError): %s", exc)
        return None
    except ValueError as exc:
        logger.info("Structured output parse error (ValueError): %s", exc)
        return None
    except Exception as exc:
        if _is_rate_limit_error(exc) or _is_endpoint_missing_error(exc):
            raise
        logger.info("Structured output unexpected error: %s", exc)
        return None


def create_agent(
    config: AppConfigModel,
    logger: logging.Logger,
    model_override: str | None = None,
) -> ChatOpenAI | None:
    api_key = config.api_key
    if not api_key or not str(api_key).strip():
        logger.warning("create_agent: API key is missing or empty. Cannot create ChatOpenAI agent.")
        return None

    try:
        return ChatOpenAI(
            model=model_override or config.model,
            api_key=api_key,  # type: ignore[arg-type]
            base_url=config.base_url,
            temperature=0,
        )
    except Exception as e:
        logger.error("Failed to create ChatOpenAI agent: %s", e)
        return None


def _build_catalog_prompt() -> str:
    """Build a rich, LLM-readable catalog section from service_catalog descriptions.

    Format per action:
      - service_key.action_key — short description
        params: param1 (required), param2 (optional)

    This replaces the old bare 'service_key: action1, action2' listing which
    gave the LLM no guidance on what each action does or what parameters it needs.
    """
    lines: list[str] = []
    for s_key, s_spec in SERVICES.items():
        svc_desc = f" — {s_spec.description}" if s_spec.description else ""
        lines.append(f"[{s_key}]{svc_desc}")
        for a_key, a_spec in s_spec.actions.items():
            act_desc = f" — {a_spec.description}" if a_spec.description else ""
            param_parts = []
            for p in a_spec.parameters:
                flag = "required" if p.required else "optional"
                param_parts.append(f"{p.name} ({flag}, e.g. {p.example!r})")
            param_str = ", ".join(param_parts) if param_parts else "no parameters"
            lines.append(f"  {s_key}.{a_key}{act_desc}")
            lines.append(f"    params: {param_str}")
    return "\n".join(lines)


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
    to parse errors or invalid plans. Raises on persistent 429 or immediately on 404.
    """
    for attempt in range(max_retries):
        model = create_agent(config, logger, model_override=model_name)
        if not model:
            logger.warning("create_agent returned None for model '%s'", model_name)
            return None
            
        try:
            chain = prompt | model.with_structured_output(_REQUEST_PLAN_SCHEMA)
            result = _safe_invoke_structured_output(chain, {"request": request_text}, logger)

            if result is not None and not is_valid_plan(result):
                logger.info(
                    "Model '%s': plan failed validation on attempt %d/%d. Raw: %s",
                    model_name, attempt + 1, max_retries, result,
                )
                result = None

            if result is not None:
                logger.info("Model '%s' succeeded on attempt %d", model_name, attempt + 1)
                return result

            if attempt < max_retries - 1:
                logger.info(
                    "Model '%s': structured output None/invalid on attempt %d/%d — retrying.",
                    model_name, attempt + 1, max_retries,
                )
                time.sleep(1)
        except Exception as exc:
            if _is_endpoint_missing_error(exc):
                logger.info("Model '%s': endpoint missing (404) — skipping.", model_name)
                raise
            if _is_rate_limit_error(exc):
                delay = _backoff_delay(attempt)
                if attempt < max_retries - 1:
                    logger.info(
                        "Model '%s' rate-limited (attempt %d/%d, HTTP 429). "
                        "Rotating API key and backing off %.0fs before retry.",
                        model_name, attempt + 1, max_retries, delay,
                    )
                    config.rotate_api_key()
                    time.sleep(delay)
                    continue
                else:
                    logger.info("Model '%s' rate-limited and retries exhausted.", model_name)
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
    """Generate a RequestPlan via LangChain with automatic model fallback.

    Execution order:
    1. Try primary model (config.model) with up to 3 retries + exponential back-off.
    2. On exhaustion or 404, iterate through _MODEL_FALLBACK_CHAIN.
    3. Each candidate plan is validated by is_valid_plan() before acceptance.
    4. If every model is exhausted, return None so the heuristic planner takes over.
    """
    catalog_summary = _build_catalog_prompt()

    # Bug D fix: quadruple-escape all braces to '{{{{' / '}}}}'
    catalog_summary_escaped = catalog_summary.replace("{", "{{{{").replace("}", "}}}}")

    system_prompt = (
        "You are an expert Google Workspace automation planner. "
        "Break down the user's request into a sequential plan of discrete tasks using ONLY "
        "the services and actions listed in the catalog below.\n\n"
        "AVAILABLE SERVICES, ACTIONS, AND PARAMETERS:\n"
        f"{catalog_summary_escaped}\n\n"
        f"CURRENT CONTEXT: Today is {datetime.date.today().isoformat()}\n\n"
        "STRICT RULES:\n"
        "1. ONLY use service keys and action keys EXACTLY as listed in the catalog above. "
        "2. PARAMETERS: provide a 'parameters' object containing ALL 'required' parameters. "
        "3. PYTHON CODE: in code.execute, write standard, valid Python. "
        "4. SEQUENTIAL PLAN: reference prior outputs with {{{{task-N.field}}}}. "
        "5. BULK OPERATIONS: use placeholder for task ID to auto-expand. "
        "6. DRIVE QUERIES: use 'q' parameter for drive.list_files. "
        "7. EMAIL ACTIONS: use gmail.send_message for sending. "
        "8. EXPORTS: use drive.export_file to read content. "
        "9. WEB SEARCH: only use if explicitly requested or external info needed. "
        "10. DATA STRUCTURES: drive.list_files and gmail.list_messages return LISTS. "
        "11. CALENDAR: use $calendar_events for event lists. "
        "12. GMAIL: use $gmail_message_body_text for decoded text. "
        "13. CODE OUTPUT: use $last_code_result or $last_code_stdout. "
        "14. SEND EMAIL: LAST task must be gmail.send_message. "
        "15. PIPELINE: prefer complex multi-step workflows. "
        "16. STRING QUOTING: use placeholders for large text. "
        "17. MULTIPLE TABS: use distinct range names. "
        "18. PARAMETER BINDING: auto-links IDs between tasks. "
        "19. CURRENCY: wrap symbols in string quotes."
    )

    if memory_hint:
        memory_hint_escaped = memory_hint.replace("{", "{{{{").replace("}", "}}}}")
        system_prompt = (
            "Relevant past task context:\n"
            + memory_hint_escaped + "\n\n"
            + system_prompt
        )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "{request}")
    ])

    primary_model = config.model or ""
    models_to_try: list[str] = [primary_model] + [
        m for m in _MODEL_FALLBACK_CHAIN if m != primary_model
    ]

    plan_data: Any = None
    for model_idx, model_name in enumerate(models_to_try):
        is_fallback = model_idx > 0
        if is_fallback:
            logger.info(
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
            if _is_rate_limit_error(exc) or _is_endpoint_missing_error(exc):
                logger.info(
                    "Model '%s' skipped (%s). Moving to next fallback.",
                    model_name,
                    "rate-limited" if _is_rate_limit_error(exc) else "endpoint missing",
                )
                continue
            logger.error("Model '%s' raised unexpected error: %s", model_name, exc)
            continue

        if plan_data is not None:
            if is_fallback:
                logger.info(
                    "Plan generated successfully using fallback model '%s'.", model_name
                )
            break

    if plan_data is None:
        logger.info(
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

        # Basic cleanup of planned tasks
        for t in tasks_data:
            if not isinstance(t, dict): continue
            if t.get("service") == "gmail" and t.get("action") == "send_message":
                params = t.get("parameters") or {}
                if explicit_email:
                    params["to_email"] = explicit_email
                    t["parameters"] = params

        tasks: list[PlannedTask] = []
        for t in tasks_data:
            if isinstance(t, dict):
                params = t.get("parameters") or {}
                if not params:
                    params = {k: v for k, v in t.items() if k not in ("id", "service", "action", "parameters", "reason")}
                
                tasks.append(PlannedTask(
                    id=str(t.get("id", f"task-{len(tasks)+1}")),
                    service=str(t.get("service", "")),
                    action=str(t.get("action", "")),
                    parameters=params,
                    reason=str(t.get("reason", ""))
                ))
        return RequestPlan(
            raw_text=text,
            tasks=tasks,
            summary=str(plan_data.get("summary", "Generated Workspace Plan")),
            confidence=float(plan_data.get("confidence") or _DEFAULT_CONFIDENCE),
            no_service_detected=bool(plan_data.get("no_service_detected", False)),
            source="langchain",
        )

    return plan_data
