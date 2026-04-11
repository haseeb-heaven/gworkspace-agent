"""Shared data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict, Optional, List
from pydantic import BaseModel, Field


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


@dataclass(slots=True)
class Intent:
    raw_text: str
    service: str | None = None
    action: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    needs_clarification: bool = False
    clarification_reason: str | None = None


class PlannedTask(BaseModel):
    id: str
    service: str
    action: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


class RequestPlan(BaseModel):
    raw_text: str
    tasks: List[PlannedTask] = Field(default_factory=list)
    summary: str = ""
    confidence: float = 0.0
    no_service_detected: bool = False
    source: str = "heuristic"


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


@dataclass(slots=True)
class ServiceSpec:
    key: str
    label: str
    aliases: tuple[str, ...]
    actions: dict[str, ActionSpec]


@dataclass(slots=True)
class ExecutionResult:
    success: bool
    command: list[str]
    stdout: str = ""
    stderr: str = ""
    return_code: int = -1
    error: str | None = None


@dataclass(slots=True)
class TaskExecution:
    task: PlannedTask
    result: ExecutionResult


@dataclass(slots=True)
class PlanExecutionReport:
    plan: RequestPlan
    executions: list[TaskExecution]

    @property
    def success(self) -> bool:
        return bool(self.executions) and all(item.result.success for item in self.executions)


class AgentState(TypedDict, total=False):
    """LangGraph state for the workspace workflow."""

    messages: list[Any]
    user_text: str
    plan: RequestPlan | None
    context: dict[str, Any]
    current_task_index: int
    executions: list[TaskExecution]
    error: str | None
    retry_count: int
    final_output: str


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

