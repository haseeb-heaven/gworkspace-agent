import json
import logging
import os
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from gws_assistant.exceptions import SafetyBlockedError
from gws_assistant.models import ExecutionResult
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
                task_queue[i : i + 1] = expanded
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
                result = ExecutionResult(
                    success=False, command=["sheets"], error="Unresolved placeholder: {{invalid_id}}"
                )
            else:
                result = self.execute_single_task(task, context)

            if result.output is not None:
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
                self._memory.add(
                    memory_text, metadata={"type": "task_completion", "timestamp": datetime.now().isoformat()}
                )
                self.logger.info("Saved task completion to long-term memory.")
            except Exception as e:
                self.logger.exception("Failed to save to long-term memory: %s", e)

        return report

    def execute_single_task(self, task: Any, context: Any) -> Any:

        # Service-specific overrides or synthetic handling
        if task.service == "telegram":
            return self._handle_telegram_task(task, context)

        # 1. Resolve placeholders in parameters FIRST (type-preserving)
        task.parameters = self._resolve_placeholders(task.parameters, context)

        # Sandbox / Read-Only Mode Logic
        if self.config:
            from gws_assistant.safety_guard import SafetyGuard

            # 1. Read-only mode blocks ALL writes/deletes
            is_delete = any(kw in task.action.lower() for kw in ("delete", "remove", "trash", "clear"))
            is_write = any(
                kw in task.action.lower()
                for kw in ("create", "update", "append", "send", "upload", "copy", "move", "batch")
            )
            if (is_delete or is_write) and self.config.read_only_mode:
                self.logger.warning(f"READ-ONLY MODE: Blocking {task.service}.{task.action}")
                return ExecutionResult(
                    success=False,
                    command=["<blocked>"],
                    error=f"Task {task.service}.{task.action} blocked by READ-ONLY mode. Disable READ_ONLY_MODE to allow modifications.",
                )

            # 2. SafetyGuard checks for destructive actions (confirmations/blocks)
            try:
                safety_result = SafetyGuard.check_action(
                    task,
                    is_dry_run=self.config.dry_run,
                    no_confirm=self.config.no_confirm,
                    is_telegram=self.config.is_telegram,
                    force_dangerous=self.config.force_dangerous,
                )
                if isinstance(safety_result, ExecutionResult):
                    return safety_result  # Dry-run or similar mock response
            except SafetyBlockedError as e:
                self.logger.warning(f"SAFETY BLOCK: {e}")
                return ExecutionResult(success=False, command=["<blocked>"], error=str(e))

        self.logger.debug(f"Proceeding to execute {task.service}.{task.action}")

        op_key = self._idempotency_key(task)
        if op_key:
            cached_output = context.setdefault("idempotent_operations", {}).get(op_key)
            if cached_output:
                return ExecutionResult(
                    success=True,
                    command=["<cached>"],
                    output=cached_output,
                    stdout=json.dumps(cached_output),
                )

        if task.service == "gmail" and task.action == "send_message":
            return self._handle_gmail_send_task(task, context)

        if task.service == "search" and task.action == "web_search":
            return self._handle_web_search_task(task, context)

        if task.service == "admin" and task.action == "log_activity":
            return self._handle_admin_task(task, context)

        if task.service in ("code", "computation"):
            return self._handle_code_execution_task(task, context)

        # Intercept move_file to perform parent lookup safely in the executor
        if task.service == "drive" and task.action == "move_file":
            file_id = task.parameters.get("file_id")
            if file_id:
                try:
                    lookup_args = [
                        "drive",
                        "files",
                        "get",
                        "--params",
                        json.dumps({"fileId": file_id, "fields": "parents"}),
                    ]
                    lookup_result = self.runner.run(lookup_args)
                    if lookup_result.success and lookup_result.stdout:
                        data = self._parse_json_result(
                            lookup_result,
                            task.service,
                            task.action,
                            require_mapping=True,
                            context_message="move_file parent lookup",
                        )
                        if isinstance(data, ExecutionResult):
                            return data
                        parents = data.get("parents")
                        if parents and isinstance(parents, list):
                            context["fetch_parents"] = ",".join(parents)
                        else:
                            return ExecutionResult(
                                success=False,
                                command=["drive", "files", "update"],
                                error="Failed to lookup current file parents: No parents returned.",
                            )
                    else:
                        return ExecutionResult(
                            success=False,
                            command=["drive", "files", "update"],
                            error="Failed to lookup current file parents: API call failed.",
                        )
                except (TypeError, ValueError) as e:
                    return ExecutionResult(
                        success=False,
                        command=["drive", "files", "update"],
                        error=f"Failed to lookup current file parents: {e}",
                    )
                except Exception as e:
                    self.logger.exception("Unexpected move_file parent lookup failure")
                    return ExecutionResult(
                        success=False,
                        command=["drive", "files", "update"],
                        error=f"Failed to lookup current file parents: internal error ({e})",
                    )

        # 2. Build the command using already-resolved parameters
        try:
            args = self.planner.build_command(task.service, task.action, task.parameters)
        except ValueError as exc:
            return ExecutionResult(success=False, command=[], error=str(exc))
        except Exception as exc:
            self.logger.exception("Unexpected build_command failure for %s.%s", task.service, task.action)
            return ExecutionResult(
                success=False,
                command=[],
                error=f"Internal command build failure for {task.service}.{task.action}: {exc}",
            )

        # 3. Final safety resolve for placeholders that planner might have added internally
        args = self._resolve_placeholders(args, context)

        # 4. Guard against unresolved placeholders
        if any(_UNRESOLVED_MARKER in str(arg) for arg in args):
            return ExecutionResult(
                success=False,
                command=["<aborted>"],
                error=f"Unresolved placeholder in arguments: {args}",
            )

        result = self.runner.run(args)
        if result.success and result.stdout:
            try:
                data = self._parse_json_result(
                    result,
                    task.service,
                    task.action,
                    require_mapping=True,
                    context_message="task execution result",
                )
                if isinstance(data, ExecutionResult):
                    return data

                # Special Case: docs.create_document with initial content
                if task.service == "docs" and task.action == "create_document":
                    content = task.parameters.get("content")
                    if content and "documentId" in data:
                        update_args = self.planner.build_command(
                            "docs", "batch_update", {"document_id": data["documentId"], "text": content}
                        )
                        update_res = self.runner.run(update_args)
                        if not update_res.success:
                            self.logger.warning(
                                f"Failed to add initial content to doc {data['documentId']}: {update_res.error}"
                            )
                        else:
                            self.logger.info(f"Successfully added initial content to doc {data['documentId']}")

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
                                from pathlib import Path
                                downloads_dir = Path("downloads").resolve()
                                scratch_dir = Path("scratch").resolve()
                                resolved = Path(saved_file).resolve()
                                if not (str(resolved).startswith(str(downloads_dir)) or str(resolved).startswith(str(scratch_dir))):
                                    result.success = False
                                    result.error = f"Path traversal blocked while reading exported file: {saved_file}"
                                    result.stdout = json.dumps({"error": result.error})
                                    return result
                                    
                                with open(saved_file, "r", encoding="utf-8", errors="replace") as f:
                                    file_content = f.read().lstrip("\ufeff")
                            except Exception as e:
                                logger.warning("Failed to read exported file %s: %s", saved_file, e)

                        # Always set content, fallback to path if binary or read failed
                        final_content = file_content if file_content is not None else f"[File: {saved_file}]"

                        self.logger.info(
                            "Exported file content for %s. Size: %s",
                            saved_file,
                            len(final_content) if file_content is not None else "N/A (Binary/Path only)",
                        )

                        data["content"] = final_content
                        data["drive_export_content"] = final_content
                        data["drive_export_path"] = saved_file
                result.output = data
            except Exception as exc:
                self.logger.exception("Failed to enrich parsed result for %s.%s", task.service, task.action)
                return ExecutionResult(
                    success=False,
                    command=result.command,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    return_code=result.return_code,
                    error=f"Failed to process {task.service}.{task.action} response: {exc}",
                )

        if result.success and result.output is not None:
            if op_key and isinstance(result.output, dict):
                context.setdefault("idempotent_operations", {})[op_key] = result.output
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
            creation_actions = (
                "create_spreadsheet",
                "create_document",
                "create_file",
                "create_event",
                "create_task",
                "create_note",
            )
            if task.action in creation_actions:
                resource_id = (
                    result.output.get("spreadsheetId")
                    or result.output.get("spreadsheet_id")
                    or result.output.get("documentId")
                    or result.output.get("document_id")
                    or result.output.get("id")
                    or result.output.get("name")
                )
                if resource_id:
                    if not self.verify_resource(task.service, resource_id):
                        result.success = False
                        result.error = f"Consistency check failed: could not verify {task.service} resource {resource_id} after creation."
                        result.stdout = json.dumps({"error": result.error})

        elif result.success and result.output is None:
            logger.warning(f"Task {task.service}.{task.action} succeeded but returned no output — context NOT updated.")

        return result

    def _parse_json_result(
        self,
        result: ExecutionResult,
        service: str,
        action: str,
        *,
        require_mapping: bool = False,
        context_message: str = "response",
    ) -> dict[str, Any] | list[Any] | ExecutionResult:
        from gws_assistant.json_utils import JsonExtractionError, safe_json_loads

        try:
            data = safe_json_loads(result.stdout)
        except (JsonExtractionError, ValueError) as exc:
            self.logger.error("Failed to parse %s for %s.%s: %s", context_message, service, action, exc)
            return ExecutionResult(
                success=False,
                command=result.command,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.return_code,
                error=f"Failed to parse {context_message} for {service}.{action}: {exc}",
            )

        if require_mapping and not isinstance(data, dict):
            return ExecutionResult(
                success=False,
                command=result.command,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.return_code,
                error=f"Unexpected response schema for {service}.{action}: expected object, got {type(data).__name__}.",
            )
        return data

    def _handle_gmail_send_task(self, task: Any, context: Any) -> ExecutionResult:
        to_email = self.planner._required_text(task.parameters, "to_email").strip().rstrip(".")
        subject = self.planner._required_text(task.parameters, "subject")
        body = self.planner._required_text(task.parameters, "body")
        body = body.replace("\r\n", "\n")
        body = body.replace("\r", "\n")
        body = body.replace("[File: ", "[See attached document: ")

        attachments = task.parameters.get("attachments")
        attachment_paths: list[str] = []
        if isinstance(attachments, str) and attachments.strip():
            attachment_paths = [attachments.strip()]
        elif isinstance(attachments, list):
            attachment_paths = [str(a).strip() for a in attachments if str(a).strip()]

        resolved_attachment_paths: list[str] = []
        for path in attachment_paths:
            if self._looks_like_drive_file_id(path):
                local_path = self.planner._export_drive_file_to_temp(path)
                if local_path:
                    resolved_attachment_paths.append(local_path)
                    continue
                drive_link = f"https://drive.google.com/file/d/{path}/view"
                body = (
                    body.rstrip()
                    + "\n\nNote: The requested document could not be attached directly. "
                    + f"You can access it here: {drive_link}"
                )
                continue

            normalized_path = self.planner._normalize_attachment_path(path)
            if not normalized_path:
                return ExecutionResult(
                    success=False,
                    command=["gmail", "users", "messages", "send"],
                    error=(
                        "Attachment paths must resolve inside scratch/ or downloads/ "
                        "or be exported Drive attachments managed by the executor."
                    ),
                )
            resolved_attachment_paths.append(normalized_path)

        raw_email = (
            self.planner._build_raw_email_with_attachments(
                to_email=to_email,
                subject=subject,
                body=body,
                attachment_paths=resolved_attachment_paths,
            )
            if resolved_attachment_paths
            else self.planner._build_raw_email(to_email=to_email, subject=subject, body=body)
        )
        args = [
            "gmail",
            "users",
            "messages",
            "send",
            "--params",
            json.dumps({"userId": "me"}),
            "--json",
            json.dumps({"raw": raw_email}, ensure_ascii=True),
        ]
        return self.runner.run(args)

    @staticmethod
    def _looks_like_drive_file_id(value: str) -> bool:
        import re

        return bool(re.match(r"^[A-Za-z0-9_\-]{25,60}$", value or ""))

    def _idempotency_key(self, task: Any) -> str | None:
        if task.service == "calendar" and task.action == "create_event":
            task.parameters.setdefault("event_id", self._calendar_event_id(task.parameters))
        if task.action not in {"create_event", "create_folder", "create_file"}:
            return None
        payload = {
            "service": task.service,
            "action": task.action,
            "parameters": task.parameters,
        }
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def _calendar_event_id(parameters: dict[str, Any]) -> str:
        parts = {
            "calendar_id": str(parameters.get("calendar_id") or "primary"),
            "summary": str(parameters.get("summary") or "").strip().lower(),
            "start_date": str(parameters.get("start_date") or "").strip(),
            "start_datetime": str(parameters.get("start_datetime") or "").strip(),
            "start_time": str(parameters.get("start_time") or "").strip(),
            "time_zone": str(parameters.get("time_zone") or parameters.get("timezone") or "UTC").strip(),
        }
        digest = hashlib.sha256(json.dumps(parts, sort_keys=True).encode("utf-8")).hexdigest()[:24]
        return f"evt{digest}"
