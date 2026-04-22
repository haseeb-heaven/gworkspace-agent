from typing import Any, Dict
from gws_assistant.output_formatter import _format_drive_files

def summarize(payload: dict[str, Any]) -> dict[str, Any]:
    files = payload.get("files", [])
    if not isinstance(files, list):
        files = []

    count = len(files)
    table = _format_drive_files(payload)

    summary_rows = []
    for f in files:
        if isinstance(f, dict):
            summary_rows.append([
                f.get("name", ""),
                f.get("mimeType", ""),
                f.get("webViewLink", "")
            ])

    return {
        "count": count,
        "table": table,
        "summary_rows": summary_rows,
    }
