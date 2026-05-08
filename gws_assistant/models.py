"""Shared data models."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypedDict


@dataclass(slots=True)
class AppConfigModel:
    provider: str
    model: str
    api_key: str | None
    base_url: str | None
    timeout_seconds: int
    gws_binary_path: Path
    log_file_path: Path
    log_level: str
    verbose: bool
    env_file_path: Path
    setup_complete: bool
    max_retries: int
    langchain_enabled: bool
    max_tokens: int | None = None
    temperature: float = 0.0
    max_replans: int = 1
    use_heuristic_fallback: bool = True
    code_execution_enabled: bool = True
    code_execution_backend: str = "local"
    code_execution_timeout_seconds: int = 5
    e2b_api_key: str | None = None
    gws_timeout_seconds: int = 180
    gws_max_retries: int = 3
    llm_api_keys: list[str] = field(default_factory=list)
    max_context_snippet_len: int = 300
    default_recipient_email: str = ""
    drive_folder_name: str = "New Folder"
    mem0_api_key: str | None = None
    mem0_user_id: str | None = None
    mem0_host: str | None = None
    memory_dir: Path | None = None
    memory_type: str = "local"
    mem0_local_storage_path: str = ".gemini/memories.jsonl"
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_confirmation_timeout_seconds: float = 60.0
    sandbox_enabled: bool = True
    read_only_mode: bool = True
    llm_fallback_models: list[str] = field(default_factory=list)
    groq_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None
    anthropic_api_key: str | None = None
    mistral_api_key: str | None = None
    ollama_api_base: str | None = None
    dry_run: bool = False
    no_confirm: bool = False
    force_dangerous: bool = False
    is_telegram: bool = False
    # NOTE: Must NOT use a leading underscore here.
    # @dataclass(slots=True) does not persist mutations to underscore-prefixed
    # fields between method calls — the slot write is silently dropped, causing
    # rotate_api_key() to always read index 0 and always jump to index 1.
    current_key_idx: int = 0
    rotation_lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    # Verification Engine Configuration
    verification_exact_placeholders: set[str] = field(default_factory=lambda: {
        "none", "null", "n/a", "na", "undefined",
        "todo", "fixme", "placeholder", "example", "sample", "dummy",
        "your_value", "insert_here", "replace_me", "changeme", "default",
        "fake", "mock", "temporary", "tbd", "missing"
    })
    verification_numeric_placeholders: set[str] = field(default_factory=lambda: {"0000", "1234", "9999", "00000000"})
    verification_exact_emails: set[str] = field(default_factory=lambda: {"noreply@domain.com", "noreply@example.com"})
    verification_email_placeholder_domains: list[str] = field(default_factory=lambda: ["@test.com"])
    verification_destructive_operations: set[str] = field(default_factory=lambda: {
        "drive_delete_file", "drive_empty_trash", "drive_move_to_trash", "drive_batch_delete",
        "gmail_delete_message", "gmail_trash_message", "gmail_batch_delete", "gmail_empty_trash",
        "sheets_delete_spreadsheet", "sheets_clear_all_data", "sheets_delete_sheet_tab",
        "docs_delete_document",
        "calendar_delete_event", "calendar_delete_calendar",
        "contacts_delete_contact",
    })
    verification_bulk_indicators: list[str] = field(default_factory=lambda: ["batch", "bulk", "multiple"])
    verification_id_fields: list[str] = field(default_factory=lambda: [
        "file_id", "document_id", "spreadsheet_id", "message_id", "event_id", "task_id", "contact_id"
    ])
    verification_content_fields: list[str] = field(default_factory=lambda: ["body", "content", "message", "text", "description"])
    verification_create_id_fields: list[str] = field(default_factory=lambda: [
        "id", "documentId", "spreadsheetId", "fileId", "messageId",
        "resourceName", "threadId", "name", "formId", "taskId", "contactId", "presentationId"
    ])
    verification_suspicious_patterns: dict[str, str] = field(default_factory=lambda: {
        "delete_all": r"delete.*all",
        "remove_everything": r"remove.*everything",
        "wipe_all": r"wipe.*all",
        "clear_all": r"clear.*all",
    })

    def rotate_api_key(self) -> str | None:
        keys = self.llm_api_keys
        if not keys:
            return self.api_key

        with self.rotation_lock:
            self.current_key_idx = (self.current_key_idx + 1) % len(keys)
            new_key = keys[self.current_key_idx]
            self.api_key = new_key
            return new_key

    def api_model_name(self) -> str:
        """Strips the LiteLLM provider prefix from the model name."""
        for prefix in ("openrouter/", "groq/", "ollama/"):
            if self.model.startswith(prefix):
                return self.model[len(prefix) :]
        return self.model


@dataclass(slots=True)
class Intent:
    raw_text: str
    service: str | None = None
    action: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    needs_clarification: bool = False
    clarification_reason: str | None = None


@dataclass(slots=True)
class PlannedTask:
    id: str
    service: str
    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    # NOTE: Same slots=True rule applies — no leading underscore.
    sequence_index: int = 0

    def is_destructive(self, destructive_ops: set[str] | None = None) -> bool:
        """Check if this task is a destructive operation.

        Args:
            destructive_ops: Optional set of full tool names (service_action)
                           that are considered destructive. If provided,
                           this takes precedence over the default list.
        """
        full_name = f"{self.service}_{self.action}"
        if destructive_ops is not None:
            return full_name in destructive_ops

        # Default fallback list of known destructive actions
        destructive = {
            "drive": ["delete_file", "empty_trash", "move_to_trash", "batch_delete"],
            "gmail": ["delete_message", "trash_message", "batch_delete", "empty_trash"],
            "sheets": ["delete_spreadsheet", "clear_all_data", "delete_sheet_tab"],
            "docs": ["delete_document"],
            "calendar": ["delete_event", "delete_calendar"],
            "contacts": ["delete_contact"],
        }
        return self.service in destructive and self.action in destructive.get(self.service, [])


# ---------------------------------------------------------------------------
# Fix #1 — PlannedTask schema validation
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """Raised when a planned task or command fails schema/semantic validation."""


def validate_planned_task(task: "PlannedTask") -> None:
    """Validate that a PlannedTask is structurally sound before execution.

    Raises ValidationError with a clear message if anything is wrong.
    This is the planner->executor contract enforcement point.
    """
    if not task.id or not str(task.id).strip():
        raise ValidationError("PlannedTask.id is empty or missing.")
    if not task.service or not str(task.service).strip():
        raise ValidationError(f"PlannedTask id={task.id!r} has empty service.")
    if not task.action or not str(task.action).strip():
        raise ValidationError(f"PlannedTask id={task.id!r} service={task.service!r} has empty action.")
    if task.parameters is None:
        raise ValidationError(
            f"PlannedTask id={task.id!r} {task.service}.{task.action}: parameters is None — must be dict."
        )
    if not isinstance(task.parameters, dict):
        raise ValidationError(
            f"PlannedTask id={task.id!r} {task.service}.{task.action}: "
            f"parameters must be dict, got {type(task.parameters).__name__}."
        )
    # Detect obviously unresolved placeholder values that should have been
    # caught by _resolve_task but slipped through.
    # Skip validation for certain parameters that may contain intentional placeholders
    # or where we want to let the execution fail with a real error instead of a validation error.
    _STUB_PATTERNS = (
        "{{task",
        "$gmail_message_ids",
        "PLACEHOLDER_",
        "___UNRESOLVED_PLACEHOLDER___",
        "{{spreadsheet_id}}",
        "{{document_id}}",
        "{{file_id}}",
        "{{message_id}}",
    )
    for key, val in task.parameters.items():
        # Skip body parameter validation for Gmail send_message
        if task.service == "gmail" and task.action == "send_message" and key == "body":
            continue
        # Skip code parameter validation for code.execute - allow it to fail in sandbox
        if task.service in ("code", "computation") and task.action == "execute" and key == "code":
            continue
        # Skip file_id validation for drive.export_file - may be resolved from empty list
        if task.service == "drive" and task.action == "export_file" and key == "file_id":
            continue

        if isinstance(val, str):
            for pat in _STUB_PATTERNS:
                if pat in val:
                    raise ValidationError(
                        f"PlannedTask id={task.id!r} {task.service}.{task.action}: "
                        f"parameter '{key}' contains unresolved stub \"{val}\"."
                    )


@dataclass(slots=True)
class RequestPlan:
    raw_text: str
    tasks: list[PlannedTask] = field(default_factory=list)
    summary: str = ""
    confidence: float = 0.0
    no_service_detected: bool = False
    source: str = "heuristic"
    needs_web_search: bool = False
    needs_code_execution: bool = False


@dataclass(slots=True)
class ParameterSpec:
    name: str
    prompt: str
    example: str
    required: bool = True


@dataclass(slots=True)
class ActionSpec:
    key: str
    label: str
    keywords: tuple[str, ...]
    negative_keywords: tuple[str, ...] = ()
    parameters: tuple[ParameterSpec, ...] = ()
    description: str = ""


@dataclass(slots=True)
class ServiceSpec:
    key: str
    label: str
    aliases: tuple[str, ...]
    actions: dict[str, ActionSpec]
    description: str = ""


@dataclass(slots=True)
class ExecutionResult:
    success: bool
    command: list[str]
    stdout: str = ""
    stderr: str = ""
    return_code: int = -1
    error: str | None = None
    output: Any = None

    def to_structured_result(self) -> StructuredToolResult:
        payload = (
            self.output
            if self.output is not None
            else {
                "command": self.command,
                "stdout": self.stdout,
                "stderr": self.stderr,
                "return_code": self.return_code,
            }
        )
        return StructuredToolResult(success=self.success, output=payload, error=self.error)


@dataclass(slots=True)
class TaskExecution:
    task: PlannedTask
    result: ExecutionResult


@dataclass(slots=True)
class PlanExecutionReport:
    plan: RequestPlan
    executions: list[TaskExecution]
    thought_trace: list[dict] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return bool(self.executions) and all(item.result.success for item in self.executions)


class AgentState(TypedDict, total=False):
    """LangGraph state for the workspace workflow."""

    messages: list[Any]
    conversation_history: list[Any]
    user_text: str
    plan: RequestPlan | None
    context: dict[str, Any]
    current_task_index: int
    executions: list[TaskExecution]
    error: str | None
    retry_count: int
    final_output: str
    last_result: StructuredToolResult | None
    reflection: ReflectionDecision | None
    current_attempt: int
    thought_trace: list[dict]
    abort_plan: bool
    intent_verification: dict[str, Any] | None
    verification_attempts: int


class StructuredToolResult(TypedDict):
    success: bool
    output: Any
    error: str | None


@dataclass(slots=True)
class ReflectionDecision:
    action: Literal["continue", "retry", "replan"]
    reason: str = ""
    replacement_plan: RequestPlan | None = None


@dataclass(slots=True)
class WebSearchResult:
    """Result from a web search tool invocation."""

    query: str
    results: list[dict[str, str]] = field(default_factory=list)
    summary: str = ""
    error: str | None = None


@dataclass(slots=True)
class CodeExecutionResult:
    """Result from sandboxed code execution."""

    code: str
    stdout: str = ""
    stderr: str = ""
    return_value: Any = None
    success: bool = False
    error: str | None = None
