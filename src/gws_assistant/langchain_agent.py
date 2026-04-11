"""LangChain-backed planning and reasoning agent."""

import logging
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from gws_assistant.models import AppConfigModel, RequestPlan, PlannedTask
from gws_assistant.service_catalog import SERVICES
from gws_assistant.tools import web_search_tool, code_execution_tool, summarize_results


def _catalog_for_prompt() -> str:
    """Formats the service catalog for the system prompt."""
    lines = []
    for s_key, spec in SERVICES.items():
        lines.append(f"service: {s_key}")
        for a_key, a_spec in spec.actions.items():
            param_str = ", ".join(f"{p.name}(required={p.required})" for p in a_spec.parameters)
            lines.append(f"  action: {a_key} -> params: {param_str}")
    return "\n".join(lines)


def create_agent(config: AppConfigModel, logger: logging.Logger) -> ChatOpenAI | None:
    """Configures and returns the LangChain model for planning."""
    if not config.api_key:
        logger.warning("LangChain planning disabled because no API key is configured.")
        return None

    # Handle provider specific configuration
    model_name = config.model
    if config.provider == "openrouter" and not model_name.startswith("openai/"):
         # Ensure we don't automatically prepend for openrouter if user already provided it but standardizes if not
         pass

    llm_kwargs: dict[str, Any] = {
        "model": model_name,
        "api_key": config.api_key,
        "temperature": 0,
        "max_retries": 2,
    }
    
    if config.base_url:
        llm_kwargs["base_url"] = config.base_url

    try:
        model = ChatOpenAI(**llm_kwargs)
        return model
    except Exception as e:
        logger.error(f"Failed to initialize LangChain model: {e}")
        return None


def plan_with_langchain(text: str, config: AppConfigModel, logger: logging.Logger) -> RequestPlan | None:
    """Uses LangChain with structured output to generate a RequestPlan."""
    model = create_agent(config, logger)
    if not model:
        return None

    system_prompt = (
        "You are a Google Workspace command planner.\n"
        "Your goal is to turn user requests into ordered, executable task plans.\n\n"
        f"Available action catalog:\n{_catalog_for_prompt()}\n\n"
        "CRITICAL RULES:\n"
        "1. DRIVE SEARCH: For drive.list_files, you MUST extract the user's search term and pass it as the 'q' parameter "
        "using Google Drive query syntax. Examples: \"name contains 'Budget'\" or \"fullText contains 'Agentic AI'\". "
        "NEVER call drive.list_files without a q parameter when the user provides a search term.\n"
        "2. EMAIL DETAILS: For Gmail, ALWAYS follow gmail.list_messages with gmail.get_message if details are needed. "
        "Pass 'q' to list_messages, then omit 'id' on get_message (the executor will automatically resolve it).\n"
        "3. EXPORTS: For Drive exports (Docs/Sheets), ALWAYS call drive.export_file. Do NOT use Docs/Sheets APIs for exporting.\n"
        "4. WEB SEARCH: If the user asks for information not in their Workspace (e.g. 'Top 3 AI frameworks'), use search.web_search first.\n"
        "5. PARAMETER BINDING: The system automatically links 'id', 'spreadsheet_id', and 'document_id' between sequential tasks.\n"
        "6. DO NOT invent services or actions that are not in the catalog. Use ONLY what is provided.\n"
        "7. If a request asks for both supported and unsupported services, create tasks ONLY for the supported ones, and ignore the unsupported ones. Do NOT set no_service_detected=true if AT LEAST ONE supported service can be used.\n"
        "8. PIPELINE ENFORCEMENT: For complex workflows, prefer the sequence: web_search -> summarize_results -> docs.create_document -> sheets.append_values -> gmail.send_message."
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "{request}")
    ])

    # Enforce structured output predicting our RequestPlan model
    try:
        chain = prompt | model.with_structured_output(RequestPlan)
        plan: Any = chain.invoke(
             {"request": text}, 
             config=RunnableConfig(metadata={"timeout": config.timeout_seconds})
        )

        # Some models/providers (like OpenRouter) might return a dict instead of the dataclass object
        if isinstance(plan, dict):
            tasks_data = plan.get("tasks") or []
            tasks = []
            for t_data in tasks_data:
                if isinstance(t_data, dict):
                    # Ensure parameters is a dict
                    params = t_data.get("parameters")
                    if not isinstance(params, dict):
                        params = {}
                    tasks.append(PlannedTask(
                        id=str(t_data.get("id", "")),
                        service=str(t_data.get("service", "")),
                        action=str(t_data.get("action", "")),
                        parameters=params,
                        reason=str(t_data.get("reason", ""))
                    ))
                else:
                    tasks.append(t_data)
            
            plan = RequestPlan(
                raw_text=str(plan.get("raw_text", text)),
                tasks=tasks,
                summary=str(plan.get("summary", "")),
                confidence=float(plan.get("confidence", 0.0)),
                no_service_detected=bool(plan.get("no_service_detected", False)),
                source="langchain"
            )

        # Apply standard defaults that CrewAI was doing
        if not plan.summary:
             plan.summary = "Generated Google Workspace Plan"
        if plan.confidence == 0.0 and len(plan.tasks) > 0:
             plan.confidence = 0.9 
        return plan
    except Exception as e:
        logger.error(f"LangChain planning failed: {e}")
        return None
