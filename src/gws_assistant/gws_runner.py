"""Subprocess runner for gws binary."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from .models import ExecutionResult


class GWSRunner:
    """Runs gws commands with timeout and robust error handling."""

    def __init__(self, gws_binary_path: Path, logger: logging.Logger) -> None:
        self.gws_binary_path = gws_binary_path
        self.logger = logger

    def validate_binary(self) -> bool:
        exists = self.gws_binary_path.exists() and self.gws_binary_path.is_file()
        if not exists:
            self.logger.error("gws binary was not found at %s", self.gws_binary_path)
        return exists

    def run(self, args: list[str], timeout_seconds: int = 90) -> ExecutionResult:
        command = [str(self.gws_binary_path), *args]
        self.logger.info("Executing command: %s", " ".join(command))
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )
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
                error=f"Command timed out after {timeout_seconds}s.",
            )
        except Exception as exc:
            self.logger.exception("Unexpected command execution error: %s", exc)
            return ExecutionResult(
                success=False,
                command=command,
                error=str(exc),
            )

