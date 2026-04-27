from typing import Any

from gws_assistant.output_formatter import _format_drive_files


def summarize(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Takes raw drive.list_files JSON output and returns a dictionary containing
    count, formatted table, and 2D summary array.
    """
    f_obj = payload.get("files")
    files = f_obj if isinstance(f_obj, list) else []

    count = len(files)
    table = _format_drive_files(payload)
    summary_rows = [[f.get("name", ""), f.get("mimeType", ""), f.get("webViewLink", "")] for f in files]

    return {
        "count": count,
        "table": table,
        "summary_rows": summary_rows,
    }
