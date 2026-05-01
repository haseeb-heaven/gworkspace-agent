import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class HelpersMixin:
    # Type hints for mypy
    config: Any
    logger: logging.Logger
    planner: Any
    runner: Any

    def _resolve_placeholders(self, val: Any, context: dict, use_repr_for_complex: bool = False, depth: int = 0) -> Any:
        # This will be provided by ResolverMixin
        ...

    def _think(self, *args, **kwargs) -> str:
        return "Thought: Proceeding with planned task."

    def _should_replan(self, *args, **kwargs) -> bool:
        return False

    def _handle_web_search_task(self, task: Any, context: dict) -> Any:
        """Execute a web search task and populate context with results."""
        try:
            from gws_assistant.models import ExecutionResult
            from gws_assistant.tools.web_search import web_search_tool

            query = task.parameters.get("query", "")
            result_data = web_search_tool.invoke({"query": query})
            results = result_data.get("results") or result_data.get("rows") or []

            markdown_lines = []
            table_values = []
            for r in results:
                if isinstance(r, dict):
                    title   = r.get("title", "")
                    # The web search tool returns 'snippet' and 'url'
                    # But if we receive 'content' and 'link' fallback to those.
                    content = r.get("snippet", r.get("content", ""))
                    link    = r.get("url", r.get("link", ""))
                    markdown_lines.append(f"## {title}\n{content}\n{link}")
                    table_values.append([title, link, content])
                elif isinstance(r, list):
                    table_values.append(r)

            context["search_summary_rows"] = table_values
            context["search_summary_table"] = "\n\n".join(markdown_lines)
            context["search_summary_count"] = len(results)

            return ExecutionResult(
                success=True, command=["web_search", query], stdout=json.dumps(result_data), output=result_data
            )
        except Exception as exc:
            from gws_assistant.models import ExecutionResult

            return ExecutionResult(success=False, command=["web_search"], error=str(exc))

    def _handle_admin_task(self, task: Any, context: dict) -> Any:
        """Handle synthetic admin tasks like log_activity."""
        from gws_assistant.models import ExecutionResult

        action = task.action
        if action == "log_activity":
            data = task.parameters.get("data", "")
            logger.info("AUDIT LOG: %s", data)
            return ExecutionResult(
                success=True,
                command=["admin", "log_activity", "internal"],
                stdout=json.dumps({"success": True, "logged_at": datetime.now().isoformat()}),
                output={"success": True},
            )
        return ExecutionResult(success=False, command=["admin"], error=f"Unsupported synthetic admin action: {action}")

    def _handle_code_execution_task(self, task: Any, context: dict) -> Any:
        """Execute a code execution task and return the result."""
        try:
            from gws_assistant.models import ExecutionResult
            from gws_assistant.tools.code_execution import execute_generated_code

            # Use code-safe resolution (use repr for dicts/lists)
            raw_code = task.parameters.get("code")
            if not raw_code:
                # Try variations
                for k in ["script", "python", "content", "text", "body", "python_code"]:
                    if k in task.parameters:
                        raw_code = task.parameters[k]
                        break

            code = self._resolve_placeholders(raw_code or "", context, use_repr_for_complex=True)
            logger.info("Executing generated code:\n%s", code)

            if not code:
                return ExecutionResult(success=False, command=["code_execute"], error="No code provided")

            if self.config and not self.config.code_execution_enabled:
                return ExecutionResult(
                    success=False,
                    command=["code_execute"],
                    error="Code execution is disabled by configuration (CODE_EXECUTION_ENABLED=false).",
                )

            # Inject task_results and other common context keys into extra_globals
            task_results = context.get("task_results", {})

            # Robustness: if LLM uses task_results[0] instead of task_results['task-1']
            # we inject integer keys pointing to the same data (0-based and 1-based).
            results_with_numeric = task_results.copy()
            for key, val in task_results.items():
                if key.startswith("task-"):
                    try:
                        num = int(key.split("-")[1])
                        results_with_numeric[num] = val  # 1-based
                        results_with_numeric[num - 1] = val  # 0-based
                    except (ValueError, IndexError):
                        pass

            # Ensure injected_vars is a list to prevent KeyError: 0
            injected_vars = context.get("injected_vars", [])
            if not isinstance(injected_vars, list):
                logger.warning("injected_vars was a %s, forcing to list", type(injected_vars))
                injected_vars = []

            extra_globals = {
                "task_results": results_with_numeric,
                "injected_vars": injected_vars,
                "any": any,
                "all": all,
                "sum": sum,
                "min": min,
                "max": max,
                "len": len,
                "list": list,
                "dict": dict,
                "set": set,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "round": round,
                "enumerate": enumerate,
                "zip": zip,
            }

            result = execute_generated_code(code, config=self.config, extra_globals=extra_globals)

            # Store in context for future placeholders
            results_map = context.setdefault("task_results", {})
            results_map["code"] = result.get("output", {})
            results_map["computation"] = result.get("output", {})

            # Extract stdout and parsed value
            output_data = result.get("output", {})

            # --- AUTO-WRITE TO FILE ---
            # If the next task (or this task) suggests a file should be created,
            # and we have content in parsed_value or stdout, write it.
            target_file = task.parameters.get("file_path")
            if target_file and result.get("success"):
                content_to_write = output_data.get("parsed_value") or output_data.get("stdout")
                if content_to_write:
                    try:
                        with open(target_file, "w", encoding="utf-8") as f:
                            f.write(str(content_to_write))
                        self.logger.info(f"Auto-wrote code output to {target_file}")
                    except Exception as e:
                        self.logger.warning(f"Failed to auto-write code output to {target_file}: {e}")

            if output_data.get("parsed_value") is not None:
                parsed = output_data["parsed_value"]
                context["last_code_result"] = parsed
                context["code_parsed_value"] = parsed

                # Promote parsed_value keys to results_map for easy placeholder access
                if isinstance(parsed, dict):
                    num = task.id.split("-")[-1] if "-" in task.id else task.id
                    for k, v in parsed.items():
                        results_map[f"task-{num}.{k}"] = v
                        results_map[f"{num}.{k}"] = v
                        # Also update the task's own entry in the map if it's a dict
                        if isinstance(results_map.get(task.id), dict):
                            results_map[task.id][k] = v
                else:
                    # If parsed_value is not a dict (e.g., a list or scalar), store it directly
                    num = task.id.split("-")[-1] if "-" in task.id else task.id
                    results_map[f"task-{num}.result"] = parsed
                    results_map[f"{num}.result"] = parsed
                    results_map[f"task-{num}.parsed_value"] = parsed
                    results_map[f"{num}.parsed_value"] = parsed

            # Always store stdout for email templates
            if output_data.get("stdout") is not None:
                stdout = output_data["stdout"]
                context["code_stdout"] = stdout
                context["last_code_stdout"] = stdout
                num = task.id.split("-")[-1] if "-" in task.id else task.id
                results_map[f"task-{num}.stdout"] = stdout
                results_map[f"{num}.stdout"] = stdout
                results_map[f"task-{num}.output"] = stdout
                results_map[f"{num}.output"] = stdout

            return ExecutionResult(
                success=result.get("success", False),
                command=["code_execute"],
                stdout=json.dumps(result.get("output", {})),
                error=result.get("error"),
                output=result.get("output", {}),
            )
        except Exception as exc:
            from gws_assistant.models import ExecutionResult

            return ExecutionResult(success=False, command=["code_execute"], error=str(exc))

    def _handle_telegram_task(self, task: Any, context: dict) -> Any:
        """Execute a telegram send_message task."""
        try:
            from gws_assistant.models import ExecutionResult
            from gws_assistant.tools.telegram import redact_sensitive, send_telegram

            message = task.parameters.get("message", "")
            message = self._resolve_placeholders(message, context)
            sent = send_telegram(str(message), context=context)

            return ExecutionResult(
                success=sent,
                command=["telegram", "send_message"],
                stdout=redact_sensitive(message),
                stderr="" if sent else "Telegram send failed.",
                return_code=0 if sent else 1,
                output={"success": sent},
            )
        except Exception as exc:
            from gws_assistant.models import ExecutionResult

            return ExecutionResult(success=False, command=["telegram"], error=str(exc))
