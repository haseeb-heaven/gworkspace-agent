"""File type and MIME type helpers for Google Workspace operations.

Maps common extensions to MIME types and provides utilities for
upload/download/export format negotiation across Drive, Docs,
Sheets, Slides, Gmail, and other GWS services.
"""

from __future__ import annotations

import mimetypes
import re
from pathlib import Path

# Matches file paths after upload/add/put keywords, or bare absolute/relative paths.
RE_FILE_PATH = re.compile(
    r"(?:upload|add|put)\s+(?:file\s+)?['\"]?([A-Za-z0-9_./\\~:-]+\.[A-Za-z0-9]{1,10})['\"]?|"
    r"\b([A-Z]:[A-Za-z0-9_./\\~-]+\.[A-Za-z0-9]{1,10})\b|"
    r"\b(/[A-Za-z0-9_./~-]+\.[A-Za-z0-9]{1,10})\b|"
    r"\b(./[A-Za-z0-9_./~-]+\.[A-Za-z0-9]{1,10})\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Common file extension -> MIME type mappings
# ---------------------------------------------------------------------------

_EXTENSION_TO_MIME: dict[str, str] = {
    # Google Workspace native types
    "gdoc": "application/vnd.google-apps.document",
    "gsheet": "application/vnd.google-apps.spreadsheet",
    "gslides": "application/vnd.google-apps.presentation",
    "gdraw": "application/vnd.google-apps.drawing",
    "gform": "application/vnd.google-apps.form",
    "gmap": "application/vnd.google-apps.map",
    "gsite": "application/vnd.google-apps.site",
    # Microsoft Office
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    # OpenDocument
    "odt": "application/vnd.oasis.opendocument.text",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "odp": "application/vnd.oasis.opendocument.presentation",
    # PDF
    "pdf": "application/pdf",
    # Plain text / markup
    "txt": "text/plain",
    "csv": "text/csv",
    "tsv": "text/tab-separated-values",
    "json": "application/json",
    "xml": "application/xml",
    "html": "text/html",
    "htm": "text/html",
    "md": "text/markdown",
    "rtf": "application/rtf",
    # Images
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "svg": "image/svg+xml",
    "tiff": "image/tiff",
    "tif": "image/tiff",
    "webp": "image/webp",
    "ico": "image/vnd.microsoft.icon",
    # Audio
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
    "oga": "audio/ogg",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "m4a": "audio/mp4",
    "wma": "audio/x-ms-wma",
    # Video
    "mp4": "video/mp4",
    "mkv": "video/x-matroska",
    "avi": "video/x-msvideo",
    "mov": "video/quicktime",
    "wmv": "video/x-ms-wmv",
    "flv": "video/x-flv",
    "webm": "video/webm",
    "mpeg": "video/mpeg",
    "mpg": "video/mpeg",
    "m4v": "video/x-m4v",
    "3gp": "video/3gpp",
    # Archives
    "zip": "application/zip",
    "rar": "application/vnd.rar",
    "tar": "application/x-tar",
    "gz": "application/gzip",
    "bz2": "application/x-bzip2",
    "7z": "application/x-7z-compressed",
    # Code / data
    "py": "text/x-python",
    "js": "text/javascript",
    "ts": "application/typescript",
    "java": "text/x-java-source",
    "c": "text/x-c",
    "cpp": "text/x-c++",
    "h": "text/x-c",
    "go": "text/x-go",
    "rs": "text/x-rust",
    "rb": "text/x-ruby",
    "php": "application/x-php",
    "sh": "application/x-sh",
    "sql": "application/sql",
    "yaml": "application/x-yaml",
    "yml": "application/x-yaml",
}

# ---------------------------------------------------------------------------
# Google Workspace export targets for native file types
# ---------------------------------------------------------------------------

_GOOGLE_DOC_EXPORT_TARGETS: dict[str, dict[str, str]] = {
    "application/vnd.google-apps.document": {
        "text/plain": ".txt",
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.oasis.opendocument.text": ".odt",
        "application/rtf": ".rtf",
        "text/html": ".html",
        "application/epub+zip": ".epub",
    },
    "application/vnd.google-apps.spreadsheet": {
        "text/csv": ".csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "application/vnd.oasis.opendocument.spreadsheet": ".ods",
        "application/pdf": ".pdf",
        "text/tab-separated-values": ".tsv",
        "application/vnd.ms-excel.sheet.macroenabled.12": ".xlsm",
    },
    "application/vnd.google-apps.presentation": {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
        "application/vnd.oasis.opendocument.presentation": ".odp",
        "text/plain": ".txt",
    },
    "application/vnd.google-apps.drawing": {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/svg+xml": ".svg",
        "application/pdf": ".pdf",
    },
}

# MIME types that are *not* Google Workspace native and should use alt=media download
_NON_WORKSPACE_DOWNLOAD_MIMES: frozenset[str] = frozenset(
    {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/bmp",
        "image/svg+xml",
        "image/webp",
        "audio/mpeg",
        "audio/wav",
        "audio/ogg",
        "audio/aac",
        "audio/flac",
        "audio/mp4",
        "video/mp4",
        "video/x-matroska",
        "video/x-msvideo",
        "video/quicktime",
        "video/webm",
        "text/plain",
        "text/csv",
        "text/html",
        "text/markdown",
        "application/json",
        "application/zip",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
)

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def guess_mime_type(file_path: str | Path) -> str | None:
    """Return MIME type for *file_path*, checking our override map first."""
    path = Path(file_path)
    ext = path.suffix.lstrip(".").lower()
    if ext in _EXTENSION_TO_MIME:
        return _EXTENSION_TO_MIME[ext]
    # Fall back to stdlib mimetypes
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed


def is_workspace_native(mime_type: str | None) -> bool:
    """Return True if *mime_type* is a Google Workspace native type."""
    if not mime_type:
        return False
    return mime_type.startswith("application/vnd.google-apps.")


def is_binary_media(mime_type: str | None) -> bool:
    """Return True for image, audio, video, archive, or PDF types."""
    if not mime_type:
        return False
    return mime_type.startswith(("image/", "audio/", "video/", "application/zip")) or mime_type == "application/pdf"


def supported_export_formats(source_mime: str | None) -> list[str] | None:
    """Return supported export MIME types for a Google Workspace native file."""
    if not source_mime:
        return None
    targets = _GOOGLE_DOC_EXPORT_TARGETS.get(source_mime)
    if targets is None:
        return None
    return list(targets.keys())


def default_export_mime(source_mime: str | None, requested_mime: str | None = None) -> str:
    """Pick a sensible export MIME type for a Google Workspace native file.

    If *requested_mime* is provided and supported, it is returned.
    Otherwise a safe default is chosen.
    """
    if not source_mime:
        return requested_mime or "application/pdf"

    targets = _GOOGLE_DOC_EXPORT_TARGETS.get(source_mime)
    if targets is None:
        return requested_mime or "application/pdf"

    if requested_mime and requested_mime in targets:
        return requested_mime

    # Safe defaults per type
    defaults = {
        "application/vnd.google-apps.document": "text/plain",
        "application/vnd.google-apps.spreadsheet": "text/csv",
        "application/vnd.google-apps.presentation": "application/pdf",
        "application/vnd.google-apps.drawing": "image/png",
    }
    return defaults.get(source_mime, "application/pdf")


def export_extension_for_mime(mime_type: str) -> str:
    """Return a sensible file extension for a MIME type."""
    ext = mimetypes.guess_extension(mime_type)
    if ext:
        return ext

    # Override map reverse lookup (first match)
    for e, m in _EXTENSION_TO_MIME.items():
        if m == mime_type:
            return "." + e

    return ".bin"


def upload_command_flags(file_path: str | Path) -> dict[str, str]:
    """Return extra gws CLI flags for uploading a file with the correct content type.

    Returns a dict with keys such as ``upload_content_type`` that the planner
    can turn into ``--upload-content-type``.
    """
    mime = guess_mime_type(file_path)
    flags: dict[str, str] = {}
    if mime:
        flags["upload_content_type"] = mime
    return flags


def describe_supported_file_types() -> str:
    """Return a human-readable summary of supported file types."""
    categories = {
        "Google Workspace": [".gdoc", ".gsheet", ".gslides", ".gdraw", ".gform"],
        "Documents": [".doc", ".docx", ".odt", ".pdf", ".txt", ".rtf", ".html", ".md"],
        "Spreadsheets": [".xls", ".xlsx", ".ods", ".csv", ".tsv"],
        "Presentations": [".ppt", ".pptx", ".odp"],
        "Images": [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".tiff", ".webp"],
        "Audio": [".mp3", ".wav", ".ogg", ".aac", ".flac", ".m4a", ".wma"],
        "Video": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mpeg", ".m4v", ".3gp"],
        "Archives": [".zip", ".rar", ".tar", ".gz", ".bz2", ".7z"],
        "Code / Data": [".py", ".js", ".ts", ".json", ".xml", ".yaml", ".sql", ".java", ".go", ".rs"],
    }
    lines = ["Supported file types:"]
    for category, exts in categories.items():
        lines.append(f"  {category}: {', '.join(exts)}")
    return "\n".join(lines)


def all_supported_extensions() -> list[str]:
    """Return every extension known by the override map."""
    return [f".{ext}" for ext in _EXTENSION_TO_MIME.keys()]
