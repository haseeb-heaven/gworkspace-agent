"""Human-readable output formatting for CLI and future GUI surfaces."""

from __future__ import annotations

import json
from typing import Any

from .models import ExecutionResult, PlanExecutionReport


class HumanReadableFormatter:
    """Formats command results without exposing raw JSON by default."""

    def format_execution_result(self, result: ExecutionResult) -> str:
        if not result.success:
            return result.stderr or result.error or "Command failed with unknown error."
        return self._format_stdout(result.stdout)

    def format_report(self, report: PlanExecutionReport) -> str:
        lines: list[str] = []
        if report.plan.summary:
            lines.append(report.plan.summary)
            lines.append("")
        for index, execution in enumerate(report.executions, start=1):
            task = execution.task
            result = execution.result
            status = "completed" if result.success else "failed"
            lines.append(f"{index}. {task.service}.{task.action} {status}.")
            detail = self.format_execution_result(result)
            if detail:
                lines.append(detail)
            if not result.success:
                break
            lines.append("")
        return "\n".join(line for line in lines if line is not None).strip()

    def _format_stdout(self, stdout: str) -> str:
        if not stdout:
            return "Command succeeded with no output."
        payload = _parse_json(stdout)
        if payload is None:
            return stdout.strip()
        if "messages" in payload or "resultSizeEstimate" in payload:
            messages = payload.get("messages") if isinstance(payload.get("messages"), list) else []
            estimate = payload.get("resultSizeEstimate")
            count = len(messages)
            if estimate is not None:
                estimated_count = _safe_int(estimate)
                prefix = f"Found an estimated {estimate} Gmail message{'s' if estimated_count != 1 else ''}."
            else:
                prefix = f"Found {count} Gmail message{'s' if count != 1 else ''}."
            if count:
                ids = ", ".join(str(item.get("id")) for item in messages[:5] if isinstance(item, dict) and item.get("id"))
                return f"{prefix}\nMessage IDs: {ids}" if ids else prefix
            return prefix
        if "values" in payload and isinstance(payload.get("values"), list):
            rows = payload.get("values") or []
            row_count = len(rows)
            cell_count = sum(len(row) for row in rows if isinstance(row, list))
            range_name = payload.get("range") or "the requested range"
            return f"Read {row_count} row{'s' if row_count != 1 else ''} and {cell_count} cell{'s' if cell_count != 1 else ''} from {range_name}."
        if "updates" in payload:
            updates = payload.get("updates") or {}
            cells = updates.get("updatedCells")
            rows = updates.get("updatedRows")
            target = updates.get("updatedRange") or payload.get("tableRange") or "the spreadsheet"
            if cells or rows:
                return f"Saved {rows or 0} row{'s' if rows != 1 else ''} and {cells or 0} cell{'s' if cells != 1 else ''} to {target}."
            return f"Saved rows to {target}."
        if "spreadsheetId" in payload:
            title = _nested(payload, "properties", "title") or "spreadsheet"
            url = payload.get("spreadsheetUrl")
            if url:
                return f"Created {title} in Google Sheets: {url}"
            return f"Created {title} in Google Sheets. Spreadsheet ID: {payload.get('spreadsheetId')}"
        if "labelIds" in payload and "id" in payload:
            return f"Email sent successfully. Message ID: {payload.get('id')}"
        if "files" in payload:
            files = payload.get("files") if isinstance(payload.get("files"), list) else []
            return f"Found {len(files)} Drive file{'s' if len(files) != 1 else ''}."
        if "items" in payload:
            items = payload.get("items") if isinstance(payload.get("items"), list) else []
            return f"Found {len(items)} item{'s' if len(items) != 1 else ''}."
        return _compact_json_summary(payload)


def _parse_json(stdout: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(stdout)
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _nested(payload: dict[str, Any], *keys: str) -> Any | None:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _compact_json_summary(payload: dict[str, Any]) -> str:
    keys = [key for key in payload.keys() if not key.startswith("@")]
    if not keys:
        return "Command succeeded."
    visible = ", ".join(keys[:6])
    return f"Command succeeded. Returned fields: {visible}."


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0
