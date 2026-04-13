"""Subprocess runner for gws binary."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import time
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
    """Rewrite oversized --json / --params values to a temporary file.

    Returns:
        (new_args, temp_files_to_cleanup, stdin_content | None)

    Strategy
    --------
    For each ``--json VALUE`` or ``--params VALUE`` pair where VALUE is too
    large we write VALUE to a ``*.tmp`` file and replace the pair with
    ``--json-file PATH`` / ``--params-file PATH``.

    If the gws binary does not support ``*-file`` flags we fall back to
    passing the *first* oversized value through stdin (``--json -`` sentinel)
    and drop it from the arg list so subprocess receives a short command line.
    The caller must then pass ``input=stdin_content`` to subprocess.run.
    """
    new_args: list[str] = []
    tmp_files: list[str] = []
    stdin_content: str | None = None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--json", "--params") and i + 1 < len(args):
            value = args[i + 1]
            if len(value.encode("utf-8", errors="replace")) > _WIN_ARG_SAFE_BYTES:
                # Write to a temp file; gws may support --json-file / --params-file
                fd, tmp_path = tempfile.mkstemp(suffix=".tmp", prefix="gws_arg_")
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as fh:
                        fh.write(value)
                except Exception:
                    os.close(fd)
                tmp_files.append(tmp_path)
                file_flag = f"{arg}-file"
                new_args.extend([file_flag, tmp_path])
                i += 2
                continue
        new_args.append(arg)
        i += 1
    return new_args, tmp_files, stdin_content


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
                check=False,
            )
            if stdin_input is not None:
                proc_kwargs["input"] = stdin_input

            result = subprocess.run(command, **proc_kwargs)
            success = result.returncode == 0
            if success:
                self.logger.info("Command completed successfully with code=%s", result.returncode)
            else:
                self.logger.warning(
                    "Command failed with code=%s stderr=%s",
                    result.returncode,
                    (result.stderr or "").strip()[:500],
                )
            return ExecutionResult(
                success=success,
                command=command,
                stdout=(result.stdout or "").strip(),
                stderr=(result.stderr or "").strip(),
                return_code=result.returncode,
            )
        except subprocess.TimeoutExpired as exc:
            self.logger.exception("Command timed out: %s", exc)
            return ExecutionResult(
                success=False,
                command=command,
                error=f"Command timed out after {timeout}s.",
            )
        except Exception as exc:
            self.logger.exception("Unexpected command execution error: %s", exc)
            return ExecutionResult(
                success=False,
                command=command,
                error=str(exc),
            )
        finally:
            for tmp_path in tmp_files:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def run_with_retry(self, args: list[str], timeout_seconds: int | None = None, max_retries: int | None = None) -> ExecutionResult:
        """Runs the command with exponential backoff for transient errors."""
        timeout       = timeout_seconds if timeout_seconds is not None else (self.config.gws_timeout_seconds if self.config else 90)
        retries_limit = max_retries if max_retries is not None else (self.config.gws_max_retries if self.config else 3)

        for attempt in range(1, retries_limit + 1):
            result = self.run(args, timeout_seconds=timeout)
            if result.success:
                return result

            error_msg = str(result.error).lower() + str(result.stderr).lower()
            is_transient = result.return_code in (429, 500, 502, 503, 504) or any(
                term in error_msg
                for term in ["timeout", "429", "500", "502", "503", "504", "quota", "connection reset", "network", "transient"]
            )

            if is_transient and attempt < retries_limit:
                sleep_time = 2 ** attempt
                self.logger.warning(
                    "Transient error on attempt %d. Retrying in %ds... Error: %s | %s",
                    attempt, sleep_time, result.error, result.stderr,
                )
                time.sleep(sleep_time)
            else:
                if attempt == retries_limit and not result.success:
                    self.logger.error(
                        "Command execution failed permanently after %d attempts: %s | %s",
                        attempt, result.error, result.stderr,
                    )
                return result
        return result
