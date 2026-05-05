import ast
import json
import logging
import re
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def _sanitize_file_path_patterns(value: Any) -> Any:
    """Replace [File: ...] patterns with a placeholder to avoid leaking local paths."""
    if isinstance(value, str):
        return re.sub(r'\[File: [^\]]+\]', '[Document file]', value)
    elif isinstance(value, list):
        return [_sanitize_file_path_patterns(item) for item in value]
    elif isinstance(value, dict):
        return {k: _sanitize_file_path_patterns(v) for k, v in value.items()}
    return value


def _coerce_structured_value(raw: Any) -> Any:
    """Return list/dict if raw string represents structured data, otherwise keep value."""
    if raw is None:
        return []
    if isinstance(raw, (list, dict)):
        return raw
    if isinstance(raw, str):
        trimmed = raw.strip()
        if not trimmed:
            return []

        try:
            parsed = json.loads(trimmed)
        except json.JSONDecodeError:
            parsed = None

        if parsed is None:
            try:
                parsed = ast.literal_eval(trimmed)
            except (SyntaxError, ValueError):
                parsed = None

        if isinstance(parsed, (list, dict)):
            return parsed

        # Heuristic for "Found 0 calendar events" style logs
        if "calendar events" in trimmed.lower() and "found" in trimmed.lower():
            return []

    return raw


def _normalize_injected_vars(values: list[Any]) -> list[Any]:
    return [_coerce_structured_value(item) for item in values]


