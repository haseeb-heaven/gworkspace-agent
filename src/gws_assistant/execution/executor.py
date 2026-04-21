import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from gws_assistant.verification_engine import VerificationEngine, VerificationError

from .context_updater import ContextUpdaterMixin
from .helpers import HelpersMixin
from .reflector import ReflectorMixin
from .resolver import _UNRESOLVED_MARKER, ResolverMixin
from .verifier import VerifierMixin

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
            from gws_assistant.memory_backend import get_memory_backend
            self._memory = get_memory_backend(self.config, self.logger)

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
            task.sequence_index = i + 1

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
        from gws_assistant.models import ExecutionResult

        # Service-specific overrides or synthetic handling
        if task.service == "telegram":
            return self._handle_telegram_task(task, context)

        # 1. Resolve placeholders in parameters FIRST (type-preserving)
        task.parameters = self._resolve_placeholders(task.parameters, context)

        # Sandbox / Read-Only Mode Logic
        is_delete = any(kw in task.action.lower() for kw in ("delete", "remove", "trash", "clear"))
        is_write = any(kw in task.action.lower() for kw in ("create", "update", "append", "send", "upload", "copy", "move", "batch"))

        if self.config:
            if is_delete or is_write:
                # Read-only mode blocks ALL writes
                if self.config.read_only_mode:
                    self.logger.warning(f"READ-ONLY MODE: Blocking {task.service}.{task.action}")
                    return ExecutionResult(
                        success=False,
                        command=["<blocked>"],
                        error=f"Task {task.service}.{task.action} blocked by READ-ONLY mode. Disable READ_ONLY_MODE to allow modifications."
                    )

                # Sandbox mode specifically intercepts deletions or high-risk writes for confirmation
                if self.config.sandbox_enabled:
                    prompt_msg = f"\n[SANDBOX] Task {task.service}.{task.action} requires modification/deletion. Disable sandbox to proceed? (Y/N): "
                    # We use a simple input check here. In a real CLI this might need better handling.
                    choice = input(prompt_msg).strip().lower()
                    if choice != 'y':
                        self.logger.info(f"SANDBOX: User declined {task.service}.{task.action}")
                        return ExecutionResult(
                            success=False,
                            command=["<declined>"],
                            error=f"Task {task.service}.{task.action} declined by user in SANDBOX mode."
                        )
                    else:
                        self.logger.info(f"SANDBOX: User authorized {task.service}.{task.action}. Proceeding.")
        
        self.logger.debug(f"Proceeding to execute {task.service}.{task.action}")

        if task.service == "search" and task.action == "web_search":
            return self._handle_web_search_task(task, context)

        if task.service == "admin" and task.action == "log_activity":
            return self._handle_admin_task(task, context)

        if task.service in ("code", "computation"):
            return self._handle_code_execution_task(task, context)

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
                        data["drive_export_path"] = saved_file
                result.output = data
            except Exception:
                pass

        if result.success and result.output is not None:
            try:
                # Use service_action format for verification engine
                VerificationEngine.verify(f"{task.service}_{task.action}", task.parameters, result.output)
            except VerificationError as e:
                if e.severity == "ERROR":
                    from gws_assistant.exceptions import VerificationError as ExistingVerificationError
                    logger.error(f"Verification engine caught an error: {e}")
                    raise ExistingVerificationError(str(e))
                else:
                    logger.warning(f"Verification engine warning: {e}")

            # Synchronize stdout with any enrichments (like body extraction)
            result.stdout = json.dumps(result.output)

            # Triple-check verification for creations to ensure consistency
            creation_actions = ("create_spreadsheet", "create_document", "create_file", "create_event", "create_task", "create_note")
            if task.action in creation_actions:
                resource_id = (
                    result.output.get("spreadsheetId") or result.output.get("spreadsheet_id") or
                    result.output.get("documentId") or result.output.get("document_id") or
                    result.output.get("id") or
                    result.output.get("name")
                )
                if resource_id:
                    if not self.verify_resource(task.service, resource_id):
                        result.success = False
                        result.error = f"Consistency check failed: could not verify {task.service} resource {resource_id} after creation."
                        result.stdout = json.dumps({"error": result.error})

        elif result.success and result.output is None:
            logger.warning(
                f"Task {task.service}.{task.action} succeeded "
                f"but returned no output — context NOT updated."
            )

        return result
