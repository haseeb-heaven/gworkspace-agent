"""Service and action catalog."""

from __future__ import annotations

from .models import ActionSpec, ParameterSpec, ServiceSpec


SERVICES: dict[str, ServiceSpec] = {
    "drive": ServiceSpec(
        key="drive",
        label="Google Drive",
        aliases=("drive", "documents", "files"),
        actions={
            "list_files": ActionSpec(
                key="list_files",
                label="List files",
                keywords=("list", "show", "view", "files", "documents"),
                parameters=(
                    ParameterSpec("page_size", "How many files should I show?", "10", required=False),
                ),
            ),
            "create_folder": ActionSpec(
                key="create_folder",
                label="Create folder",
                keywords=("create", "folder", "new"),
                parameters=(
                    ParameterSpec("folder_name", "What should the folder name be?", "My Folder"),
                ),
            ),
            "get_file": ActionSpec(
                key="get_file",
                label="Get file details",
                keywords=("get", "details", "file", "open"),
                parameters=(
                    ParameterSpec("file_id", "Enter the Google Drive file ID", "1AbCdEFg123"),
                ),
            ),
            "delete_file": ActionSpec(
                key="delete_file",
                label="Delete file",
                keywords=("delete", "remove", "trash"),
                parameters=(
                    ParameterSpec("file_id", "Enter the file ID to delete", "1AbCdEFg123"),
                ),
            ),
        },
    ),
    "sheets": ServiceSpec(
        key="sheets",
        label="Google Sheets",
        aliases=("sheets", "spreadsheet", "excel"),
        actions={
            "create_spreadsheet": ActionSpec(
                key="create_spreadsheet",
                label="Create spreadsheet",
                keywords=("create", "new", "sheet", "spreadsheet"),
                parameters=(
                    ParameterSpec("title", "What should the spreadsheet title be?", "Quarterly Budget"),
                ),
            ),
            "get_spreadsheet": ActionSpec(
                key="get_spreadsheet",
                label="Get spreadsheet details",
                keywords=("get", "open", "show", "spreadsheet", "sheet"),
                parameters=(
                    ParameterSpec("spreadsheet_id", "Enter spreadsheet ID", "1AbCdEFg123"),
                ),
            ),
        },
    ),
    "gmail": ServiceSpec(
        key="gmail",
        label="Gmail",
        aliases=("gmail", "mail", "email", "inbox"),
        actions={
            "list_messages": ActionSpec(
                key="list_messages",
                label="List messages",
                keywords=("list", "show", "messages", "emails", "inbox"),
                parameters=(
                    ParameterSpec("max_results", "How many emails should I show?", "10", required=False),
                ),
            ),
            "get_message": ActionSpec(
                key="get_message",
                label="Get message details",
                keywords=("get", "open", "message", "email"),
                parameters=(
                    ParameterSpec("message_id", "Enter message ID", "18c5a4fbe123"),
                ),
            ),
        },
    ),
    "calendar": ServiceSpec(
        key="calendar",
        label="Google Calendar",
        aliases=("calendar", "events", "meeting"),
        actions={
            "list_events": ActionSpec(
                key="list_events",
                label="List events",
                keywords=("list", "show", "events", "meetings"),
                parameters=(
                    ParameterSpec("calendar_id", "Which calendar ID should I use?", "primary", required=False),
                ),
            ),
            "create_event": ActionSpec(
                key="create_event",
                label="Create event",
                keywords=("create", "event", "schedule", "meeting"),
                parameters=(
                    ParameterSpec("summary", "Event summary", "Weekly Sync"),
                    ParameterSpec("start_date", "Start date (YYYY-MM-DD)", "2026-04-15"),
                ),
            ),
        },
    ),
}


def supported_services() -> list[str]:
    return sorted(SERVICES.keys())


def normalize_service(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip().lower()
    if candidate in SERVICES:
        return candidate
    for service, spec in SERVICES.items():
        if candidate in spec.aliases:
            return service
    return None