class HelpersMixin:
    # Type hints for mypy
    config: Any
    logger: logging.Logger
    planner: Any
    runner: Any

    def _resolve_placeholders(self, val: Any, context: dict, use_repr_for_complex: bool = False, depth: int = 0) -> Any:
        # This will be provided by ResolverMixin
        ...

    def _generate_execution_thought(self, *args, **kwargs) -> str:
        """Generate a thought/reasoning message during execution (placeholder for future use)."""
        return "Thought: Proceeding with planned task."

    def _should_trigger_replanning(self, *args, **kwargs) -> bool:
        """Determine if execution should trigger re-planning (placeholder for future use)."""
        return False

    # Backward compatibility aliases for tests that mock the old method names
    def _think(self, *args, **kwargs) -> str:
        return self._generate_execution_thought(*args, **kwargs)

    def _should_replan(self, *args, **kwargs) -> bool:
        return self._should_trigger_replanning(*args, **kwargs)

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

            # Update result_data with these calculated fields so they end up in task_results
            result_data["rows"] = table_values
            result_data["markdown"] = "\n\n".join(markdown_lines)
            result_data["summary_table"] = "\n\n".join(markdown_lines)

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
            # Replace any remaining unresolved markers with an empty string sentinel
            # to avoid RestrictedPython SyntaxErrors from identifiers starting with '_'
            from gws_assistant.execution.resolver import _UNRESOLVED_MARKER
            if _UNRESOLVED_MARKER in code:
                code = code.replace(f'"{_UNRESOLVED_MARKER}"', '""').replace(f"'{_UNRESOLVED_MARKER}'", "''").replace(_UNRESOLVED_MARKER, '""')
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

            injected_vars = _normalize_injected_vars(injected_vars)

            # Auto-fetch spreadsheet data if injected_vars contains spreadsheet references
            fetched_vars = []
            for var in injected_vars:
                logger.info("DEBUG: Processing injected_vars item: type=%s, value=%s", type(var), str(var)[:100])
                if isinstance(var, str) and (".csv" in var.lower() or "sheet" in var.lower()):
                    # Try to fetch spreadsheet data by name from drive
                    logger.info("Auto-fetching spreadsheet data for: %s", var)
                    try:
                        # Try to find spreadsheet in drive results
                        drive_results = task_results.get("drive", {})
                        files = drive_results.get("files", [])
                        logger.info("DEBUG: drive_results keys: %s, files count: %d", list(task_results.keys()), len(files))
                        if not files:
                            # Check task-1 (usually drive.list_files)
                            for k, v in task_results.items():
                                logger.info("DEBUG: Checking task_results key %s, type=%s", k, type(v))
                                if "drive" in k.lower() or isinstance(v, dict) and "files" in v:
                                    files = v.get("files", []) if isinstance(v, dict) else []
                                    logger.info("DEBUG: Found files in %s, count: %d", k, len(files))
                                    break
                        for file_info in files:
                            if isinstance(file_info, dict):
                                file_name = file_info.get("name", "")
                                logger.info("DEBUG: Checking file: %s", file_name)
                                if var.lower() in file_name.lower() or file_name.lower().endswith(".csv"):
                                    file_id = file_info.get("id")
                                    if file_id:
                                        logger.info("Found spreadsheet ID %s for %s", file_id, var)
                                        # Fetch the actual data - use the actual sheet name from file_info
                                        sheet_name = file_info.get("name", "Sheet1")
                                        get_args = ["sheets", "spreadsheets", "values", "get", "--params", json.dumps({"spreadsheetId": file_id, "range": sheet_name})]
                                        get_res = self.runner.run(get_args)
                                        logger.info("DEBUG: get_values result: success=%s, stdout=%s", get_res.success, str(get_res.stdout)[:200])
                                        if get_res.success and get_res.stdout:
                                            parsed = self._coerce_structured_value(get_res.stdout)
                                            logger.info("DEBUG: parsed type=%s, has values=%s", type(parsed), isinstance(parsed, dict) and "values" in parsed)
                                            if isinstance(parsed, dict) and "values" in parsed:
                                                values = parsed["values"]
                                                # Normalize column names to match LLM expectations
                                                if values and len(values) > 0:
                                                    headers = values[0]
                                                    # Column name mapping: normalize common variations
                                                    header_map = {}
                                                    for i, h in enumerate(headers):
                                                        h_lower = str(h).lower().strip()
                                                        if "category" in h_lower:
                                                            header_map[i] = "Category"
                                                        elif "revenue" in h_lower and "total" in h_lower:
                                                            header_map[i] = "Total Revenue"
                                                        elif "revenue" in h_lower:
                                                            header_map[i] = "Revenue"
                                                        else:
                                                            header_map[i] = h
                                                    # Apply mapping to first row
                                                    values[0] = [header_map[i] for i in range(len(headers))]
                                                fetched_vars.append(values)
                                                logger.info("Successfully fetched %d rows from spreadsheet", len(values))
                                                break
                        else:
                            # No data found, keep original string
                            logger.warning("No matching spreadsheet found for: %s", var)
                            fetched_vars.append(var)
                    except Exception as e:
                        logger.warning("Failed to auto-fetch spreadsheet data: %s", e)
                        fetched_vars.append(var)
                else:
                    fetched_vars.append(var)
            injected_vars = fetched_vars

            # Don't auto-convert to DataFrame - let LLM handle it
            # This prevents column mismatch errors

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

            def _tableify(value: Any) -> str | None:
                rows: list[list[str]] = []
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    headers = list(value[0].keys())
                    rows.append(headers)
                    for item in value:
                        row = [str(item.get(h, "")) for h in headers]
                        rows.append(row)
                elif isinstance(value, list) and value and isinstance(value[0], list):
                    rows = [[str(cell) for cell in row] for row in value]
                else:
                    return None

                if not rows:
                    return None

                header = rows[0]
                table_lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
                for row in rows[1:]:
                    # pad row
                    padded = row + [""] * (len(header) - len(row))
                    table_lines.append("| " + " | ".join(padded) + " |")
                return "\n".join(table_lines)

            if output_data.get("parsed_value") is not None:
                parsed = output_data["parsed_value"]
                # Sanitize [File: ...] patterns to avoid leaking local paths in sheets
                parsed = _sanitize_file_path_patterns(parsed)
                context["last_code_result"] = parsed
                context["code_parsed_value"] = parsed
                table_text = _tableify(parsed)
                if table_text:
                    context["last_code_result_table"] = table_text

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
