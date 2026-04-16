"""Service and action catalog."""

from __future__ import annotations

from .models import ActionSpec, ParameterSpec, ServiceSpec

SERVICES: dict[str, ServiceSpec] = {
    "drive": ServiceSpec(
        key="drive",
        label="Google Drive",
        aliases=("drive", "files", "google drive"),
        description="Manage files and folders in Google Drive. Returns file metadata including id, name, mimeType, webViewLink.",
        actions={
            "list_files": ActionSpec(
                key="list_files",
                label="List files",
                description="List or search files in Drive. Returns: [{id, name, mimeType, modifiedTime, webViewLink}]. Use id for subsequent get_file or export_file calls.",
                keywords=("list", "show", "view", "files", "documents", "search", "find"),
                parameters=(
                    ParameterSpec("page_size", "How many files should I show?", "10", required=False),
                    ParameterSpec("q", "Drive search query (e.g. name contains 'report')", "", required=False),
                ),
            ),
            "create_folder": ActionSpec(
                key="create_folder",
                label="Create folder",
                description="Create a new folder in Google Drive. Returns: {id, name}.",
                keywords=("create", "new", "folder", "drive"),
                parameters=(
                    ParameterSpec("folder_name", "What should the folder be named?", "My Folder"),
                ),
            ),
            "upload_file": ActionSpec(
                key="upload_file",
                label="Upload file",
                description="Upload a local file to Google Drive. Returns: {id, name, mimeType}.",
                keywords=("upload", "add", "put", "drive"),
                parameters=(
                    ParameterSpec("file_path", "Local path to the file to upload", "README.md"),
                    ParameterSpec("name", "Optional: name for the file on Drive", "Uploaded File", required=False),
                ),
            ),
            "get_file": ActionSpec(
                key="get_file",
                label="Get file details",
                description="Get metadata for a specific Drive file by id. Returns: {id, name, mimeType, size, webViewLink}.",
                keywords=("get", "details", "file", "open"),
                parameters=(
                    ParameterSpec("file_id", "Enter the Google Drive file ID", "1AbCdEFg123"),
                ),
            ),
            "export_file": ActionSpec(
                key="export_file",
                label="Export file",
                description="Export a Google Workspace document (Doc/Sheet) to a given MIME type (e.g. text/plain, application/pdf). Use this — not Docs/Sheets APIs — for reading file content.",
                keywords=("export", "download", "attach", "attachment", "pdf", "xlsx", "sheet", "doc"),
                parameters=(
                    ParameterSpec("file_id", "Enter the Google Drive file ID", "1AbCdEFg123"),
                    ParameterSpec("mime_type", "Target export MIME type", "application/pdf", required=False),
                ),
            ),
            "delete_file": ActionSpec(
                key="delete_file",
                label="Delete file",
                description="Permanently delete a Drive file by id. Irreversible — use with caution.",
                keywords=("delete", "remove", "trash"),
                parameters=(
                    ParameterSpec("file_id", "Enter the Google Drive file ID", "1AbCdEFg123"),
                ),
            ),
            "move_file": ActionSpec(
                key="move_file",
                label="Move file",
                description="Move a Drive file to a new folder. Requires file_id and folder_id.",
                keywords=("move", "relocate", "transfer", "organize"),
                parameters=(
                    ParameterSpec("file_id", "Enter the Google Drive file ID", "1AbCdEFg123"),
                    ParameterSpec("folder_id", "Enter the destination folder ID", "1XyZ..."),
                ),
            ),
        },
    ),
    "sheets": ServiceSpec(
        key="sheets",
        label="Google Sheets",
        aliases=("sheets", "sheet", "spreadsheet", "excel"),
        description="Create and manipulate Google Sheets spreadsheets. Always create the spreadsheet before appending values.",
        actions={
            "create_spreadsheet": ActionSpec(
                key="create_spreadsheet",
                label="Create spreadsheet",
                description="Create a new Google Sheets spreadsheet. Returns: {spreadsheetId, spreadsheetUrl, title}. Use spreadsheetId in subsequent append_values or get_values calls.",
                keywords=("create", "new", "sheet", "spreadsheet"),
                parameters=(
                    ParameterSpec("title", "What should the spreadsheet title be?", "Quarterly Budget"),
                ),
            ),
            "get_spreadsheet": ActionSpec(
                key="get_spreadsheet",
                label="Get spreadsheet details",
                description="Get metadata and sheet names for a spreadsheet by spreadsheetId. Returns: {spreadsheetId, title, sheets[]}.",
                keywords=("get", "open", "show", "spreadsheet", "sheet"),
                parameters=(
                    ParameterSpec("spreadsheet_id", "Enter spreadsheet ID", "1AbCdEFg123"),
                ),
            ),
            "get_values": ActionSpec(
                key="get_values",
                label="Read spreadsheet values",
                description="Read cell values from a spreadsheet range. Returns: {values: [[row1col1, ...], ...]}. Use range format 'Sheet1!A1:Z500'.",
                keywords=("read", "fetch", "get", "search", "values", "data", "sheet"),
                parameters=(
                    ParameterSpec("spreadsheet_id", "Enter spreadsheet ID", "1AbCdEFg123"),
                    ParameterSpec("range", "Enter values range", "Sheet1!A1:Z500", required=False),
                ),
            ),
            "append_values": ActionSpec(
                key="append_values",
                label="Append rows",
                description="Append rows to a spreadsheet. 'values' must be a 2D array [[col1, col2], ...] or a $placeholder resolved at runtime. Requires spreadsheet_id from a preceding create_spreadsheet.",
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
        description="Read and send Gmail messages. Always call list_messages first to get message IDs, then get_message for full content.",
        actions={
            "list_messages": ActionSpec(
                key="list_messages",
                label="List messages",
                description="Search the Gmail inbox and return a list of message stubs. Returns: [{id, threadId}]. Pass 'q' using Gmail search syntax (e.g. 'is:unread', 'subject:\"receipt\"', 'from:stripe.com'). Must call get_message next to read content.",
                keywords=("list", "show", "find", "search", "messages", "emails", "inbox"),
                parameters=(
                    ParameterSpec("max_results", "How many emails should I show?", "10", required=False),
                    ParameterSpec("q", "What Gmail search query should I use?", "ticket", required=False),
                ),
            ),
            "get_message": ActionSpec(
                key="get_message",
                label="Get message details",
                description="Fetch the full content of a Gmail message by id. Returns: {id, subject, from, to, date, snippet, body}. The executor auto-resolves message_id from the preceding list_messages result — you may omit it.",
                keywords=("get", "open", "message", "email"),
                parameters=(
                    ParameterSpec("message_id", "Enter message ID (or omit — auto-resolved from list_messages)", "18c5a4fbe123", required=False),
                ),
            ),
            "send_message": ActionSpec(
                key="send_message",
                label="Send email",
                description="Send an email from the authenticated account. 'body' can be a $placeholder (e.g. $sheet_email_body, $last_code_stdout, $web_search_markdown) resolved at runtime.",
                keywords=("send", "compose", "mail", "email", "share"),
                parameters=(
                    ParameterSpec("to_email", "Recipient email address", "person@example.com"),
                    ParameterSpec("subject", "Email subject", "Requested data"),
                    ParameterSpec("body", "Email body or $placeholder", "$sheet_email_body"),
                    ParameterSpec("attachments", "Optional local attachment paths", "scratch/exports/report.pdf", required=False),
                ),
            ),
        },
    ),
    "calendar": ServiceSpec(
        key="calendar",
        label="Google Calendar",
        aliases=("calendar", "events", "meeting"),
        description="List and create Google Calendar events.",
        actions={
            "list_events": ActionSpec(
                key="list_events",
                label="List events",
                description="List upcoming calendar events ordered by start time. Returns: [{id, summary, start, end, location}].",
                keywords=("list", "show", "events", "meetings"),
                parameters=(
                    ParameterSpec("calendar_id", "Which calendar ID should I use?", "primary", required=False),
                ),
            ),
            "create_event": ActionSpec(
                key="create_event",
                label="Create event",
                description="Create an all-day or timed event on the primary calendar. Returns: {id, summary, htmlLink}.",
                keywords=("create", "event", "schedule", "meeting"),
                parameters=(
                    ParameterSpec("summary", "Event summary", "Weekly Sync"),
                    ParameterSpec("start_date", "Start date (YYYY-MM-DD)", "2026-04-15"),
                ),
            ),
            "delete_event": ActionSpec(
                key="delete_event",
                label="Delete event",
                description="Delete an event from a calendar by ID.",
                keywords=("delete", "remove", "cancel", "trash"),
                parameters=(
                    ParameterSpec("event_id", "Enter the Calendar event ID", "icfdpe6lrg7jvtinujvd5h6qa4"),
                    ParameterSpec("calendar_id", "Which calendar ID? (default: primary)", "primary", required=False),
                ),
            ),
            "update_event": ActionSpec(
                key="update_event",
                label="Update event",
                description="Update an existing calendar event. Only provided fields are changed.",
                keywords=("update", "edit", "modify", "patch"),
                parameters=(
                    ParameterSpec("event_id", "Enter the Calendar event ID", "icfdpe6lrg7jvtinujvd5h6qa4"),
                    ParameterSpec("summary", "New summary", "Updated Title", required=False),
                    ParameterSpec("description", "New description", "Updated notes", required=False),
                    ParameterSpec("calendar_id", "Which calendar ID? (default: primary)", "primary", required=False),
                ),
            ),
        },
    ),
    "docs": ServiceSpec(
        key="docs",
        label="Google Docs",
        aliases=("docs", "doc", "document", "documents", "google docs", "google documents"),
        description="Create and edit Google Docs documents.",
        actions={
            "create_document": ActionSpec(
                key="create_document",
                label="Create document",
                description="Create a new Google Doc with an optional initial body. 'content' can be a $placeholder (e.g. $web_search_summary). Returns: {documentId, title, documentUrl}.",
                keywords=("create", "new", "write", "save", "document", "doc"),
                parameters=(
                    ParameterSpec("title", "What should the document title be?", "My Document"),
                    ParameterSpec("content", "Initial document content or $placeholder", "$web_search_summary", required=False),
                ),
            ),
            "get_document": ActionSpec(
                key="get_document",
                label="Get document",
                description="Fetch the content and metadata of a Google Doc by documentId. Returns: {documentId, title, body}.",
                keywords=("get", "open", "show", "read", "document", "doc"),
                parameters=(
                    ParameterSpec("document_id", "Enter the Google Docs document ID", "1AbCdEFg123"),
                ),
            ),
            "batch_update": ActionSpec(
                key="batch_update",
                label="Update document content",
                description="Insert or append text into an existing Google Doc at index 1. Use documentId from a preceding create_document.",
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
        description="Read and create Google Slides presentations.",
        actions={
            "get_presentation": ActionSpec(
                key="get_presentation",
                label="Get presentation",
                description="Get slides content and metadata for a presentation by presentationId. Returns: {presentationId, title, slides[]}.",
                keywords=("get", "open", "show", "read", "presentation", "slides", "deck"),
                parameters=(
                    ParameterSpec("presentation_id", "Enter the Google Slides presentation ID", "1AbCdEFg123"),
                ),
            ),
            "create_presentation": ActionSpec(
                key="create_presentation",
                label="Create presentation",
                description="Create a new blank Google Slides presentation. Returns: {presentationId, title}.",
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
        description="List contacts from the authenticated Google account.",
        actions={
            "list_contacts": ActionSpec(
                key="list_contacts",
                label="List contacts",
                description="List contacts with names, emails, and phone numbers. Returns: [{name, emailAddresses[], phoneNumbers[]}].",
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
        description="Send and read messages in Google Chat spaces.",
        actions={
            "list_spaces": ActionSpec(
                key="list_spaces",
                label="List spaces",
                description="List Google Chat spaces the user belongs to. Returns: [{name, displayName, type}]. Use 'name' (e.g. spaces/AAAA1234) for send_message or list_messages.",
                keywords=("list", "show", "find", "spaces", "rooms", "chat"),
                parameters=(
                    ParameterSpec("page_size", "How many spaces should I show?", "10", required=False),
                ),
            ),
            "send_message": ActionSpec(
                key="send_message",
                label="Send message",
                description="Post a text message to a Chat space. Requires 'space' (e.g. spaces/AAAA1234) from list_spaces.",
                keywords=("send", "message", "post", "chat"),
                parameters=(
                    ParameterSpec("space", "Space name (e.g. spaces/AAAA1234)", "spaces/AAAA1234"),
                    ParameterSpec("text", "Message text", "Hello team!"),
                ),
            ),
            "list_messages": ActionSpec(
                key="list_messages",
                label="List messages",
                description="List recent messages in a Chat space. Returns: [{name, text, sender, createTime}].",
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
        description="Create and look up Google Meet video conference spaces.",
        actions={
            "list_conferences": ActionSpec(
                key="list_conferences",
                label="List conferences",
                description="List existing Meet spaces. Returns: [{name, meetingUri, activeConference}].",
                keywords=("list", "show", "find", "conferences", "meetings", "video"),
                parameters=(
                    ParameterSpec("space", "Space name (e.g. spaces/AAAA1234)", "spaces/AAAA1234", required=False),
                ),
            ),
            "get_conference": ActionSpec(
                key="get_conference",
                label="Get conference",
                description="Get details for a specific Meet space by name. Returns: {name, meetingUri, activeConference}.",
                keywords=("get", "show", "details", "conference", "meeting", "video"),
                parameters=(
                    ParameterSpec("name", "Conference name", "spaces/AAAA1234"),
                ),
            ),
            "create_meeting": ActionSpec(
                key="create_meeting",
                label="Create meeting",
                description="Create a new Meet space. Returns: {name, meetingUri}. No parameters required.",
                keywords=("create", "new", "start", "meeting", "meet", "video"),
                parameters=(),
            ),
        },
    ),
    "keep": ServiceSpec(
        key="keep",
        label="Google Keep",
        aliases=("keep", "notes", "keep notes"),
        description="Manage Google Keep notes. Note: The API may have limited access in personal accounts; enterprise accounts are preferred.",
        actions={
            "list_notes": ActionSpec(
                key="list_notes",
                label="List notes",
                description="List Google Keep notes. Returns: {notes: [{name, title, body}]}.",
                keywords=("list", "show", "find", "notes", "keep"),
                parameters=(
                    ParameterSpec("page_size", "How many notes should I show?", "10", required=False),
                ),
            ),
            "create_note": ActionSpec(
                key="create_note",
                label="Create note",
                description="Create a new Google Keep note. Returns: {name, title, body}.",
                keywords=("create", "new", "note", "keep"),
                parameters=(
                    ParameterSpec("title", "What should the note title be?", "My Note"),
                    ParameterSpec("body", "Initial note content", "Hello world", required=False),
                ),
            ),
        },
    ),
    "search": ServiceSpec(
        key="search",
        label="Web Search",
        aliases=("search", "web", "google", "find"),
        description="Search the web for external information not available in the user's Workspace. Use for 'top X', 'best Y', 'latest Z' queries.",
        actions={
            "web_search": ActionSpec(
                key="web_search",
                label="Search the web",
                description="Run a web search query and return structured results. Returns: {summary, rows: [[col1, col2], ...]}. Use $web_search_summary for doc content, $web_search_rows or $web_search_table_values for sheet cell values.",
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
        aliases=("admin", "directory", "users", "sdk", "reports", "admin-reports"),
        description="Audit logs and activity reports via the Google Admin SDK (Reports API). Use for tracking user logins, drive events, or admin changes.",
        actions={
            "log_activity": ActionSpec(
                key="log_activity",
                label="Log activity",
                description="Synthetic internal tool to record an audit log entry for the agent's actions. Returns: {success, logged_at}.",
                keywords=("log", "audit", "track", "metadata", "store"),
                parameters=(
                    ParameterSpec("data", "Metadata or activity to log", "User performed X"),
                ),
            ),
            "list_activities": ActionSpec(
                key="list_activities",
                label="List activities",
                description="Retrieve audit logs for a specific application (e.g. 'drive', 'admin'). Returns: {items: [...]}.",
                keywords=("list", "find", "search", "logs", "audit", "events"),
                parameters=(
                    ParameterSpec("application_name", "Application to audit (admin, drive, etc.)", "drive"),
                    ParameterSpec("max_results", "How many logs to show?", "10", required=False),
                ),
            ),
        },
    ),
    "forms": ServiceSpec(
        key="forms",
        label="Google Forms",
        aliases=("forms", "form", "survey"),
        description="Create and manage Google Forms.",
        actions={
            "create_form": ActionSpec(
                key="create_form",
                label="Create form",
                description="Create a new Google Form. Returns: {formId, info: {title}}.",
                keywords=("create", "new", "form", "survey"),
                parameters=(
                    ParameterSpec("title", "What should the form title be?", "Untitled Form"),
                ),
            ),
            "get_form": ActionSpec(
                key="get_form",
                label="Get form",
                description="Fetch metadata for a Google Form by ID. Returns: {formId, info, items}.",
                keywords=("get", "open", "read", "form"),
                parameters=(
                    ParameterSpec("form_id", "Enter the Google Form ID", "1AbCdEFg123"),
                ),
            ),
        },
    ),
    "code": ServiceSpec(
        key="code",
        label="Code Execution",
        aliases=("code", "python", "computation", "compute", "script"),
        description="Execute Python code in a restricted sandbox for logic, math, data processing, and sorting. Output is captured as stdout and return values.",
        actions={
            "execute": ActionSpec(
                key="execute",
                label="Execute Python code",
                description="Run a block of Python code. Captured results are available as $last_code_stdout and $last_code_result.",
                keywords=("run", "execute", "python", "code", "sort", "calculate", "math", "compute"),
                parameters=(
                    ParameterSpec("code", "Python code to execute", "sorted([3, 1, 2])"),
                ),
            ),
        },
    ),
    "computation": ServiceSpec(
        key="computation",
        label="Computation Engine",
        aliases=("computation", "math", "calc"),
        description="Alias for code execution service, specifically for mathematical and logical processing.",
        actions={
            "execute": ActionSpec(
                key="execute",
                label="Run calculation",
                description="Run Python-based logic or calculation. Results are stored in context.",
                keywords=("run", "execute", "calculate", "math", "compute"),
                parameters=(
                    ParameterSpec("code", "Python code to execute", "x = 10 + 5; print(x)"),
                ),
            ),
        },
    ),
    "telegram": ServiceSpec(
        key="telegram",
        label="Telegram Updates",
        aliases=("telegram", "tg", "notify"),
        description="Send progress updates to the user via Telegram.",
        actions={
            "send_message": ActionSpec(
                key="send_message",
                label="Send Telegram Message",
                description="Send a text message to the user's Telegram chat.",
                keywords=("send", "update", "notify", "telegram", "message"),
                parameters=(
                    ParameterSpec("message", "The update message to send", "Completed task X"),
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
