"""Full native ReAct agent using LangChain create_react_agent + LangGraph ToolNode.

ReAct = Reasoning + Acting.  The core loop is:

    Thought  → LLM reasons about what to do next
    Action   → LLM calls one of the bound GWS tools
    Observation → Tool result is appended to message history
    ... loop until LLM emits a final answer (no tool call) ...

This module replaces the old plan→validate→execute pipeline with a single
LLM-native loop.  The LLM itself decides:
  - Which tool to call
  - In what order
  - Whether a previous observation means it should try something different
  - When it has enough information to give a final answer

Key components:
  - create_react_agent()  : LangGraph built-in that creates the agent graph
  - ToolNode              : LangGraph node that executes tool calls from AIMessages
  - bind_tools()          : Attaches ALL_TOOLS schema to the LLM so it can call them
  - MessagesState         : Built-in TypedDict state with a 'messages' channel

Usage:
    from gws_assistant.react_agent import create_react_agent_graph, run_react_agent

    graph = create_react_agent_graph(config, executor, logger)
    output = run_react_agent("Send me an email with the top 5 Python repos", graph, logger)
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent  # LangGraph native ReAct

from .models import AppConfigModel
from .react_tools import ALL_TOOLS, build_gws_tools

# ---------------------------------------------------------------------------
# System prompt — tells the LLM its role and the ReAct discipline
# ---------------------------------------------------------------------------

_REACT_SYSTEM_PROMPT = """\
You are an expert Google Workspace automation assistant.
You have access to tools for Gmail, Google Sheets, Google Docs, Google Drive,
Google Calendar, web search, and Python code execution.

Follow the ReAct pattern strictly:
  Thought:     Reason step-by-step about what to do next.
  Action:      Call the appropriate tool.
  Observation: Read the tool result carefully before continuing.
  ... repeat as needed ...
  Final Answer: When you have enough information, give a clear, concise answer.

Guidelines:
1. Always verify what you observe before taking the next action.
2. If a tool returns an error, reflect on why and try a corrected approach.
3. Chain tools when needed (e.g. search emails → get full message → summarise).
4. For Gmail send: always use the EXACT email address from the user's request.
5. For Sheets: create the spreadsheet first, then append data in a second call.
6. For web search followed by a write action: extract the key data from the
   observation before writing it.
