"""Shared data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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

