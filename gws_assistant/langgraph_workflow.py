"""LangGraph workflow for the assistant."""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from gws_assistant.langchain_agent import create_agent
from gws_assistant.models import (
    AgentState,
    AppConfigModel,
    PlanExecutionReport,
    ReflectionDecision,
    StructuredToolResult,
    TaskExecution,
    validate_planned_task,
)
from gws_assistant.output_formatter import HumanReadableFormatter
from gws_assistant.tools.code_execution import execute_generated_code
from gws_assistant.tools.web_search import summarize_results, web_search_tool

_MAX_HISTORY = 10

# Keywords that signal intent to search external data.
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

# GWS service keywords — queries containing these should route to execute_task
# even when heuristic planning returns 0 tasks, NOT to generate_code.
_GWS_INTENT_KEYWORDS = (
    "email",
    "gmail",
    "sheet",
    "spreadsheet",
    "google doc",
    "drive",
    "calendar",
    "slides",
    "send",
    "extract data",
    "search emails",
    "job offer",
    "inbox",
    "task",
    "todo",
)

# Phrases that indicate an LLM refusal or non-code response.
_REFUSAL_PHRASES = (
    "i'm sorry",
    "i am sorry",
    "i can't help",
    "i cannot help",
    "i'm not able",
    "i am not able",
    "as an ai",
    "as a language model",
    "cannot assist",
    "unable to assist",
)


def _trim_history(messages: list[Any]) -> list[Any]:
    return messages[-_MAX_HISTORY:]


