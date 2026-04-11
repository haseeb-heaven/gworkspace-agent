"""Code execution tool for the LangChain agent."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.tools import tool


@dataclass(frozen=True, slots=True)
class SandboxSettings:
    enabled: bool
    backend: str
    timeout_seconds: int
    memory_mb: int
    max_output: int
    docker_image: str
    docker_binary: str


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_backend(value: str | None) -> str:
    candidate = (value or "restricted_subprocess").strip().lower().replace("-", "_")
    if candidate in {"subprocess", "restricted", "restrictedpython"}:
        return "restricted_subprocess"
    if candidate in {"restricted_subprocess", "docker", "e2b"}:
        return candidate
    return "restricted_subprocess"


def _load_settings() -> SandboxSettings:
    return SandboxSettings(
        enabled=_to_bool(os.getenv("CODE_EXECUTION_ENABLED"), default=True),
        backend=_normalize_backend(os.getenv("CODE_EXECUTION_BACKEND")),
        timeout_seconds=max(int(os.getenv("CODE_EXECUTION_TIMEOUT_SECONDS", "10")), 1),
        memory_mb=max(int(os.getenv("CODE_EXECUTION_MEMORY_MB", "64")), 16),
        max_output=max(int(os.getenv("CODE_EXECUTION_MAX_OUTPUT", "8192")), 256),
        docker_image=(os.getenv("CODE_EXECUTION_DOCKER_IMAGE") or "gws-sandbox:latest").strip(),
        docker_binary=(os.getenv("CODE_EXECUTION_DOCKER_BINARY") or "docker").strip(),
    )


def _result(code: str, *, stdout: str = "", stderr: str = "", success: bool = False, error: str | None = None) -> dict[str, Any]:
    return {
        "code": code,
        "stdout": stdout,
        "stderr": stderr,
        "success": success,
        "error": error,
    }


def _trim_output(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...(TRUNCATED)"


def _parse_payload(stdout: str) -> dict[str, Any] | None:
    lines = [line for line in (stdout or "").splitlines() if line.strip()]
    if not lines:
        return None
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _run_restricted_subprocess(code: str, settings: SandboxSettings) -> dict[str, Any]:
    code_b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")
    env = os.environ.copy()
    env["CODE_EXECUTION_TIMEOUT_SECONDS"] = str(settings.timeout_seconds)
    env["CODE_EXECUTION_MEMORY_MB"] = str(settings.memory_mb)
    env["CODE_EXECUTION_MAX_OUTPUT"] = str(settings.max_output)
    inner_script = Path(__file__).with_name("code_execution_inner.py")

    try:
        proc = subprocess.run(
            [sys.executable, str(inner_script)],
            input=code_b64,
            text=True,
            capture_output=True,
            timeout=settings.timeout_seconds + 1,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return _result(code, error=f"TimeoutError: Execution exceeded {settings.timeout_seconds} seconds.")
    except Exception as exc:
        return _result(code, error=f"InternalError: {exc}")

    payload = _parse_payload(proc.stdout)
    if payload is None:
        if proc.returncode != 0:
            return _result(
                code,
                stdout=_trim_output(proc.stdout or "", settings.max_output),
                stderr=_trim_output(proc.stderr or "", settings.max_output),
                error=f"Process exited with code {proc.returncode}",
            )
        return _result(
            code,
            stdout=_trim_output(proc.stdout or "", settings.max_output),
            stderr=_trim_output(proc.stderr or "", settings.max_output),
            error="Failed to parse sandbox output as JSON",
        )

    return _result(
        code,
        stdout=_trim_output(str(payload.get("stdout") or ""), settings.max_output),
        stderr=_trim_output((proc.stderr or "") + str(payload.get("stderr") or ""), settings.max_output),
        success=bool(payload.get("success")),
        error=payload.get("error"),
    )


def _run_docker_sandbox(code: str, settings: SandboxSettings) -> dict[str, Any]:
    code_b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")
    timeout = settings.timeout_seconds + 2
    try:
        proc = subprocess.run(
            [
                settings.docker_binary,
                "run",
                "--rm",
                "--memory",
                f"{settings.memory_mb}m",
                "--pids-limit",
                "64",
                "--network",
                "none",
                "--user",
                "sandbox",
                "-e",
                f"CODE_EXECUTION_TIMEOUT_SECONDS={settings.timeout_seconds}",
                "-e",
                f"CODE_EXECUTION_MEMORY_MB={settings.memory_mb}",
                "-e",
                f"CODE_EXECUTION_MAX_OUTPUT={settings.max_output}",
                "-i",
                settings.docker_image,
            ],
            input=code_b64,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return _result(code, error=f"TimeoutError: container execution exceeded {timeout} seconds.")
    except Exception as exc:
        return _result(code, error=f"ContainerError: {exc}")

    payload = _parse_payload(proc.stdout)
    if payload is None:
        return _result(
            code,
            stdout=_trim_output(proc.stdout or "", settings.max_output),
            stderr=_trim_output(proc.stderr or "", settings.max_output),
            error="Failed to parse container JSON output",
        )

    return _result(
        code,
        stdout=_trim_output(str(payload.get("stdout") or ""), settings.max_output),
        stderr=_trim_output((proc.stderr or "") + str(payload.get("stderr") or ""), settings.max_output),
        success=bool(payload.get("success")),
        error=payload.get("error"),
    )


def _run_e2b_sandbox(code: str, settings: SandboxSettings) -> dict[str, Any]:
    if not (os.getenv("E2B_API_KEY") or "").strip():
        return _result(code, error="E2BImportError: E2B_API_KEY is required when CODE_EXECUTION_BACKEND=e2b.")

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    result_chunks: list[str] = []
    error_chunks: list[str] = []
    sandbox: Any = None

    def on_stdout(message: Any) -> None:
        line = getattr(message, "line", None)
        if line is not None:
            stdout_lines.append(str(line))

    def on_stderr(message: Any) -> None:
        line = getattr(message, "line", None)
        if line is not None:
            stderr_lines.append(str(line))

    def on_result(item: Any) -> None:
        rendered = str(item).strip()
        if rendered:
            result_chunks.append(rendered)

    def on_error(item: Any) -> None:
        name = getattr(item, "name", "ExecutionError")
        value = getattr(item, "value", str(item))
        error_chunks.append(f"{name}: {value}")

    try:
        try:
            from e2b_code_interpreter import CodeInterpreter

            sandbox = CodeInterpreter()
        except ImportError:
            from e2b_code_interpreter import Sandbox

            sandbox = Sandbox.create() if hasattr(Sandbox, "create") else Sandbox()
    except Exception as exc:
        return _result(code, error=f"E2BImportError: {exc}")

    try:
        execution = sandbox.run_code(
            code,
            on_stdout=on_stdout,
            on_stderr=on_stderr,
            on_result=on_result,
            on_error=on_error,
            timeout=float(settings.timeout_seconds),
            request_timeout=float(settings.timeout_seconds + 5),
        )
    except Exception as exc:
        return _result(code, error=f"E2BExecutionError: {exc}")
    finally:
        close = getattr(sandbox, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass

    if getattr(execution, "text", None):
        result_chunks.append(str(execution.text))
    if getattr(execution, "stdout", None):
        stdout_lines.append(str(execution.stdout))
    if getattr(execution, "stderr", None):
        stderr_lines.append(str(execution.stderr))

    stdout = "\n".join(part for part in ["\n".join(stdout_lines).strip(), "\n".join(result_chunks).strip()] if part).strip()
    stderr = "\n".join(stderr_lines).strip()
    error = "\n".join(error_chunks).strip() or None
    return _result(
        code,
        stdout=_trim_output(stdout, settings.max_output),
        stderr=_trim_output(stderr, settings.max_output),
        success=error is None,
        error=error,
    )


@tool
def code_execution_tool(code: str) -> dict[str, Any]:
    """
    Execute Python code using the configured sandbox backend.

    Backends:
    - `restricted_subprocess`: RestrictedPython in a local subprocess.
    - `docker`: RestrictedPython inside a Docker container.
    - `e2b`: remote sandbox via the E2B code interpreter SDK.
    """
    settings = _load_settings()
    if not settings.enabled:
        return _result(code, error="Code execution is disabled. Set CODE_EXECUTION_ENABLED=true to enable it.")

    if settings.backend == "docker":
        return _run_docker_sandbox(code, settings)
    if settings.backend == "e2b":
        return _run_e2b_sandbox(code, settings)
    return _run_restricted_subprocess(code, settings)
