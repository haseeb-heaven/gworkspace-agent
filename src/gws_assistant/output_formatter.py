"""Human-readable output formatting for CLI and future GUI surfaces."""

from __future__ import annotations

import json
import unicodedata
from typing import Any

from .models import ExecutionResult, PlanExecutionReport


class HumanReadableFormatter:
    """Formats command results without exposing raw JSON by default."""

    def format_execution_result(self, result: ExecutionResult) -> str:
        if not result.success:
            return _clean_text(result.stderr or result.error or "Command failed with unknown error.")
        return _clean_text(self._format_stdout(result.stdout))

    def format_report(self, plan: RequestPlan, executions: list[TaskExecution]) -> str:
        lines: list[str] = []
        if plan.summary:
            lines.append(_clean_text(plan.summary))
            lines.append("")
        for index, execution in enumerate(executions, start=1):
            task = execution.task
            result = execution.result
            status = "completed" if result.success else "failed"
            lines.append(_clean_text(f"{index}. {task.service}.{task.action} {status}."))
            detail = self.format_execution_result(result)
            if detail:
                lines.append(detail)
            if not result.success:
                break
            lines.append("")
        return _clean_text("\n".join(line for line in lines if line is not None).strip())

    def _format_stdout(self, stdout: str) -> str:
        if not stdout:
            return "Command succeeded with no output."
        payload = _parse_json(stdout)
        if payload is None:
            return _clean_text(stdout.strip())
        if "id" in payload and "payload" in payload:
            return _format_gmail_message(payload)
        if "messages" in payload or "resultSizeEstimate" in payload:
            return _format_gmail_list(payload)
        if "values" in payload and isinstance(payload.get("values"), list):
            rows = payload.get("values") or []
            row_count = len(rows)
            cell_count = sum(len(row) for row in rows if isinstance(row, list))
            range_name = payload.get("range") or "the requested range"
            preview = _tabular_preview(rows)
            summary = f"Read {row_count} row{'s' if row_count != 1 else ''} and {cell_count} cell{'s' if cell_count != 1 else ''} from {range_name}."
            return _clean_text(f"{summary}\n{preview}" if preview else summary)
        if "updates" in payload:
            updates = payload.get("updates") or {}
            cells = updates.get("updatedCells")
            rows = updates.get("updatedRows")
            target = updates.get("updatedRange") or payload.get("tableRange") or "the spreadsheet"
            if cells or rows:
                return _clean_text(f"Saved {rows or 0} row{'s' if rows != 1 else ''} and {cells or 0} cell{'s' if cells != 1 else ''} to {target}.")
            return _clean_text(f"Saved rows to {target}.")
        if "spreadsheetId" in payload:
            title = _nested(payload, "properties", "title") or "spreadsheet"
            url = payload.get("spreadsheetUrl")
            if url:
                return _clean_text(f"Created {title} in Google Sheets: {url}")
            return _clean_text(f"Created {title} in Google Sheets. Spreadsheet ID: {payload.get('spreadsheetId')}")
        if "labelIds" in payload and "id" in payload:
            return _clean_text(f"Email sent successfully. Message ID: {payload.get('id')}")
        if "files" in payload:
            return _format_drive_files(payload)
        if "connections" in payload and isinstance(payload.get("connections"), list):
            return _format_contacts(payload)
        if "slides" in payload and "presentationId" in payload:
            return _format_slides(payload)
        if "documentId" in payload and ("title" in payload or "body" in payload):
            return _format_docs(payload)
        if "items" in payload and isinstance(payload.get("items"), list):
            return _format_calendar_items(payload)
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
        return _clean_text("Command succeeded.")
    visible = ", ".join(keys[:6])
    return _clean_text(f"Command succeeded. Returned fields: {visible}.")


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _format_gmail_list(payload: dict[str, Any]) -> str:
    messages = payload.get("messages") if isinstance(payload.get("messages"), list) else []
    estimate = payload.get("resultSizeEstimate")
    count = len(messages)
    if estimate is not None:
        estimated_count = _safe_int(estimate)
        prefix = f"Found an estimated {estimate} Gmail message{'s' if estimated_count != 1 else ''}."
    else:
        prefix = f"Found {count} Gmail message{'s' if count != 1 else ''}."
    return _clean_text(prefix)


def _format_gmail_message(payload: dict[str, Any]) -> str:
    headers = _gmail_headers(payload)
    snippet = str(payload.get("snippet") or "")
    subject = headers.get("subject", "(no subject)")
    sender = headers.get("from", "(unknown sender)")
    date = headers.get("date", "")
    pieces = [
        f"From: {sender}",
        f"Subject: {subject}",
    ]
    if date:
        pieces.append(f"Date: {date}")
    if snippet:
        pieces.append(f"Snippet: {snippet}")
    return _clean_text("\n".join(pieces))


def _format_drive_files(payload: dict[str, Any]) -> str:
    files = payload.get("files") if isinstance(payload.get("files"), list) else []
    header = f"Found {len(files)} Drive file{'s' if len(files) != 1 else ''}."
    if not files:
        return header
    rows = [["Name", "Type", "Link"]]
    for item in files[:20]:
        if isinstance(item, dict):
            rows.append(
                [
                    str(item.get("name") or ""),
                    _short_mime_type(str(item.get("mimeType") or "")),
                    str(item.get("webViewLink") or ""),
                ]
            )
    preview = _tabular_preview(rows)
    return _clean_text(f"{header}\n{preview}" if preview else header)