7. Never hallucinate tool arguments — use only concrete values from context.
8. When you are done with all actions, return a clear human-readable summary.
"""


# ---------------------------------------------------------------------------
# Model fallback chain (same as langchain_agent.py for consistency)
# ---------------------------------------------------------------------------

_MODEL_FALLBACK_CHAIN: list[str] = [
    "google/gemini-2.0-flash-001",
    "google/gemini-flash-1.5-8b",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen-2.5-72b-instruct:free",
]


def _build_llm(config: AppConfigModel, logger: logging.Logger,
               model_override: str | None = None) -> ChatOpenAI:
    """Create a ChatOpenAI LLM instance pointing to the configured provider."""
    model_name = model_override or config.model or _MODEL_FALLBACK_CHAIN[0]
    logger.info("ReAct agent: using model '%s' via base_url='%s'", model_name, config.base_url)
    return ChatOpenAI(
        model=model_name,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=0,
        max_retries=3,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_react_agent_graph(
    config: AppConfigModel,
    executor: Any,
    logger: logging.Logger,
    model_override: str | None = None,
) -> Any:
    """Build and return a compiled LangGraph ReAct agent.

    The agent is created with:
      - LLM with tools bound via bind_tools()
      - LangGraph ToolNode that executes tool calls automatically
      - MessagesState as the state schema (built-in reducer handles message append)
      - System prompt injected as the first message

    Args:
        config:         AppConfigModel with model/api_key/base_url.
        executor:       PlanExecutor instance — injected into react_tools.
        logger:         Standard Python logger.
        model_override: Optional model name to override config.model.

    Returns:
        Compiled LangGraph StateGraph (callable as app.invoke({...})).
    """
    # Step 1 — inject executor + config into the @tool module globals
    tools = build_gws_tools(executor, config)

    # Step 2 — build LLM and bind all tools so it knows their schemas
    llm = _build_llm(config, logger, model_override)

    # Step 3 — create_react_agent() wires up:
    #   START → agent_node (LLM with bound tools)
    #        → tools_node (ToolNode) on tool_call
    #        → agent_node (loop)
    #        → END on no tool_call
    agent_graph = create_react_agent(
        model=llm,
        tools=tools,
        prompt=_REACT_SYSTEM_PROMPT,
    )

    logger.info(
        "ReAct agent graph compiled with %d tools: %s",
        len(tools),
        [t.name for t in tools],
    )
    return agent_graph


def run_react_agent(
    user_text: str,
    agent_graph: Any,
    logger: logging.Logger,
    recursion_limit: int = 50,
) -> str:
    """Run the ReAct agent on a user request and return the final text answer.

    The agent iterates Thought → Action → Observation until it produces
    a final AIMessage with no tool calls.

    Args:
        user_text:       The user's natural-language request.
        agent_graph:     Compiled graph from create_react_agent_graph().
        logger:          Standard Python logger.
        recursion_limit: Max number of LangGraph steps (default 50).

    Returns:
        Final assistant response as a plain string.
    """
    messages = [HumanMessage(content=user_text)]
    logger.info("ReAct agent: starting run for query='%s'", user_text[:120])

    # First, import RunnableConfig with fallback
    try:
        from langgraph.core.runnables import RunnableConfig
    except ImportError:
        # RunnableConfig path differs across LangGraph versions — try fallback
        from langchain_core.runnables import RunnableConfig

    # Then, invoke the graph with proper error handling
    try:
        final_state = agent_graph.invoke(
            {"messages": messages},
            config=RunnableConfig(recursion_limit=recursion_limit),
        )
    except Exception as exc:
        logger.exception("ReAct agent run failed.")
        return f"ReAct Agent Error: {exc}"

    # Extract final answer from the last AIMessage with no tool calls
    messages_out = final_state.get("messages", [])
    for msg in reversed(messages_out):
        if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", []):
            logger.info("ReAct agent: completed with %d messages in history.",
                        len(messages_out))
            return str(msg.content).strip()

    logger.warning("ReAct agent: no final AIMessage found in state.")
    return "ReAct agent completed but produced no final text output."


def run_react_agent_with_fallback(
    user_text: str,
    config: AppConfigModel,
    executor: Any,
    logger: logging.Logger,
) -> str:
    """Try each model in the fallback chain until one succeeds.

    Builds a fresh agent graph for each model candidate so that bind_tools()
    is called on the correct LLM instance.

    Args:
        user_text: The user's natural-language request.
        config:    AppConfigModel.
        executor:  PlanExecutor instance.
        logger:    Standard Python logger.

    Returns:
        Final assistant response as a plain string.
    """
    primary = config.model or ""
    models_to_try: list[str] = [primary] + [
        m for m in _MODEL_FALLBACK_CHAIN if m != primary
    ]

    last_error = ""
    for idx, model_name in enumerate(models_to_try):
        if idx > 0:
            logger.warning(
                "ReAct agent: primary model exhausted, trying fallback %d/%d: '%s'",
                idx, len(models_to_try) - 1, model_name,
            )
        try:
            graph = create_react_agent_graph(
                config=config,
                executor=executor,
                logger=logger,
                model_override=model_name,
            )
            result = run_react_agent(user_text, graph, logger)
            if result and "ReAct Agent Error" not in result:
                if idx > 0:
                    logger.info("ReAct agent: succeeded with fallback model '%s'", model_name)
                return result
            last_error = result
        except Exception as exc:
            logger.warning("ReAct agent: model '%s' raised: %s", model_name, exc)
            last_error = str(exc)
            continue

    return f"ReAct agent failed after {len(models_to_try)} model(s). Last error: {last_error}"