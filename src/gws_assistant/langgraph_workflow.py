"""LangGraph workflow for the assistant."""

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
    ReflectionDecision,
    StructuredToolResult,
    TaskExecution,
)
from gws_assistant.output_formatter import HumanReadableFormatter
from gws_assistant.tools.code_execution import execute_generated_code
from gws_assistant.tools.web_search import summarize_results, web_search_tool
from gws_assistant.langchain_agent import create_agent

_MAX_HISTORY = 10

# Keywords that signal the intent is to find/search external data.
_SEARCH_INTENT_KEYWORDS = (
    "find top",
    "search for",
    "look up",
    "find best",
    "find latest",
    "what are the top",
    "top 3",
    "top 5",
    "top 10",
    "best ",
)


def _trim_history(messages: list[Any]) -> list[Any]:
    return messages[-_MAX_HISTORY:]


def create_workflow(config: AppConfigModel, system, executor, logger: logging.Logger):
    """Creates the compiled LangGraph workflow."""

    formatter = HumanReadableFormatter()

    def _append_history(state: AgentState, msg: Any) -> list[Any]:
        history = list(state.get("conversation_history", []))
        history.append(msg)
        return _trim_history(history)

    def _normalize_workspace_result(result: Any) -> StructuredToolResult:
        if hasattr(result, "to_structured_result"):
            return result.to_structured_result()
        return StructuredToolResult(success=False, output={}, error="Unknown execution result type")

    def _log_step(tool_name: str, normalized_input: Any, normalized_output: StructuredToolResult | ReflectionDecision | dict[str, Any]) -> None:
        logger.info("tool=%s input=%s output=%s", tool_name, normalized_input, normalized_output)

    def plan_node(state: AgentState) -> dict[str, Any]:
        try:
            plan = system.plan(state["user_text"])
            history = _append_history(state, AIMessage(content=f"Planned {len(plan.tasks)} tasks."))
            _log_step("planner", {"user_text": state["user_text"]}, {"tasks": len(plan.tasks), "source": plan.source})
            return {"plan": plan, "error": None, "conversation_history": history}
        except Exception as exc:
            history = _append_history(state, AIMessage(content=f"Planning failed: {exc}"))
            _log_step("planner", {"user_text": state.get("user_text", "")}, {"error": str(exc)})
            return {"error": str(exc), "conversation_history": history}

    def validate_node(state: AgentState) -> dict[str, Any]:
        plan = state.get("plan")
        if not plan:
            return {"error": "No plan to validate."}
        for task in plan.tasks:
            if not task.action:
                return {"error": f"Task {task.id} has no action."}
        return {"error": None}

    def execute_task_node(state: AgentState) -> dict[str, Any]:
        plan = state.get("plan")
        idx = state.get("current_task_index", 0)
        context = state.get("context", {})
        executions = list(state.get("executions", []))
        thought_trace = list(state.get("thought_trace", []))

        if not plan or idx >= len(plan.tasks):
            return {"error": "No tasks to execute."}

        task = plan.tasks[idx]
        expanded = executor._expand_task(task, context)
        if not expanded:
            return {
                "error": f"Task {task.id} expanded to no executable tasks.",
                "last_result": StructuredToolResult(success=False, output={}, error="Empty expansion"),
                "executions": executions,
            }

        latest: StructuredToolResult | None = None
        task_error: str | None = None
        for exp_task in expanded:
            resolved = executor._resolve_task(exp_task, context)
            result = executor.execute_single_task(resolved, context)
            executions.append(TaskExecution(task=resolved, result=result))
            latest = _normalize_workspace_result(result)
            thought_trace.append({
                "step": idx + 1,
                "action": f"{resolved.service}.{resolved.action}",
                "observation": str(latest.get("output", {})
                                .get("stdout", ""))[:300],
                "success": result.success,
                "reason": resolved.reason,
            })
            _log_step(f"{resolved.service}.{resolved.action}", resolved.parameters, latest)
            if not result.success:
                task_error = result.error or result.stderr or "Task execution failed"
                break

        return {
            "executions": executions,
            "context": context,
            "error": task_error,
            "last_result": latest,
            "current_attempt": state.get("current_attempt", 0) + 1,
            "conversation_history": _trim_history(state.get("conversation_history", [])),
            "thought_trace": thought_trace,
        }

    def reflect_node(state: AgentState) -> dict[str, Any]:
        error = state.get("error")
        attempts = state.get("current_attempt", 0)
        context = dict(state.get("context", {}))
        updates: dict[str, Any] = {}
        if not error:
            decision = ReflectionDecision(action="continue", reason="Task completed successfully.")
        elif "CODE_EXECUTION_ENABLED=false" in str(error):
            decision = ReflectionDecision(action="continue", reason="Code execution is disabled by configuration.")
        elif attempts < config.max_retries:
            decision = ReflectionDecision(action="retry", reason="Retrying failed task.")
        elif state.get("plan") and context.get("replan_count", 0) < config.max_replans:
            context["replan_count"] = int(context.get("replan_count", 0)) + 1
            updates["context"] = context
            updates["current_attempt"] = 0
            updates["current_task_index"] = 0
            updates["error"] = None
            decision = ReflectionDecision(action="replan", reason="Retries exhausted, requesting new plan.")
        else:
            decision = ReflectionDecision(action="continue", reason="Cannot recover from failure.")
        _log_step("reflection", {"error": error, "attempt": attempts}, decision)
        updates["reflection"] = decision
        updates["conversation_history"] = _append_history(state, AIMessage(content=decision.reason))
        return updates

    def update_context_node(state: AgentState) -> dict[str, Any]:
        return {
            "current_task_index": state.get("current_task_index", 0) + 1,
            "error": None,
            "current_attempt": 0,
            "conversation_history": _trim_history(state.get("conversation_history", [])),
        }

    def format_output_node(state: AgentState) -> dict[str, Any]:
        plan = state.get("plan")
        executions = state.get("executions", [])
        if plan and executions:
            report = formatter.format_report(
                PlanExecutionReport(
                    plan=plan,
                    executions=executions,
                    thought_trace=state.get("thought_trace", []),
                )
            )
        else:
            report = state.get("final_output") or state.get("error") or "No result produced."
        if any(not item.result.success for item in executions) and "failed" not in report.lower():
            report = f"Execution finished with failures.\n\n{report}"
        return {"final_output": report, "conversation_history": _trim_history(state.get("conversation_history", []))}

    def web_search_node(state: AgentState) -> dict[str, Any]:
        result = web_search_tool.invoke({"query": state["user_text"]})
        if result.get("error"):
            structured = StructuredToolResult(success=False, output=result, error=result["error"])
            return {"last_result": structured, "error": result["error"]}
        summary = summarize_results.invoke({"text": str(result.get("results"))})
        structured = StructuredToolResult(success=True, output={"query": state["user_text"], "summary": summary, "results": result.get("results", [])}, error=None)
        # Store summary for downstream docs/sheets tasks to consume via $web_search_summary.
        context = dict(state.get("context", {}))
        context["web_search_summary"] = summary
        context["web_search_rows"] = [[r.get("title", ""), r.get("url", ""), r.get("snippet", "")] for r in result.get("results", [])]
        return {
            "final_output": f"Web Search Result:\n\n{summary}",
            "last_result": structured,
            "context": context,
        }

    def code_execution_node(state: AgentState) -> dict[str, Any]:
        if not config.code_execution_enabled:
            return {
                "error": "Code execution is disabled by configuration (CODE_EXECUTION_ENABLED=false).",
                "last_result": StructuredToolResult(success=False, output={}, error="code_execution_disabled"),
                "current_attempt": state.get("current_attempt", 0) + 1,
            }
        code = (state.get("context", {}) or {}).get("generated_code")
        if not code:
            return {
                "error": "Code execution requires generated_code in context.",
                "last_result": StructuredToolResult(success=False, output={}, error="Missing generated_code"),
                "current_attempt": state.get("current_attempt", 0) + 1,
            }
        result = execute_generated_code(str(code), config=config)
        _log_step("sandbox_execute", {"code": code}, result)
        
        # Update context for placeholders
        context = dict(state.get("context", {}))
        results_map = context.setdefault("task_results", {})
        # Since this is a standalone code execution node (not part of sequence),
        # we index it under 'code' and 'computation'
        results_map["code"] = result.get("output", {})
        results_map["computation"] = result.get("output", {})
        
        return {
            "last_result": result,
            "error": result.get("error"),
            "final_output": result["output"].get("stdout", ""),
            "current_attempt": state.get("current_attempt", 0) + 1,
            "context": context,
        }

    def generate_code_node(state: AgentState) -> dict[str, Any]:
        prompt = (
            "Generate Python code ONLY. The code must store its final answer in a variable named `result` "
            "and may print intermediate details. NO markdown formatting, just raw code.\n\n"
            "CRITICAL: Do NOT use ANY 'import' statements. All standard libraries are unavailable. "
            "Use only built-in functions and basic logic.\n\n"
            f"User request:\n{state['user_text']}"
        )
        model = create_agent(config, logger)
        if not model:
            if not config.use_heuristic_fallback:
                return {
                    "error": "Unable to generate code because no LLM is configured and heuristic fallback is disabled.",
                    "last_result": StructuredToolResult(success=False, output={"prompt": prompt}, error="code_generation_unavailable"),
                }
            extracted = "".join(ch for ch in state["user_text"] if ch.isdigit() or ch in ".+-*/() ")
            generated = f"result = {extracted or '0'}\nprint(result)"
            context = dict(state.get("context", {}))
            context["generated_code"] = generated
            _log_step("generate_code", {"prompt": state["user_text"]}, {"mode": "heuristic_fallback"})
            return {"context": context, "error": None}

        llm_response = model.invoke(prompt)
        content = getattr(llm_response, "content", str(llm_response))
        if not isinstance(content, str):
            content = str(content)
        generated_code = content.strip().removeprefix("```python").removeprefix("```").removesuffix("```").strip()
        context = dict(state.get("context", {}))
        context["generated_code"] = generated_code
        _log_step("generate_code", {"prompt": state["user_text"]}, {"generated_code": generated_code})
        return {"context": context, "error": None}

    def route_after_plan(state: AgentState) -> Literal["validate", "format_output", "web_search", "generate_code"]:
        if state.get("error"):
            return "format_output"
        plan = state.get("plan")
        text = state["user_text"].lower()

        # Route to web_search if:
        # 1. Plan has no tasks (tasks=0) regardless of no_service_detected flag, OR
        # 2. Plan explicitly signals needs_web_search, OR
        # 3. Query contains search intent keywords and has save-to-workspace intent
        has_search_intent = any(kw in text for kw in _SEARCH_INTENT_KEYWORDS)
        plan_has_tasks = bool(plan and plan.tasks)
        needs_web_search = getattr(plan, "needs_web_search", False) if plan else False

        if needs_web_search:
            return "web_search"

        if not plan_has_tasks:
            # No plan or empty plan — determine best fallback
            if has_search_intent or needs_web_search:
                return "web_search"
            if getattr(plan, "needs_code_execution", False) or any(keyword in text for keyword in ("calculate", "compute", "sum", "average")):
                return "generate_code"
            return "format_output"

        # Plan has tasks — check if it's a web-search-then-save workflow
        # (tasks reference $web_search_summary or $web_search_rows)
        if plan:
            for task in plan.tasks:
                params = task.parameters or {}
                if any("$web_search" in str(v) for v in params.values()):
                    return "web_search"

        return "validate"

    def route_after_web_search(state: AgentState) -> Literal["validate", "format_output"]:
        """After web search, if the plan has workspace tasks to execute, go to validate."""
        plan = state.get("plan")
        if plan and plan.tasks and not state.get("error"):
            return "validate"
        return "format_output"

    def route_after_task(state: AgentState) -> Literal["reflect_node"]:
        return "reflect_node"

    def route_after_reflection(state: AgentState) -> Literal["update_context", "execute_task", "generate_plan", "format_output", "generate_code"]:
        decision = state.get("reflection")
        if not decision:
            return "format_output"
        if decision.action == "continue":
            return "update_context" if not state.get("error") else "format_output"
        if decision.action == "retry":
            # If we failed during code execution, retry from generate_code/code_execution
            if state.get("context", {}).get("generated_code"):
                return "generate_code"
            return "execute_task"
        if decision.action == "replan":
            return "generate_plan"
        return "format_output"

    def route_after_context(state: AgentState) -> Literal["execute_task", "format_output"]:
        plan = state.get("plan")
        idx = state.get("current_task_index", 0)
        if plan and idx < len(plan.tasks):
            return "execute_task"
        return "format_output"


    workflow = StateGraph(AgentState)
    workflow.add_node("generate_plan", plan_node)
    workflow.add_node("validate", validate_node)
    workflow.add_node("execute_task", execute_task_node)
    workflow.add_node("reflect_node", reflect_node)
    workflow.add_node("update_context", update_context_node)
    workflow.add_node("format_output", format_output_node)
    workflow.add_node("web_search", web_search_node)
    workflow.add_node("generate_code", generate_code_node)
    workflow.add_node("code_execution", code_execution_node)

    workflow.add_edge(START, "generate_plan")
    workflow.add_conditional_edges("generate_plan", route_after_plan)
    workflow.add_edge("validate", "execute_task")
    workflow.add_conditional_edges("execute_task", route_after_task)
    workflow.add_conditional_edges("reflect_node", route_after_reflection)
    workflow.add_conditional_edges("update_context", route_after_context)
    # web_search now routes to validate (if plan has workspace tasks) or format_output
    workflow.add_conditional_edges("web_search", route_after_web_search)
    workflow.add_edge("generate_code", "code_execution")
    workflow.add_edge("code_execution", "reflect_node")
    workflow.add_edge("format_output", END)
    return workflow.compile()


def run_workflow(user_text: str, config: AppConfigModel, system, executor, logger: logging.Logger) -> str:
    initial_state = AgentState(
        user_text=user_text,
        context={"request_text": user_text},
        current_task_index=0,
        executions=[],
        retry_count=0,
        current_attempt=0,
        conversation_history=[HumanMessage(content=user_text)],
    )
    app = create_workflow(config, system, executor, logger)
    try:
        final_state = app.invoke(initial_state, config=RunnableConfig(recursion_limit=100))
        return final_state.get("final_output", "Workflow returned no output.")
    except Exception as exc:
        logger.exception("Workflow failed.")
        return f"Workflow Error: {exc}"
