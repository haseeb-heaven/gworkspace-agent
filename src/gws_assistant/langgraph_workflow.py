"""LangGraph workflow for the GWS assistant — powered by a native ReAct agent.

This module replaces the old plan→validate→execute pipeline with a
full ReAct (Reasoning + Acting) loop.

Workflow architecture
─────────────────────

  START
    │
    ▼
  route_input ──────────────────────────────┐
    │  (pure GWS or multi-step)             │  (simple web search only)
    ▼                                       ▼
  react_agent_node                    web_search_node
    │  (Thought → Action → Obs loop)        │
    │  Calls GWS tools, web search,         │
    │  code execution natively.             │
    ▼                                       │
  format_output_node  ◄───────────────────── ┘
    │
    ▼
  END

Key differences vs the old workflow
────────────────────────────────────
  OLD: LLM plans a static task list → executor runs it blindly.
  NEW: LLM reasons at EVERY step — it sees every tool observation before
       deciding the next action.  This is true ReAct.

  OLD: reflect_node is a simple retry counter.
  NEW: Reflection is native — the LLM's own Thought step IS the reflection.
       If a tool fails, the LLM reads the error in its Observation and
       tries a corrected approach on the next iteration.

  OLD: route_after_plan has complex keyword-matching heuristics.
  NEW: Routing is minimal — just decide whether to use the ReAct agent
       or the lightweight web_search_node for pure search queries.

Backward compatibility
───────────────────────
  The public API (create_workflow + run_workflow) is preserved so
  agent_system.py and all callers continue working without changes.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from gws_assistant.models import (
    AgentState,
    AppConfigModel,
    PlanExecutionReport,
    StructuredToolResult,
)
from gws_assistant.output_formatter import HumanReadableFormatter
from gws_assistant.tools.web_search import summarize_results, web_search_tool


_MAX_HISTORY = 10

# ---------------------------------------------------------------------------
# Keywords for lightweight routing decision
# ---------------------------------------------------------------------------

# Queries that are ONLY about web search — no GWS write action needed
_PURE_SEARCH_KEYWORDS = (
    "what is ",
    "who is ",
    "define ",
    "explain ",
    "how does ",
    "tell me about ",
)

# Any GWS-touching keyword → must go to full ReAct agent
_GWS_ACTION_KEYWORDS = (
    "email", "gmail", "send", "sheet", "spreadsheet", "google doc",
    "drive", "calendar", "create", "upload", "append", "write",
    "read", "fetch", "get messages", "search emails", "list files",
    "schedule", "event", "meeting",
)


def _trim_history(messages: list[Any]) -> list[Any]:
    return messages[-_MAX_HISTORY:]


# ---------------------------------------------------------------------------
# Workflow factory
# ---------------------------------------------------------------------------

def create_workflow(
    config: AppConfigModel,
    system: Any,
    executor: Any,
    logger: logging.Logger,
) -> Any:
    """Create and return the compiled LangGraph workflow.

    The workflow uses a native ReAct agent as its primary execution engine.
    The old plan→validate→execute nodes have been removed; the ReAct agent
    handles planning, tool execution, and reflection in a single unified loop.

    Args:
        config:   AppConfigModel with model/api_key settings.
        system:   GWSAssistantSystem (kept for interface compatibility — unused).
        executor: PlanExecutor instance (injected into react_tools).
        logger:   Standard Python logger.

    Returns:
        Compiled LangGraph StateGraph.
    """
    formatter = HumanReadableFormatter()

    # ------------------------------------------------------------------
    # Lazy import of ReAct components — avoids circular imports at module
    # load time and makes the old pipeline still importable independently.
    # ------------------------------------------------------------------
    from gws_assistant.react_agent import (
        create_react_agent_graph,
        run_react_agent,
    )

    # Build the ReAct agent graph once — it will be reused across calls.
    # We build it here (inside create_workflow) so config + executor are
    # captured in the closure correctly.
    _react_graph = create_react_agent_graph(
        config=config,
        executor=executor,
        logger=logger,
    )

    # ------------------------------------------------------------------
    # Node: react_agent_node
    # The single node that runs the full ReAct loop.  It receives the
    # user_text from state, runs the compiled ReAct graph, and stores
    # the final answer in state['final_output'].
    # ------------------------------------------------------------------

    def react_agent_node(state: AgentState) -> dict[str, Any]:
        user_text = state.get("user_text", "")
        logger.info("[react_agent_node] Running ReAct loop for: '%s'", user_text[:120])

        thought_trace: list[dict] = list(state.get("thought_trace", []))
        history:       list[Any]  = list(state.get("conversation_history", []))

        try:
            from langchain_core.messages import HumanMessage as HM
            messages_in = [{"messages": [HM(content=user_text)]}]

            # Stream the ReAct agent so we can capture intermediate steps
            # for the thought_trace (useful for debugging / UI display).
            final_state: dict[str, Any] = {}
            step_count = 0

            for chunk in _react_graph.stream(
                {"messages": [HM(content=user_text)]},
                config=RunnableConfig(recursion_limit=50),
                stream_mode="values",
            ):
                final_state = chunk
                step_count += 1

                # Capture each non-human message as a thought/observation
                for msg in chunk.get("messages", []):
                    role    = type(msg).__name__
                    content = getattr(msg, "content", "") or ""
                    tcs     = getattr(msg, "tool_calls", []) or []
                    if tcs:
                        for tc in tcs:
                            thought_trace.append({
                                "step":        step_count,
                                "role":        "tool_call",
                                "action":      tc.get("name", ""),
                                "observation": str(tc.get("args", {}))[:200],
                                "success":     True,
                                "reason":      "ReAct agent action",
                            })
                    elif role == "ToolMessage":
                        thought_trace.append({
                            "step":        step_count,
                            "role":        "observation",
                            "action":      getattr(msg, "name", "tool_result"),
                            "observation": str(content)[:300],
                            "success":     True,
                            "reason":      "Tool observation",
                        })

            # Extract the final answer — last AIMessage with no tool calls
            final_answer = ""
            for msg in reversed(final_state.get("messages", [])):
                content   = getattr(msg, "content", None)
                tool_calls = getattr(msg, "tool_calls", [])
                if content and not tool_calls and type(msg).__name__ == "AIMessage":
                    final_answer = str(content).strip()
                    break

            if not final_answer:
                final_answer = "ReAct agent completed but produced no final text output."

            history.append(AIMessage(content=final_answer))

            logger.info(
                "[react_agent_node] Completed in %d steps. Answer: '%s'",
                step_count, final_answer[:120],
            )

            return {
                "final_output":         final_answer,
                "thought_trace":        thought_trace,
                "conversation_history": _trim_history(history),
                "error":                None,
            }

        except Exception as exc:
            logger.exception("[react_agent_node] ReAct agent raised an exception.")
            error_msg = f"ReAct Agent Error: {exc}"
            history.append(AIMessage(content=error_msg))
            return {
                "final_output":         error_msg,
                "error":                str(exc),
                "thought_trace":        thought_trace,
                "conversation_history": _trim_history(history),
            }

    # ------------------------------------------------------------------
    # Node: web_search_node
    # Lightweight node for pure informational queries that don't involve
    # any GWS write operations.  Avoids spinning up the full ReAct loop.
    # ------------------------------------------------------------------

    def web_search_node(state: AgentState) -> dict[str, Any]:
        query   = state.get("user_text", "")
        history = list(state.get("conversation_history", []))
        logger.info("[web_search_node] Query: '%s'", query[:120])

        try:
            result  = web_search_tool.invoke({"query": query})
            summary = ""
            if not result.get("error"):
                try:
                    summary = summarize_results.invoke({"text": str(result.get("results", ""))})
                except Exception as _e:
                    logger.warning("[web_search_node] summarize_results failed (ignored): %s", _e)
                    summary = str(result.get("results", ""))[:2000]

            output = f"Web Search Results for: {query}\n\n{summary}" if summary else (
                result.get("error") or "No results found."
            )
            structured = StructuredToolResult(
                success=not bool(result.get("error")),
                output={"query": query, "summary": summary, "results": result.get("results", [])},
                error=result.get("error"),
            )
        except Exception as exc:
            logger.error("[web_search_node] failed: %s", exc)
            output     = f"Web search failed: {exc}"
            structured = StructuredToolResult(success=False, output={}, error=str(exc))

        history.append(AIMessage(content=output))
        return {
            "final_output":         output,
            "last_result":          structured,
            "conversation_history": _trim_history(history),
            "error":                structured.get("error"),
        }

    # ------------------------------------------------------------------
    # Node: format_output_node
    # Cleans up the final_output string — keeps it as-is since the ReAct
    # agent already produces human-readable text.  Adds a failure prefix
    # if the error flag is set.
    # ------------------------------------------------------------------

    def format_output_node(state: AgentState) -> dict[str, Any]:
        output  = state.get("final_output") or state.get("error") or "No result produced."
        history = list(state.get("conversation_history", []))

        if state.get("error") and "failed" not in str(output).lower():
            output = f"Execution finished with failures.\n\n{output}"

        history.append(AIMessage(content=str(output)))
        return {
            "final_output":         str(output),
            "conversation_history": _trim_history(history),
        }

    # ------------------------------------------------------------------
    # Routing function: route_input
    # Decides whether to use the lightweight web_search_node or the full
    # ReAct agent.  Defaults to the ReAct agent for safety.
    # ------------------------------------------------------------------

    def route_input(
        state: AgentState,
    ) -> Literal["react_agent", "web_search"]:
        text = (state.get("user_text") or "").lower().strip()

        has_gws_action  = any(kw in text for kw in _GWS_ACTION_KEYWORDS)
        is_pure_search  = (
            any(text.startswith(kw) for kw in _PURE_SEARCH_KEYWORDS)
            and not has_gws_action
        )

        if is_pure_search:
            logger.info("[route_input] → web_search_node (pure informational query)")
            return "web_search"

        logger.info("[route_input] → react_agent_node")
        return "react_agent"

    # ------------------------------------------------------------------
    # Graph assembly
    # ------------------------------------------------------------------
    workflow = StateGraph(AgentState)

    workflow.add_node("react_agent",   react_agent_node)
    workflow.add_node("web_search",    web_search_node)
    workflow.add_node("format_output", format_output_node)

    # Edges
    workflow.add_conditional_edges(
        START,
        route_input,
        {
            "react_agent": "react_agent",
            "web_search":  "web_search",
        },
    )
    workflow.add_edge("react_agent",   "format_output")
    workflow.add_edge("web_search",    "format_output")
    workflow.add_edge("format_output", END)

    return workflow.compile()


# ---------------------------------------------------------------------------
# Public run helper — preserves the original interface
# ---------------------------------------------------------------------------

def run_workflow(
    user_text: str,
    config: AppConfigModel,
    system: Any,
    executor: Any,
    logger: logging.Logger,
) -> str:
    """Run the ReAct workflow and return the final plain-text answer.

    Args:
        user_text: The user's natural-language request.
        config:    AppConfigModel.
        system:    GWSAssistantSystem (kept for interface compat — unused).
        executor:  PlanExecutor instance.
        logger:    Standard Python logger.

    Returns:
        Final assistant answer as a plain string.
    """
    initial_state = AgentState(
        user_text=user_text,
        context={"request_text": user_text},
        current_task_index=0,
        executions=[],
        retry_count=0,
        current_attempt=0,
        conversation_history=[HumanMessage(content=user_text)],
        thought_trace=[],
    )

    app = create_workflow(config, system, executor, logger)

    try:
        final_state = app.invoke(
            initial_state,
            config=RunnableConfig(recursion_limit=100),
        )
        return final_state.get("final_output", "Workflow returned no output.")
    except Exception as exc:
        logger.exception("ReAct workflow failed.")
        return f"Workflow Error: {exc}"
