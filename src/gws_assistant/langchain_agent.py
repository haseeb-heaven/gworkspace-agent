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
        "2. EMAIL DETAILS: For Gmail, ALWAYS follow gmail.list_messages with gmail.get_message if details are needed. "
        "Pass 'q' to list_messages, then omit 'id' on get_message (the executor will automatically resolve it).\n"
        "3. EXPORTS: For Drive exports (Docs/Sheets), ALWAYS call drive.export_file. Do NOT use Docs/Sheets APIs for exporting.\n"
        "4. WEB SEARCH: If the user asks for information not in their Workspace (e.g. 'Top 3 AI frameworks'), use search.web_search first.\n"
        "5. PARAMETER BINDING: The system automatically links 'id', 'spreadsheet_id', and 'document_id' between sequential tasks.\n"
        "6. DO NOT invent services or actions that are not in the catalog. Use ONLY what is provided.\n"
        "7. If a request asks for both supported and unsupported services, create tasks ONLY for the supported ones, and ignore the unsupported ones. Do NOT set no_service_detected=true if AT LEAST ONE supported service can be used.\n"
        "8. PIPELINE ENFORCEMENT: For complex workflows, prefer the sequence: web_search -> summarize_results -> docs.create_document -> sheets.append_values -> gmail.send_message."
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