def _is_llm_refusal(code: str) -> bool:
    """Return True if the string looks like an LLM refusal rather than Python code."""
    lowered = code.lower().strip()
    return any(phrase in lowered for phrase in _REFUSAL_PHRASES)


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

    def _log_step(
        tool_name: str,
        normalized_input: Any,
        normalized_output: StructuredToolResult | ReflectionDecision | dict[str, Any],
    ) -> None:
        if config.verbose:
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
        context = dict(state.get("context", {}))
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
                "context": context,
            }

        latest: StructuredToolResult | None = None
        task_error: str | None = None
        for exp_task in expanded:
            resolved = executor._resolve_task(exp_task, context)

            # Bug Fix: Ensure task is structurally valid AND all placeholders resolved
            try:
                validate_planned_task(resolved)
            except Exception as val_exc:
                logger.error(f"Validation failed after resolution for task {resolved.id}: {val_exc}")
                return {
                    "error": str(val_exc),
                    "last_result": StructuredToolResult(success=False, output={}, error=str(val_exc)),
                    "executions": executions,
                    "context": context,
                }

            result = executor.execute_single_task(resolved, context)
            executions.append(TaskExecution(task=resolved, result=result))
            latest = _normalize_workspace_result(result)

            # Store results in context for placeholder resolution
            # executor._resolve_template expects dict with keys like 'files', 'id' etc.
            # latest['output'] usually contains 'parsed_payload' which has the real data.
            results_map = context.setdefault("task_results", {})
            payload = latest["output"].get("parsed_payload") or latest["output"]

            # Fix: If payload contains 'messages' list, promote it so code.execute sees a list
            # as expected by LLM for list_messages tasks.
            if isinstance(payload, dict) and "messages" in payload and isinstance(payload["messages"], list):
                if len(payload["messages"]) > 0:
                    storage_payload = [
                        item if isinstance(item, dict) else {"id": str(item), "content": str(item)}
                        for item in payload["messages"]
                    ]
                else:
                    storage_payload = []
            elif isinstance(payload, list):
                storage_payload = [
                    item if isinstance(item, dict) else {"id": str(item), "content": str(item)} for item in payload
                ]
            else:
                storage_payload = payload

            # Update legacy context keys (last_spreadsheet_id, message_id, etc.)
            executor._update_context_from_result(payload, context, resolved)

            # Always also store by sequential index (task-1, task-2, etc.) to
            # support LLMs that refer to tasks by their order regardless of name.
            seq_id = f"task-{idx + 1}"
            results_map[seq_id] = storage_payload
            results_map[str(idx + 1)] = storage_payload
            results_map[f"t{idx + 1}"] = storage_payload
            logger.debug(f"DEBUG: Saved result to results_map keys: {seq_id}, {idx + 1}, t{idx + 1}")

            # Use task.id as provided in the plan (usually 'task-1', 'task-2' etc.)
            t_id = str(task.id)
            if t_id != seq_id:
                results_map[t_id] = storage_payload
                # Also store with numeric ID for {task-1...} vs {1...}
                if t_id.startswith("task-"):
                    num = t_id.removeprefix("task-")
                    results_map[num] = storage_payload
                    results_map[f"t{num}"] = storage_payload
                elif t_id.isdigit():
                    results_map[f"task-{t_id}"] = storage_payload
                    results_map[f"t{t_id}"] = storage_payload

            if resolved.service == "drive" and resolved.action == "export_file" and latest["success"]:
                # Special handling: if we exported a file, its content (if text) is stored directly.
                # This is used by later tasks like gmail.send_message via $drive_export_content.
                if "drive_export_content" in latest["output"]:
                    content = latest["output"]["drive_export_content"]
                    context["drive_export_content"] = content
                    context["drive_export_file"] = content
                    # Also put it in task_results so {task-N.content} works
                    results_map[t_id] = {"content": content}
                    if t_id.startswith("task-"):
                        results_map[t_id.removeprefix("task-")] = {"content": content}
            thought_trace.append(
                {
                    "step": idx + 1,
                    "action": f"{resolved.service}.{resolved.action}",
                    "observation": str(latest["output"].get("stdout", ""))[:300],
                    "success": result.success,
                    "reason": resolved.reason,
                }
            )
            _log_step(f"{resolved.service}.{resolved.action}", resolved.parameters, latest)
            if not result.success:
                task_error = result.error or result.stderr or "Task execution failed"
                break

        # Fix #5 — fallback if loop had no iterations
        if latest is None:
            latest = StructuredToolResult(success=True, output={}, error=None)

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

        decision, abort_plan = executor.reflect_on_error(error, attempts, config.max_retries)

        if abort_plan:
            updates["abort_plan"] = True

        if decision.action == "replan":
            if state.get("plan") and context.get("replan_count", 0) < config.max_replans:
                context["replan_count"] = int(context.get("replan_count", 0)) + 1
                updates["context"] = context
                updates["current_attempt"] = 0
                updates["current_task_index"] = 0
                updates["error"] = None
                decision.reason = "Retries exhausted, requesting new plan."
            else:
                decision = ReflectionDecision(action="continue", reason="Cannot recover from failure.")
                updates["abort_plan"] = True

        _log_step("reflection", {"error": error, "attempt": attempts}, decision)
        updates["reflection"] = decision
        updates["conversation_history"] = _append_history(state, AIMessage(content=decision.reason))
        return updates

    def update_context_node(state: AgentState) -> dict[str, Any]:
        new_index = state.get("current_task_index", 0) + 1
        if state.get("abort_plan"):
            plan = state.get("plan")
            if plan is not None:
                new_index = len(plan.tasks)
        return {
            "current_task_index": new_index,
            "error": state.get("error"),
            "current_attempt": 0,
            "conversation_history": _trim_history(state.get("conversation_history", [])),
        }

    def format_output_node(state: AgentState) -> dict[str, Any]:
        plan = state.get("plan")
        executions = state.get("executions", [])
        context = state.get("context", {})

        if plan and executions:
            # Resolve placeholders in summary if any exist
            if plan.summary and ("{" in plan.summary or "$" in plan.summary):
                try:
                    plan.summary = executor._resolve_placeholders(plan.summary, context)
                except Exception as e:
                    logger.warning(f"Failed to resolve placeholders in summary: {e}")

            report = formatter.format_report(
                PlanExecutionReport(
                    plan=plan,
                    executions=executions,
                    thought_trace=state.get("thought_trace", []),
                )
            )
        else:
            report = state.get("final_output") or state.get("error") or "No result produced."

        # Guard: if report is still empty and there was an error in state, use it.
        if not report or report == "No result produced.":
            err = state.get("error")
            if err:
                report = err
        if any(not item.result.success for item in executions) and "failed" not in report.lower():
            report = f"Execution finished with failures.\n\n{report}"
        # Save to episodic memory if successful
        if executions and all(item.result.success for item in executions):
            try:
                from .memory import save_episode
                save_episode(state["user_text"], [e.task.parameters for e in executions], report)
            except Exception as e:
                logger.warning(f"Failed to save episode to memory: {e}")

        # Also add a semantic memory fact if successful
        if executions and all(item.result.success for item in executions):
            try:
                memory_text = f"User task: {state['user_text']}. Status: Completed successfully. Summary: {report[:200]}..."
                system.memory.add(memory_text, metadata={"type": "task_completion"})
            except Exception as e:
                logger.warning(f"Failed to add semantic memory: {e}")

        return {"final_output": report, "conversation_history": _trim_history(state.get("conversation_history", []))}

    def web_search_node(state: AgentState) -> dict[str, Any]:
        result = web_search_tool.invoke({"query": state["user_text"]})
        if result.get("error"):
            structured = StructuredToolResult(success=False, output=result, error=result["error"])
            return {"last_result": structured, "error": result["error"]}
        # Isolate summarize so its failure never kills the search result.
        summary = ""
        try:
            summary = summarize_results.invoke({"text": str(result.get("results"))})
        except Exception as _sum_exc:
            logger.warning("summarize_results failed in web_search_node (ignored): %s", _sum_exc)
        structured = StructuredToolResult(
            success=True,
            output={"query": state["user_text"], "summary": summary, "results": result.get("results", [])},
            error=None,
        )
        context = dict(state.get("context", {}))

        rows = [
            [r.get("title", ""), r.get("url", ""), r.get("snippet", "")]
            for r in result.get("results", [])
        ]

        markdown_lines = []
        for r in result.get("results", []):
            title   = r.get("title", "")
            content = r.get("snippet", r.get("content", ""))
            link    = r.get("url", r.get("link", ""))
            markdown_lines.append(f"## {title}\n{content}\n{link}")
        markdown_table = "\n\n".join(markdown_lines)

        # New canonical keys
        context["search_summary_table"] = markdown_table
        context["search_summary_rows"] = rows
        context["search_summary_count"] = len(result.get("results", []))

        # We can still store the LLM summary for use if needed
        context["search_llm_summary"] = summary

        return {
            "final_output": f"Web Search Result:\n\n{summary}",
            "last_result": structured,
            "context": context,
        }

    def code_execution_node(state: AgentState) -> dict[str, Any]:
        if not config.code_execution_enabled:
            msg = "Code execution is disabled by configuration (CODE_EXECUTION_ENABLED=false)."
            return {
                "error": msg,
                "last_result": StructuredToolResult(success=False, output={}, error=msg),
                "current_attempt": state.get("current_attempt", 0) + 1,
            }

        context = dict(state.get("context", {}))
        code = context.get("generated_code")

        # Fallback: if no generated_code, check current task parameters
        if not code:
            plan = state.get("plan")
            idx = state.get("current_task_index", 0)
            if plan and idx < len(plan.tasks):
                task = plan.tasks[idx]
                if task.service in ("code", "computation"):
                    code = task.parameters.get("code")
                    if not code:
                        for k in ["script", "python", "content", "text", "body", "python_code"]:
                            if k in task.parameters:
                                code = task.parameters[k]
                                break

        if not code:
            return {
                "error": "Code execution requires generated_code in context or code parameter in task.",
                "last_result": StructuredToolResult(success=False, output={}, error="Missing code"),
                "current_attempt": state.get("current_attempt", 0) + 1,
            }
        result = execute_generated_code(str(code), config=config)
        _log_step("sandbox_execute", {"code": code}, result)

        results_map = context.setdefault("task_results", {})
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
        lowered = state["user_text"].lower()
        is_computation = any(
            kw in lowered for kw in ("calculate", "sum", "average", "compute", "sort", "reverse", "math", "numbers")
        )

        if not model:
            if not config.use_heuristic_fallback or not is_computation:
                msg = "Unable to generate code because no LLM is configured" if not model else "LLM failed"
                return {
                    "error": f"{msg} and request is not a simple computation.",
                    "last_result": StructuredToolResult(
                        success=False, output={"prompt": prompt}, error="code_generation_unavailable"
                    ),
                    "current_attempt": state.get("current_attempt", 0) + 1,
                }
            extracted = "".join(ch for ch in state["user_text"] if ch.isdigit() or ch in ".+-*/() ")
            generated = f"result = {extracted or '0'}\nprint(result)"
            context = dict(state.get("context", {}))
            context["generated_code"] = generated
            _log_step("generate_code", {"prompt": state["user_text"]}, {"mode": "heuristic_fallback"})
            return {"context": context, "error": None}

        try:
            llm_response = model.invoke(prompt)
        except Exception as exc:
            logger.warning("LLM code generation failed: %s. Falling back to heuristics.", exc)
            if not is_computation:
                return {
                    "error": f"LLM code generation failed and request is not a simple computation: {exc}",
                    "last_result": StructuredToolResult(success=False, output={"prompt": prompt}, error=str(exc)),
                    "current_attempt": state.get("current_attempt", 0) + 1,
                }
            numbers = re.findall(r"\b\d+\b", state["user_text"])
            lowered = state["user_text"].lower()
            if len(numbers) >= 2 and ("from" in lowered or "between" in lowered):
                start, end = numbers[0], numbers[1]
                rev = "True" if "reverse" in lowered or "descending" in lowered else "False"
                generated = f"result = list(range({start}, {int(end) + 1}))\nif {rev}: result.reverse()\nprint(result)"
            else:
                # Basic math extraction
                extracted = "".join(ch for ch in state["user_text"] if ch.isdigit() or ch in ".+-*/() ")
                # Clean up multiple spaces or invalid sequences
                cleaned = re.sub(r"\s+", " ", extracted).strip()
                # If it still looks like multiple numbers, just pick the first or join with +
                if " " in cleaned:
                    cleaned = " + ".join(cleaned.split())
                generated = f"result = {cleaned or '0'}\nprint(result)"

            context = dict(state.get("context", {}))
            context["generated_code"] = generated
            _log_step("generate_code", {"prompt": state["user_text"]}, {"mode": "heuristic_fallback_enhanced"})
            return {"context": context, "error": None}

        content = getattr(llm_response, "content", str(llm_response))
        if not isinstance(content, str):
            content = str(content)
        generated_code = content.strip().removeprefix("```python").removeprefix("```").removesuffix("```").strip()

        # Guard: if the LLM refused or returned non-code, don't pass it to the sandbox.
        if _is_llm_refusal(generated_code):
            logger.warning("generate_code_node: LLM returned a refusal, not executable code.")
            return {
                "error": "LLM declined to generate code for this request. Try rephrasing as a computation task.",
                "last_result": StructuredToolResult(
                    success=False,
                    output={"prompt": prompt, "response": generated_code},
                    error="llm_refusal",
                ),
                "current_attempt": state.get("current_attempt", 0) + 1,
            }

        context = dict(state.get("context", {}))
        context["generated_code"] = generated_code
        _log_step("generate_code", {"prompt": state["user_text"]}, {"generated_code": generated_code})
        return {"context": context, "error": None}

    def route_after_plan(state: AgentState) -> Literal["validate", "format_output", "web_search", "generate_code"]:
        if state.get("error"):
            return "format_output"
        plan = state.get("plan")
        text = state["user_text"].lower()

        has_search_intent = any(kw in text for kw in _SEARCH_INTENT_KEYWORDS)
        has_gws_intent = any(kw in text for kw in _GWS_INTENT_KEYWORDS)
        plan_has_tasks = bool(plan and plan.tasks)
        needs_web_search = getattr(plan, "needs_web_search", False) if plan else False

        if needs_web_search:
            return "web_search"

        if plan and plan_has_tasks:
            # Plan has tasks — check if it's a web-search-then-save workflow
            for task in plan.tasks:
                params = task.parameters or {}
                if any("$web_search" in str(v) for v in params.values()):
                    return "web_search"
            return "validate"

        # No tasks in plan — determine best fallback.
        # GWS-intent queries (email, sheets, drive...) should NOT fall to generate_code;
        # return format_output with a helpful message instead.
        if has_gws_intent:
            return "format_output"

        if has_search_intent:
            return "web_search"

        if getattr(plan, "needs_code_execution", False) or any(
            kw in text for kw in ("calculate", "compute", "sum", "average", "sort", "reverse", "math")
        ):
            return "generate_code"

        return "format_output"

    def route_after_web_search(state: AgentState) -> Literal["validate", "format_output"]:
        """After web search, if the plan has workspace tasks to execute, go to validate."""
        plan = state.get("plan")
        if plan and plan.tasks and not state.get("error"):
            return "validate"
        return "format_output"

    def route_after_task(state: AgentState) -> Literal["reflect_node"]:
        return "reflect_node"

    def route_after_reflection(
        state: AgentState,
    ) -> Literal["update_context", "execute_task", "generate_plan", "format_output", "generate_code"]:
        decision = state.get("reflection")
        if not decision:
            return "format_output"
        if decision.action == "continue":
            return "update_context"
        if decision.action == "retry":
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
    workflow.add_conditional_edges(
        "reflect_node",
        route_after_reflection,
        {
            "update_context": "update_context",
            "execute_task": "execute_task",
            "generate_plan": "generate_plan",
            "format_output": "format_output",
            "generate_code": "generate_code",
        },
    )
    workflow.add_conditional_edges("update_context", route_after_context)
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
