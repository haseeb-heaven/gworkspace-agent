"""Subprocess runner for gws binary."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from .models import AppConfigModel, ExecutionResult

# Windows CreateProcess has a hard limit of ~32 767 characters for the entire
# command-line string.  Any single CLI argument larger than this threshold will
# trigger WinError 206 ("The filename or extension is too long").  We use a
# conservative threshold so the total command stays well below that ceiling.
_WIN_ARG_SAFE_BYTES = 8_000


def _args_too_long(args: list[str]) -> bool:
    """Return True when any single arg exceeds the safe Windows CLI threshold."""
    return os.name == "nt" and any(len(a.encode("utf-8", errors="replace")) > _WIN_ARG_SAFE_BYTES for a in args)


def _rewrite_large_args_via_tempfile(
    args: list[str],
) -> tuple[list[str], list[str], str | None]:
    """Rewrite oversized --json / --params values.

    Returns:
        (new_args, temp_files_to_cleanup, stdin_content | None)

    Strategy
    --------
    If a --json or --params value is too large for Windows CLI limits,
    we pass it via stdin using the '-' sentinel.
    Note: 'gws' does not support --json-file, so we MUST use stdin.
    Currently, we only support ONE oversized value via stdin.
    """
    new_args: list[str] = []
    stdin_content: str | None = None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--json", "--params") and i + 1 < len(args) and stdin_content is None:
            value = args[i + 1]
            if len(str(value).encode("utf-8", errors="replace")) > _WIN_ARG_SAFE_BYTES:
                stdin_content = value
                new_args.extend([arg, "-"])
                i += 2
                continue
        new_args.append(arg)
        i += 1
    return new_args, [], stdin_content


class GWSRunner:
    """Runs gws commands with timeout and robust error handling."""

    def __init__(self, gws_binary_path: Path, logger: logging.Logger, config: AppConfigModel | None = None) -> None:
        self.gws_binary_path = gws_binary_path
        self.logger = logger
        self.config = config

    def validate_binary(self) -> bool:
        exists = self.gws_binary_path.exists() and self.gws_binary_path.is_file()
        if not exists:
            self.logger.error("gws binary was not found at %s", self.gws_binary_path)
        return exists

    def run(self, args: list[str], timeout_seconds: int | None = None) -> ExecutionResult:
        timeout = timeout_seconds if timeout_seconds is not None else (self.config.gws_timeout_seconds if self.config else 90)
        command = [str(self.gws_binary_path), *args]

        # ------------------------------------------------------------------
        # Fix: WinError 206 — guard against oversized CLI arguments
        # ------------------------------------------------------------------
        tmp_files: list[str] = []
        stdin_input: str | None = None
        if _args_too_long(command):
            self.logger.warning(
                "Oversized CLI arg detected (WinError 206 risk); rewriting large args to temp files."
            )
            command, tmp_files, stdin_input = _rewrite_large_args_via_tempfile(command)

        self.logger.info("Executing command: %s", " ".join(a[:80] if len(a) > 80 else a for a in command))
        try:
            proc_kwargs: dict[str, Any] = dict(
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            if stdin_input:
                proc_kwargs["input"] = stdin_input

            result = subprocess.run(command, **proc_kwargs)

            # Cleanup temp files if any were created
            for f in tmp_files:
                try:
                    os.remove(f)
                except Exception:
                    pass

            return ExecutionResult(
                success=result.returncode == 0,
                command=command,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            self.logger.error("Command timed out after %d seconds: %s", timeout, " ".join(command))
            return ExecutionResult(
                success=False,
                command=command,
                stdout="",
                stderr=f"Command timed out after {timeout} seconds.",
                return_code=-1,
            )
        except Exception as exc:
            self.logger.exception("Failed to run gws command: %s", exc)
            return ExecutionResult(
                success=False,
                command=command,
                stdout="",
                stderr=str(exc),
                return_code=-1,
            )
