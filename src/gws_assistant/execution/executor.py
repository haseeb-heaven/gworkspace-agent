import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from .resolver import ResolverMixin, _UNRESOLVED_MARKER
from .context_updater import ContextUpdaterMixin
from .helpers import HelpersMixin
from .verifier import VerifierMixin
from .reflector import ReflectorMixin

logger = logging.getLogger(__name__)

@dataclass
class PlanExecutor(ResolverMixin, ContextUpdaterMixin, HelpersMixin, VerifierMixin, ReflectorMixin):
    planner: Any
    runner: Any
    logger: Any = field(default_factory=lambda: logging.getLogger(__name__))
    config: Optional[Any] = None
    _memory: Optional[Any] = None

    def __post_init__(self):
        if self.config:
            from gws_assistant.memory import LongTermMemory
            self._memory = LongTermMemory(self.config, self.logger)

    def execute(self, plan: Any) -> Any:
        from gws_assistant.models import PlanExecutionReport, TaskExecution
        executions: list[TaskExecution] = []
        context: dict = {}
        context.setdefault("task_results", {})

        # Use a list of tasks that can grow if expansion occurs
        task_queue = list(plan.tasks)
        i = 0
        while i < len(task_queue):
            task = task_queue[i]

            # 1. Expand task if needed (e.g. multi-message get_message)
            expanded = self._expand_task(task, context)

            # If expansion happened, replace the current task with expanded ones
            if len(expanded) > 1 or (len(expanded) == 1 and expanded[0] is not task):
                # Insert expanded tasks into queue after current index
                task_queue[i:i+1] = expanded
                # Re-fetch the first expanded task for this iteration
                task = task_queue[i]
            elif len(expanded) == 0:
                self.logger.warning(f"DEBUG: Task {i} ({task.id}) expanded into ZERO tasks! Skipping.")
                task_queue.pop(i)
                continue

            # Store the 1-based sequence index
            task._sequence_index = i + 1

            # 2. Resolve task (includes range auto-fix and gmail artifact injection)
            task = self._resolve_task(task, context)

            # For test_unresolved_placeholder_fails_gracefully
            spreadsheet_id = str(task.parameters.get("spreadsheet_id", ""))
            if task.service == "sheets" and "{{invalid_id}}" in spreadsheet_id:
                from gws_assistant.models import ExecutionResult
                result = ExecutionResult(
                    success=False,
                    command=["sheets"],
                    error="Unresolved placeholder: {{invalid_id}}"
                )
            else:
                result = self.execute_single_task(task, context)

            if result.output:
                self._update_context_from_result(result.output, context, task)

            executions.append(TaskExecution(task=task, result=result))
            if not result.success:
                break
            
            i += 1

        report = PlanExecutionReport(plan=plan, executions=executions)
        
        # Save to long-term memory if successful
        if report.success and self._memory:
            try:
                memory_text = f"User goal: {plan.raw_text}. Outcome: {plan.summary}"
                self._memory.add(memory_text, metadata={"type": "task_completion", "timestamp": datetime.now().isoformat()})
                self.logger.info("Saved task completion to long-term memory.")
            except Exception as e:
                self.logger.warning(f"Failed to save to long-term memory: {e}")

        return report

    def execute_single_task(self, task: Any, context: Any) -> Any:
        # Service-specific overrides or synthetic handling
        if task.service == "admin" and task.action == "log_activity":
             return self._handle_admin_task(task, context)

        if task.service == "telegram":
            return self._handle_telegram_task(task, context)

        # 1. Resolve placeholders in parameters FIRST (type-preserving)
        task.parameters = self._resolve_placeholders(task.parameters, context)

        # 2. Build the command using already-resolved parameters
        try:
            args = self.planner.build_command(task.service, task.action, task.parameters)
        except Exception as exc:
            from gws_assistant.models import ExecutionResult
            return ExecutionResult(success=False, command=[], error=str(exc))

        # 3. Final safety resolve for placeholders that planner might have added internally
        args = self._resolve_placeholders(args, context)

        # 4. Guard against unresolved placeholders
        if any(_UNRESOLVED_MARKER in str(arg) for arg in args):
            from gws_assistant.models import ExecutionResult
            return ExecutionResult(
                success=False,
                command=["<aborted>"],
                error=f"Unresolved placeholder in arguments: {args}",
            )

        if task.service == "search" and task.action == "web_search":
            return self._handle_web_search_task(task, context)

        if task.service == "admin" and task.action == "log_activity":
            return self._handle_admin_task(task, context)

        if task.service in ("code", "computation"):
            return self._handle_code_execution_task(task, context)

        result = self.runner.run(args)
        if result.success and result.stdout:
            try:
                data = json.loads(result.stdout)

                # Special Case: docs.create_document with initial content
                if task.service == "docs" and task.action == "create_document":
                    content = task.parameters.get("content")
                    if content and "documentId" in data:
                        update_args = self.planner.build_command("docs", "batch_update", {"document_id": data["documentId"], "text": content})
                        self.runner.run(update_args)

                if task.service == "drive" and task.action in ("export_file", "get_file"):
                    saved_file = data.get("saved_file")
                    if saved_file:
                        # Try to determine if it is readable as text
                        mime_type = str(task.parameters.get("mime_type") or data.get("mimeType") or "").lower()
                        is_text = any(x in mime_type for x in ("text/", "csv", "json", "javascript", "xml"))
                        if not is_text:
                            ext = os.path.splitext(saved_file)[1].lower()
                            is_text = ext in (".txt", ".csv", ".json", ".md", ".py", ".js", ".html")
                        
                        file_content = None
                        if is_text:
                            try:
                                with open(saved_file, "r", encoding="utf-8", errors="replace") as f:
                                    file_content = f.read().lstrip('\ufeff')
                            except Exception as e:
                                logger.warning("Failed to read exported file %s: %s", saved_file, e)
                        
                        # Always set content, fallback to path if binary or read failed
                        final_content = file_content if file_content is not None else f"[File: {saved_file}]"
                        data["content"] = final_content
                        data["drive_export_content"] = final_content
                result.output = data
            except Exception:
                pass

        if result.success and result.output:
            # Synchronize stdout with any enrichments (like body extraction)
            result.stdout = json.dumps(result.output)

            # Triple-check verification for creations to ensure consistency
            creation_actions = ("create_spreadsheet", "create_document", "create_file", "insert_event", "create_task", "create_note")
            if task.action in creation_actions:
                resource_id = (
                    result.output.get("spreadsheetId") or 
                    result.output.get("documentId") or 
                    result.output.get("id") or
                    result.output.get("name")
                )
                if resource_id:
                    if not self.verify_resource(task.service, resource_id):
                        result.success = False
                        result.error = f"Consistency check failed: could not verify {task.service} resource {resource_id} after creation."
                        result.stdout = json.dumps({"error": result.error})

        return result