def _format_contacts(payload: dict[str, Any]) -> str:
    connections = payload.get("connections") if isinstance(payload.get("connections"), list) else []
    header = f"Found {len(connections)} contact{'s' if len(connections) != 1 else ''}."
    if not connections:
        return header
    rows = [["Name", "Email", "Phone"]]
    for person in connections[:20]:
        if not isinstance(person, dict):
            continue
        rows.append(
            [
                _first_nested_value(person.get("names"), "displayName"),
                _first_nested_value(person.get("emailAddresses"), "value"),
                _first_nested_value(person.get("phoneNumbers"), "value"),
            ]
        )
    preview = _tabular_preview(rows)
    return _clean_text(f"{header}\n{preview}" if preview else header)


def _format_slides(payload: dict[str, Any]) -> str:
    title = str(payload.get("title") or "presentation")
    slides = payload.get("slides") if isinstance(payload.get("slides"), list) else []
    return _clean_text(f"Presentation: {title}\nSlides: {len(slides)}\nPresentation ID: {payload.get('presentationId')}")


def _format_docs(payload: dict[str, Any]) -> str:
    title = str(payload.get("title") or "document")
    doc_id = str(payload.get("documentId") or "")
    snippet = _docs_snippet(payload)
    lines = [f"Document: {title}", f"Document ID: {doc_id}"]
    if snippet:
        lines.append(f"Preview: {snippet}")
    return _clean_text("\n".join(lines))


def _format_calendar_items(payload: dict[str, Any]) -> str:
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    header = f"Found {len(items)} calendar event{'s' if len(items) != 1 else ''}."
    if not items:
        return header
    rows = [["Summary", "Start", "End", "ID"]]
    for event in items[:20]:
        if isinstance(event, dict):
            start = _nested(event, "start", "dateTime") or _nested(event, "start", "date") or ""
            end = _nested(event, "end", "dateTime") or _nested(event, "end", "date") or ""
            rows.append([str(event.get("summary") or ""), str(start), str(end), str(event.get("id") or "")])
    preview = _tabular_preview(rows)
    return _clean_text(f"{header}\n{preview}" if preview else header)


def _tabular_preview(rows: list[list[Any]], max_rows: int = 12, max_col_width: int = 42) -> str:
    if not rows:
        return ""
    clipped_rows = rows[:max_rows]
    column_count = max(len(row) for row in clipped_rows)
    normalized = []
    for row in clipped_rows:
        cells = [_clip_cell(cell, max_col_width) for cell in row]
        if len(cells) < column_count:
            cells.extend([""] * (column_count - len(cells)))
        normalized.append(cells)
    widths = [max(len(str(row[col])) for row in normalized) for col in range(column_count)]
    rendered: list[str] = []
    for row_index, row in enumerate(normalized):
        rendered.append(" | ".join(str(cell).ljust(widths[col]) for col, cell in enumerate(row)))
        if row_index == 0:
            rendered.append("-+-".join("-" * width for width in widths))
    if len(rows) > max_rows:
        rendered.append(f"... {len(rows) - max_rows} more row(s)")
    return _clean_text("\n".join(rendered))


def _clip_cell(value: Any, max_width: int) -> str:
    text = _clean_text(str(value or "").replace("\n", " ").strip())
    if len(text) <= max_width:
        return text
    return text[: max_width - 3] + "..."


def _first_nested_value(items: Any, key: str) -> str:
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item.get(key):
                return str(item.get(key))
    return ""


def _short_mime_type(mime: str) -> str:
    mapping = {
        "application/vnd.google-apps.folder": "Folder",
        "application/vnd.google-apps.spreadsheet": "Sheet",
        "application/vnd.google-apps.document": "Doc",
        "application/vnd.google-apps.presentation": "Slide",
        "application/vnd.google-apps.form": "Form",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word",
        "application/pdf": "PDF",
        "image/jpeg": "Image",
        "image/png": "Image",
        "text/plain": "Text",
    }
    return mapping.get(mime, mime.split("/")[-1].split(".")[-1].title())


def _docs_snippet(payload: dict[str, Any]) -> str:
    body = payload.get("body") if isinstance(payload.get("body"), dict) else {}
    content = body.get("content") if isinstance(body.get("content"), list) else []
    text_chunks: list[str] = []
    for section in content:
        if not isinstance(section, dict):
            continue
        paragraph = section.get("paragraph") if isinstance(section.get("paragraph"), dict) else {}
        elements = paragraph.get("elements") if isinstance(paragraph.get("elements"), list) else []
        for element in elements:
            text_run = element.get("textRun") if isinstance(element, dict) and isinstance(element.get("textRun"), dict) else {}
            text = str(text_run.get("content") or "").strip()
            if text:
                text_chunks.append(text)
            if len(" ".join(text_chunks)) > 220:
                break
        if len(" ".join(text_chunks)) > 220:
            break
    snippet = " ".join(text_chunks).strip()
    return _clip_cell(snippet, 220)


def _gmail_headers(payload: dict[str, Any]) -> dict[str, str]:
    msg_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    headers = msg_payload.get("headers") if isinstance(msg_payload.get("headers"), list) else []
    parsed: dict[str, str] = {}
    for header in headers:
        if isinstance(header, dict):
            name = str(header.get("name") or "").lower()
            value = _clean_text(str(header.get("value") or ""))
            if name and value:
                parsed[name] = value
    return parsed


def _clean_text(value: str) -> str:
    """Remove control and formatting characters that can break terminal rendering."""
    if not value:
        return ""
    cleaned: list[str] = []
    for char in value:
        if char in "\n\r\t":
            cleaned.append(char)
            continue
        if unicodedata.category(char).startswith("C"):
            continue
        cleaned.append(char)
    text = "".join(cleaned)
    try:
        return text.encode("cp1252", errors="ignore").decode("cp1252", errors="ignore")
    except Exception:
        return text
