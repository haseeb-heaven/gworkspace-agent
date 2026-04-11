"""LangGraph workflow for the assistant."""

import logging
from typing import Literal

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, END, START

from gws_assistant.models import AgentState, AppConfigModel, TaskExecution
from gws_assistant.agent_system import WorkspaceAgentSystem
from gws_assistant.execution import PlanExecutor
from gws_assistant.tools.web_search import web_search_tool, summarize_results
from gws_assistant.tools.code_execution import code_execution_tool
from gws_assistant.output_formatter import HumanReadableFormatter


def create_workflow(config: AppConfigModel, system: WorkspaceAgentSystem, executor: PlanExecutor, logger: logging.Logger):
    """Creates the compiled LangGraph workflow."""
    
    formatter = HumanReadableFormatter()

    def plan_node(state: AgentState) -> dict:
        """Plans the tasks based on user input."""
        logger.info("Executing plan node.")
        try:
            plan = system.plan(state["user_text"])
            if plan:
                 logger.info("Generated Plan: %s", plan.model_dump_json(indent=2))
            return {"plan": plan, "messages": state.get("messages", []) + [AIMessage(content=f"Planned {len(plan.tasks)} tasks.")], "error": None}
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            return {"error": str(e)}

    def validate_node(state: AgentState) -> dict:
        """Validates the generated plan."""
        logger.info("Executing validate node.")
        plan = state.get("plan")
        if not plan:
            return {"error": "No plan to validate."}
            
        # Example validation: ensure no empty actions
        for task in plan.tasks:
            if not task.action:
                return {"error": f"Task {task.id} has no action."}
                
        return {"error": None}

    def execute_task_node(state: AgentState) -> dict:
        """Executes the current task in the plan."""
        plan = state["plan"]
        idx = state.get("current_task_index", 0)
        context = state.get("context", {})
        executions = state.get("executions", [])
        
        if not plan or idx >= len(plan.tasks):
             return {"error": "No tasks to execute."}
             
        task = plan.tasks[idx]
        
        # Expand and resolve
        expanded = executor._expand_task(task, context)
        
        for exp_task in expanded:
            resolved = executor._resolve_task(exp_task, context)
            result = executor.execute_single_task(resolved, context)
            executions.append(TaskExecution(task=resolved, result=result))
            
            if not result.success:
                return {
                     "executions": executions, 
                     "error": result.error, 
                     "context": context
                }
                
        return {
             "executions": executions, 
             "context": context, 
             "error": None
        }

    def update_context_node(state: AgentState) -> dict:
        """Advances to the next task index conditionally."""
        return {"current_task_index": state.get("current_task_index", 0) + 1}

    def format_output_node(state: AgentState) -> dict:
        """Formats the final output for the user."""
        logger.info("Executing format output node.")
        plan = state.get("plan")
        executions = state.get("executions", [])
        
        report = formatter.format_report(plan, executions)
        return {"final_output": report}

    def handle_error_node(state: AgentState) -> dict:
        """Handles retries or formats error output."""
        logger.warning(f"Handling error: {state.get('error')}")
        retry_count = state.get("retry_count", 0)
        
        if retry_count < config.max_retries: # default is typically 3
             logger.info(f"Retrying task (attempt {retry_count + 1})")
             return {"retry_count": retry_count + 1, "error": None}
             
        # Max retries exceeded
        return {"final_output": f"Workflow failed permanently: {state.get('error')}"}

    def route_after_plan(state: AgentState) -> Literal["validate", "format_output", "web_search", "code_execution"]:
        if state.get("error"):
            return "format_output"
        plan = state.get("plan")
        if not plan or plan.no_service_detected:
            # Check for pure research / web search request instead of GWS
            if "search" in state["user_text"].lower() and "web" in state["user_text"].lower():
                 return "web_search"
            # Check for code execution request
            if "run code" in state["user_text"].lower() or "calculate" in state["user_text"].lower():
                 return "code_execution"
            return "format_output"
        return "validate"
        
    def web_search_node(state: AgentState) -> dict:
         """Handles web search queries."""
         result = web_search_tool.invoke({"query": state["user_text"]})
         if result.get("error"):
              return {"final_output": result["error"]}
         
         # Optionally summarize
         summary = summarize_results.invoke({"text": str(result.get("results"))})
         return {"final_output": f"Web Search Result:\n\n{summary}"}
         
    def code_execution_node(state: AgentState) -> dict:
         """Handles direct code execution requests conditionally."""
         # In a real setup, we might use the LLM to write the code.
         # For simplicity in this state machine, if we reach here we assume user provided it
         code = state["user_text"].replace("run code", "").strip()
         if not code:
              return {"final_output": "No code provided to execute."}
              
         result = code_execution_tool.invoke({"code": code})
         
         out = f"Code Output:\n{result.get('stdout')}\n"
         if result.get("error"):
              out += f"\nError: {result.get('error')}"
         return {"final_output": out}

    def route_after_task(state: AgentState) -> Literal["update_context", "handle_error"]:
        if state.get("error"):
            return "handle_error"
        return "update_context"
        
    def route_after_context(state: AgentState) -> Literal["execute_task", "format_output"]:
        plan = state.get("plan")
        idx = state.get("current_task_index", 0)
        if plan and idx < len(plan.tasks):
            return "execute_task"
        return "format_output"
        
    def route_after_error(state: AgentState) -> Literal["execute_task", "format_output"]:
         if state.get("retry_count", 0) > 0 and not state.get("error"): # we successfully cleared error for a retry
              return "execute_task"
         return "format_output"


    # Build Graph
    workflow = StateGraph(AgentState)
    
    workflow.add_node("generate_plan", plan_node)
    workflow.add_node("validate", validate_node)
    workflow.add_node("execute_task", execute_task_node)
    workflow.add_node("update_context", update_context_node)
    workflow.add_node("format_output", format_output_node)
    workflow.add_node("handle_error", handle_error_node)
    workflow.add_node("web_search", web_search_node)
    workflow.add_node("code_execution", code_execution_node)
    
    workflow.add_edge(START, "generate_plan")
    workflow.add_conditional_edges("generate_plan", route_after_plan)
    workflow.add_edge("validate", "execute_task")
    workflow.add_conditional_edges("execute_task", route_after_task)
    workflow.add_conditional_edges("update_context", route_after_context)
    workflow.add_conditional_edges("handle_error", route_after_error)
    workflow.add_edge("web_search", "format_output")
    workflow.add_edge("code_execution", "format_output")
    workflow.add_edge("format_output", END)
    
    return workflow.compile()


def run_workflow(user_text: str, config: AppConfigModel, system: WorkspaceAgentSystem, executor: PlanExecutor, logger: logging.Logger) -> str:
    """Convenience function to run the graph and extract final output."""
    initial_state = AgentState(
         user_text=user_text,
         context={"request_text": user_text},
         current_task_index=0,
         executions=[],
         retry_count=0,
    )
    # Patch config default if missing
    if not hasattr(config, "max_retries"):
         config.max_retries = 3

    app = create_workflow(config, system, executor, logger)
    try:
         final_state = app.invoke(initial_state)
         return final_state.get("final_output", "Workflow returned no output.")
    except Exception as e:
         logger.exception("Workflow failed.")
         return f"Workflow Error: {str(e)}"
