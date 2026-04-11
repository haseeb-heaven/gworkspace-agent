"""LangChain-backed planning and reasoning agent."""

import logging
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from gws_assistant.models import AppConfigModel, RequestPlan, PlannedTask
from gws_assistant.service_catalog import SERVICES, normalize_service


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
        "5. DOCS WRITING: To save data to a document, use docs.create_document followed by docs.batch_update. Use '$last_document_id' for binding.\n"
        "6. PARAMETER BINDING: Use '$last_spreadsheet_id', '$last_document_id', '$last_folder_id', '$web_search_results', and '$gmail_message_body' to link steps.\n"
        "7. DO NOT invent services or actions that are not in the catalog. Use ONLY what is provided.\n"
        "8. If a request asks for both supported and unsupported services, create tasks ONLY for the supported ones, and ignore the unsupported ones. Do NOT set no_service_detected=true if AT LEAST ONE supported service can be used."
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "{request}")
    ])

    # Enforce structured output predicting our RequestPlan model
    try:
        logger.info("Initializing LangChain structured output chain (json_mode).")
        # Use json_mode for better compatibility across providers like OpenRouter
        chain = prompt | model.with_structured_output(RequestPlan, method="json_mode")
        
        logger.info("Invoking LangChain model for text: %s", text[:50] + "...")
        plan: RequestPlan = chain.invoke(
             {"request": text}, 
             config=RunnableConfig(metadata={"timeout": config.timeout_seconds})
        )
        
        if plan is None:
             logger.warning("LangChain returned None plan.")
             return None

        logger.info("LangChain planning successful with %d tasks.", len(plan.tasks))
        
        # Apply standard defaults
        if not plan.summary:
             plan.summary = "Generated Google Workspace Plan"
        if plan.confidence == 0.0 and len(plan.tasks) > 0:
             plan.confidence = 0.9 
        
        plan.source = "langchain"
        return plan
    except Exception as e:
        logger.warning(f"LangChain structured output failed, attempting non-structured fallback: {e}")
        try:
             # Fallback: Just ask for JSON and parse manually
             raw_chain = prompt | model
             response = raw_chain.invoke({"request": text + "\n\nOutput only a JSON object matching the RequestPlan schema."})
             import json
             import re
             content = response.content
             match = re.search(r"(\{.*\})", content, re.DOTALL)
             if match:
                  data = json.loads(match.group(1))
                  # Robust parsing similar to agent_system
                  tasks_data = data.get("tasks") or data.get("plan") or data.get("steps") or []
                  if not isinstance(tasks_data, list): tasks_data = []
                  
                  tasks = []
                  for i, t in enumerate(tasks_data, start=1):
                       if not isinstance(t, dict): continue
                       tasks.append(PlannedTask(
                            id=str(t.get("id") or f"task-{i}"),
                            service=normalize_service(str(t.get("service") or "")),
                            action=str(t.get("action") or "").strip(),
                            parameters=t.get("parameters") or t.get("params") or {},
                            reason=str(t.get("reason") or "").strip()
                       ))
                  
                  plan = RequestPlan(
                       raw_text=data.get("raw_text") or text,
                       tasks=tasks,
                       summary=data.get("summary") or "Generated Workspace Plan",
                       confidence=float(data.get("confidence") or 0.8),
                       source="langchain-fallback"
                  )
                  return plan
        except Exception as e2:
             logger.error(f"LangChain fallback also failed: {e2}")
        
        return None
