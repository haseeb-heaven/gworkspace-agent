"""Service and action catalog."""

from __future__ import annotations

from .models import ActionSpec, ParameterSpec, ServiceSpec


SERVICES: dict[str, ServiceSpec] = {
    "drive": ServiceSpec(
        key="drive",
        label="Google Drive",
        # Removed 'documents', 'doc', 'google documents', 'google docs' — those belong to docs service.
        aliases=("drive", "files", "google drive"),
        actions={
            "list_files": ActionSpec(
                key="list_files",
                label="List files",
                keywords=("list", "show", "view", "files", "documents", "search", "find"),
                parameters=(
                    ParameterSpec("page_size", "How many files should I show?", "10", required=False),
                    ParameterSpec("q", "Drive search query (e.g. name contains 'report')", "", required=False),
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
            "export_file": ActionSpec(
                key="export_file",
                label="Export file",
                keywords=("export", "download", "attach", "attachment", "pdf", "xlsx", "sheet", "doc"),
                parameters=(
                    ParameterSpec("file_id", "Enter the Google Drive file ID", "1AbCdEFg123"),
                    ParameterSpec("mime_type", "Target export MIME type", "application/pdf", required=False),
                ),
            ),
            "delete_file": ActionSpec(
                key="delete_file",
                label="Delete file",
                keywords=("delete", "remove", "trash"),
                parameters=(
                    ParameterSpec("file_id", "Enter the Google Drive file ID", "1AbCdEFg123"),
                ),
            ),
        },
    ),
    "sheets": ServiceSpec(
        key="sheets",
        label="Google Sheets",
        aliases=("sheets", "sheet", "spreadsheet", "excel"),
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
            "get_values": ActionSpec(
                key="get_values",
                label="Read spreadsheet values",
                keywords=("read", "fetch", "get", "search", "values", "data", "sheet"),
                parameters=(
                    ParameterSpec("spreadsheet_id", "Enter spreadsheet ID", "1AbCdEFg123"),
                    ParameterSpec("range", "Enter values range", "Sheet1!A1:Z500", required=False),
                ),
            ),
            "append_values": ActionSpec(
                key="append_values",
                label="Append rows",
                keywords=("append", "add", "save", "write", "insert", "rows"),
                parameters=(
                    ParameterSpec("spreadsheet_id", "Enter spreadsheet ID", "1AbCdEFg123"),
                    ParameterSpec("range", "Enter the target range", "Sheet1!A1", required=False),
                    ParameterSpec("values", "Enter rows to append", "value", required=False),
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
                keywords=("list", "show", "find", "search", "messages", "emails", "inbox"),
                parameters=(
                    ParameterSpec("max_results", "How many emails should I show?", "10", required=False),
                    ParameterSpec("q", "What Gmail search query should I use?", "ticket", required=False),
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
            "send_message": ActionSpec(
                key="send_message",
                label="Send email",
                keywords=("send", "compose", "mail", "email", "share"),
                parameters=(
                    ParameterSpec("to_email", "Recipient email address", "person@example.com"),
                    ParameterSpec("subject", "Email subject", "Requested data"),
                    ParameterSpec("body", "Email body", "Hello,\nPlease find the data below."),
                    ParameterSpec("attachments", "Optional local attachment paths", "scratch/exports/report.pdf", required=False),
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
    "docs": ServiceSpec(
        key="docs",
        label="Google Docs",
        # 'documents' and 'doc' moved here exclusively (removed from drive).
        aliases=("docs", "doc", "document", "documents", "google docs", "google documents"),
        actions={
            "create_document": ActionSpec(
                key="create_document",
                label="Create document",
                keywords=("create", "new", "write", "save", "document", "doc"),
                parameters=(
                    ParameterSpec("title", "What should the document title be?", "My Document"),
                    ParameterSpec("content", "Initial document content", "", required=False),
                ),
            ),
            "get_document": ActionSpec(
                key="get_document",
                label="Get document",
                keywords=("get", "open", "show", "read", "document", "doc"),
                parameters=(
                    ParameterSpec("document_id", "Enter the Google Docs document ID", "1AbCdEFg123"),
                ),
            ),
            "batch_update": ActionSpec(
                key="batch_update",
                label="Update document content",
                keywords=("update", "append", "write", "insert", "text", "content"),
                parameters=(
                    ParameterSpec("document_id", "Enter the Google Docs document ID", "1AbCdEFg123"),
                    ParameterSpec("text", "Text to append/insert", "Hello world"),
                ),
            ),
        },
    ),
    "slides": ServiceSpec(
        key="slides",
        label="Google Slides",
        aliases=("slides", "presentation", "presentations", "deck"),
        actions={
            "get_presentation": ActionSpec(
                key="get_presentation",
                label="Get presentation",
                keywords=("get", "open", "show", "read", "presentation", "slides", "deck"),
                parameters=(
                    ParameterSpec("presentation_id", "Enter the Google Slides presentation ID", "1AbCdEFg123"),
                ),
            ),
            "create_presentation": ActionSpec(
                key="create_presentation",
                label="Create presentation",
                keywords=("create", "new", "presentation", "slides", "deck"),
                parameters=(
                    ParameterSpec("title", "What should the presentation title be?", "Sales Deck"),
                ),
            ),
        },
    ),
    "contacts": ServiceSpec(
        key="contacts",
        label="Google Contacts",
        aliases=("contacts", "people", "profile", "profiles"),
        actions={
            "list_contacts": ActionSpec(
                key="list_contacts",
                label="List contacts",
                keywords=("list", "show", "find", "search", "contacts", "people"),
                parameters=(
                    ParameterSpec("page_size", "How many contacts should I show?", "10", required=False),
                ),
            ),
        },
    ),
    "chat": ServiceSpec(
        key="chat",
        label="Google Chat",
        aliases=("chat", "spaces", "messages"),
        actions={
            "list_spaces": ActionSpec(
                key="list_spaces",
                label="List spaces",
                keywords=("list", "show", "find", "spaces", "rooms", "chat"),
                parameters=(
                    ParameterSpec("page_size", "How many spaces should I show?", "10", required=False),
                ),
            ),
            "send_message": ActionSpec(
                key="send_message",
                label="Send message",
                keywords=("send", "message", "post", "chat"),
                parameters=(
                    ParameterSpec("space", "Space name (e.g. spaces/AAAA1234)", "spaces/AAAA1234"),
                    ParameterSpec("text", "Message text", "Hello team!"),
                ),
            ),
            "list_messages": ActionSpec(
                key="list_messages",
                label="List messages",
                keywords=("list", "show", "messages", "chat", "history"),
                parameters=(
                    ParameterSpec("space", "Space name (e.g. spaces/AAAA1234)", "spaces/AAAA1234"),
                    ParameterSpec("page_size", "How many messages should I show?", "10", required=False),
                ),
            ),
        },
    ),
    "meet": ServiceSpec(
        key="meet",
        label="Google Meet",
        aliases=("meet", "meeting", "conference", "video"),
        actions={
            "list_conferences": ActionSpec(
                key="list_conferences",
                label="List conferences",
                keywords=("list", "show", "find", "conferences", "meetings", "video"),
                parameters=(
                    ParameterSpec("space", "Space name (e.g. spaces/AAAA1234)", "spaces/AAAA1234", required=False),
                ),
            ),
            "get_conference": ActionSpec(
                key="get_conference",
                label="Get conference",
                keywords=("get", "show", "details", "conference", "meeting", "video"),
                parameters=(
                    ParameterSpec("name", "Conference name", "spaces/AAAA1234"),
                ),
            ),
            "create_meeting": ActionSpec(
                key="create_meeting",
                label="Create meeting",
                keywords=("create", "new", "start", "meeting", "meet", "video"),
                parameters=(),
            ),
        },
    ),
    "search": ServiceSpec(
        key="search",
        label="Web Search",
        aliases=("search", "web", "google", "find"),
        actions={
            "web_search": ActionSpec(
                key="web_search",
                label="Search the web",
                keywords=("search", "find", "lookup", "info", "information", "web"),
                parameters=(
                    ParameterSpec("query", "What would you like to search for?", "Top Agentic AI frameworks"),
                ),
            ),
        },
    ),
    "admin": ServiceSpec(
        key="admin",
        label="Google Admin SDK",
        aliases=("admin", "directory", "users", "sdk"),
        actions={
            "log_activity": ActionSpec(
                key="log_activity",
                label="Log activity",
                keywords=("log", "audit", "track", "metadata", "store"),
                parameters=(
                    ParameterSpec("data", "Metadata or activity to log", "User performed X"),
                ),
            ),
        },
    ),
    "forms": ServiceSpec(
        key="forms",
        label="Google Forms",
        aliases=("forms", "form", "survey", "sync"),
        actions={
            "sync_data": ActionSpec(
                key="sync_data",
                label="Sync data to form",
                keywords=("sync", "save", "connect", "form"),
                parameters=(
                    ParameterSpec("form_id", "Google Form ID", "1AbCdEFg123", required=False),
                    ParameterSpec("data", "Data to sync", "Result of tasks"),
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
