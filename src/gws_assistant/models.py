"""Shared data models."""

from __future__ import annotations

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
    max_replans: int = 1
    use_heuristic_fallback: bool = True
    code_execution_enabled: bool = True
    code_execution_backend: str = "local"
    e2b_api_key: str | None = None
    gws_timeout_seconds: int = 90
    gws_max_retries: int = 3
    max_context_snippet_len: int = 300


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


# ---------------------------------------------------------------------------
# Fix #1 — PlannedTask schema validation
# ---------------------------------------------------------------------------

from .exceptions import ValidationError  # noqa: E402  (after class defs to avoid circular import)


def validate_planned_task(task: "PlannedTask") -> None:
    """Validate that a PlannedTask is structurally sound before execution.

    Raises ValidationError with a clear message if anything is wrong.
    This is the planner→executor contract enforcement point.
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
    _STUB_PATTERNS = ("{{task", "{task-", "$gmail_message_ids", "PLACEHOLDER_")
    for key, val in task.parameters.items():
        if isinstance(val, str):
            for pat in _STUB_PATTERNS:
                if pat in val:
                    raise ValidationError(
                        f"PlannedTask id={task.id!r} {task.service}.{task.action}: "
                        f"parameter {key!r} contains unresolved stub {val!r}."
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
        payload = self.output if self.output is not None else {
            "command": self.command,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "return_code": self.return_code,
        }
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
