"""Service and action catalog."""

from __future__ import annotations

from .models import ActionSpec, ParameterSpec, ServiceSpec

SERVICES: dict[str, ServiceSpec] = {
    "drive": ServiceSpec(
        key="drive",
        label="Google Drive",
        aliases=("drive", "files", "google drive", "document", "documents", "file"),
        description="Manage files and folders in Google Drive. Returns file metadata including id, name, mimeType, webViewLink.",
        actions={
            "list_files": ActionSpec(
                key="list_files",
                label="List files",
                description="List or search files in Drive. Returns: [{id, name, mimeType, modifiedTime, webViewLink}]. Use id for subsequent get_file or export_file calls.",
                keywords=("list", "files", "show", "view", "search", "find"),
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
                parameters=(ParameterSpec("folder_name", "What should the folder be named?", "My Folder"),),
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
                parameters=(ParameterSpec("file_id", "Enter the Google Drive file ID", "1AbCdEFg123"),),
            ),
            "create_file": ActionSpec(
                key="create_file",
                label="Create file",
                description="Create a new file in Google Drive. Returns: {id, name, mimeType}.",
                keywords=("create", "new", "file"),
                parameters=(
                    ParameterSpec("name", "What should the file be named?", "New Document"),
                    ParameterSpec(
                        "mime_type",
                        "Optional: MIME type (e.g. application/vnd.google-apps.document)",
                        "application/vnd.google-apps.document",
                        required=False,
                    ),
                    ParameterSpec("folder_id", "Optional: Parent folder ID", "1AbCd...", required=False),
                ),
            ),
            "export_file": ActionSpec(
                key="export_file",
                label="Export file",
                description="Read or download the content of a file. Use this for both Google Workspace documents (Doc/Sheet/Slide) and regular files (txt, csv, pdf) to retrieve their text or binary content.",
                keywords=("export", "download", "read", "content", "text", "binary", "attachment"),
                parameters=(
                    ParameterSpec("file_id", "Enter the Google Drive file ID", "1AbCdEFg123"),
                    ParameterSpec(
                        "mime_type",
                        "Target export MIME type (optional for regular files)",
                        "text/plain",
                        required=False,
                    ),
                ),
            ),
            "delete_file": ActionSpec(
                key="delete_file",
                label="Delete file",
                description="Permanently delete a Drive file by id. Irreversible — use with caution.",
                keywords=("delete", "remove", "trash"),
                parameters=(ParameterSpec("file_id", "Enter the Google Drive file ID", "1AbCdEFg123"),),
            ),
            "update_file_metadata": ActionSpec(
                key="update_file_metadata",
                label="Update file metadata",
                description="Update an existing file's name or description.",
                keywords=("update", "rename", "edit", "metadata"),
                parameters=(
                    ParameterSpec("file_id", "Enter the Google Drive file ID", "1AbCdEFg123"),
                    ParameterSpec("name", "New name for the file", "Updated Name", required=False),
                    ParameterSpec("description", "New description for the file", "Updated Description", required=False),
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
            "copy_file": ActionSpec(
                key="copy_file",
                label="Copy file",
                description="Create a copy of a Drive file. Returns metadata for the new copy.",
                keywords=("copy", "duplicate", "backup", "clone"),
                parameters=(
                    ParameterSpec("file_id", "ID of the file to copy", "1AbCdEFg123"),
                    ParameterSpec("name", "New name for the copy", "Backup of File", required=False),
                    ParameterSpec("folder_id", "Optional: destination folder ID", "1XyZ...", required=False),
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
                negative_keywords=("read", "get", "search", "fetch", "find"),
                parameters=(ParameterSpec("title", "What should the spreadsheet title be?", "Quarterly Budget"),),
            ),
            "get_spreadsheet": ActionSpec(
                key="get_spreadsheet",
                label="Get spreadsheet details",
                description="Get metadata and sheet names for a spreadsheet by spreadsheetId. Returns: {spreadsheetId, title, sheets[]}.",
                keywords=("get", "open", "show", "spreadsheet", "sheet"),
                parameters=(ParameterSpec("spreadsheet_id", "Enter spreadsheet ID", "1AbCdEFg123"),),
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
            "delete_spreadsheet": ActionSpec(
                key="delete_spreadsheet",
                label="Delete spreadsheet",
                description="Delete a spreadsheet by ID. This actually deletes the file from Google Drive.",
                keywords=("delete", "remove", "trash", "spreadsheet"),
                parameters=(ParameterSpec("spreadsheet_id", "Enter spreadsheet ID", "1AbCdEFg123"),),
            ),
            "clear_values": ActionSpec(
                key="clear_values",
                label="Clear values",
                description="Clear all values from a spreadsheet range.",
                keywords=("clear", "empty", "delete values", "reset", "wipe"),
                parameters=(
                    ParameterSpec("spreadsheet_id", "Enter spreadsheet ID", "1AbCdEFg123"),
                    ParameterSpec("range", "Enter the range to clear", "Sheet1!A1:Z100"),
                ),
            ),
        },
    ),
    "gmail": ServiceSpec(
        key="gmail",
        label="Gmail",
        aliases=("gmail", "mail", "email", "emails", "message", "messages", "inbox"),
        description="Read and send Gmail messages. Always call list_messages first to get message IDs, then get_message for full content.",
        actions={
            "list_messages": ActionSpec(
                key="list_messages",
                label="List messages",
                description="Search the Gmail inbox and return a list of message stubs. Returns: [{id, threadId}]. Pass 'q' using Gmail search syntax (e.g. 'is:unread', 'subject:\"receipt\"', 'from:stripe.com'). Must call get_message next to read content.",
                keywords=("list", "show", "find", "search", "messages", "emails", "inbox"),
                negative_keywords=("send", "compose", "mail to", "write email", "email to"),
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
                negative_keywords=("send", "list", "search"),
                parameters=(
                    ParameterSpec(
                        "message_id",
                        "Enter message ID (or omit — auto-resolved from list_messages)",
                        "18c5a4fbe123",
                        required=False,
                    ),
                ),
            ),
            "trash_message": ActionSpec(
                key="trash_message",
                label="Trash message",
                description="Move a Gmail message to the trash by id.",
                keywords=("trash", "remove", "delete"),
                parameters=(ParameterSpec("message_id", "Enter message ID", "18c5a4fbe123"),),
            ),
            "delete_message": ActionSpec(
                key="delete_message",
                label="Delete message permanently",
                description="Permanently delete a Gmail message by id. Irreversible.",
                keywords=("delete", "permanently", "remove"),
                parameters=(ParameterSpec("message_id", "Enter message ID", "18c5a4fbe123"),),
            ),
            "send_message": ActionSpec(
                key="send_message",
                label="Send email",
                description="Send an email from the authenticated account. 'body' can be a $placeholder (e.g. $sheet_summary_table, $code_output, $search_summary_table) resolved at runtime.",
                keywords=("send", "compose", "mail", "email", "share"),
                negative_keywords=("list", "show", "find", "search", "messages", "emails", "inbox"),
                parameters=(
                    ParameterSpec("to_email", "Recipient email address", "person@example.com"),
                    ParameterSpec("subject", "Email subject", "Requested data"),
                    ParameterSpec("body", "Email body or $placeholder", "$sheet_summary_table"),
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
                description="List or search calendar events. Returns: [{id, summary, start, end, location}].",
                keywords=("list", "show", "events", "meetings", "search"),
                parameters=(
                    ParameterSpec("calendar_id", "Which calendar ID should I use?", "primary", required=False),
                    ParameterSpec("q", "Free-text search query (e.g. 'Sync')", "", required=False),
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
            "get_event": ActionSpec(
                key="get_event",
                label="Get event details",
                description="Fetch the details of a calendar event by ID. Returns: {id, summary, start, end, location}.",
                keywords=("get", "details", "event", "open"),
                parameters=(
                    ParameterSpec("event_id", "Enter the Calendar event ID", "icfdpe6lrg7jvtinujvd5h6qa4"),
                    ParameterSpec("calendar_id", "Which calendar ID? (default: primary)", "primary", required=False),
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
        aliases=("docs", "doc", "document", "documents", "google doc", "google docs", "google documents"),
        description="Create and edit Google Docs documents.",
        actions={
            "create_document": ActionSpec(
                key="create_document",
                label="Create document",
                description="Create a new Google Doc with an optional initial body. 'content' can be a $placeholder (e.g. $web_search_summary). Returns: {documentId, title, documentUrl}.",
                keywords=("create", "new", "write", "draft"),
                parameters=(
                    ParameterSpec("title", "What should the document title be?", "My Document"),
                    ParameterSpec(
                        "content", "Initial document content or $placeholder", "$web_search_summary", required=False
                    ),
                ),
            ),
            "get_document": ActionSpec(
                key="get_document",
                label="Get document",
                description="Fetch the content and metadata of a Google Doc by documentId. Returns: {documentId, title, body}.",
                keywords=("get", "open", "show", "read", "fetch"),
                parameters=(ParameterSpec("document_id", "Enter the Google Docs document ID", "1AbCdEFg123"),),
            ),
            "batch_update": ActionSpec(
                key="batch_update",
                label="Update document content",
                description="Insert or append text into an existing Google Doc at index 1. Use documentId from a preceding create_document.",
                keywords=(
                    "update document",
                    "append to document",
                    "write to document",
                    "insert into document",
                    "add text to document",
                ),
                negative_keywords=("read", "get", "show", "find", "search", "open"),
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
        aliases=("slides", "presentation", "presentations", "google slides"),
        description="Create and read Google Slides presentations.",
        actions={
            "create_presentation": ActionSpec(
                key="create_presentation",
                label="Create presentation",
                description="Create a new Google Slides presentation. Returns: {presentationId, title, presentationUrl}.",
                keywords=("create", "new", "write"),
                negative_keywords=("search", "find", "list", "show"),
                parameters=(ParameterSpec("title", "What should the presentation title be?", "My Presentation"),),
            ),
            "get_presentation": ActionSpec(
                key="get_presentation",
                label="Get presentation",
                description="Fetch the content and metadata of a Google Slides presentation. Returns: {presentationId, title, slides}.",
                keywords=("get", "open", "show", "read"),
                negative_keywords=("create", "new", "search"),
                parameters=(
                    ParameterSpec("presentation_id", "Enter the Google Slides presentation ID", "1AbCdEFg123"),
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
                parameters=(ParameterSpec("page_size", "How many contacts should I show?", "10", required=False),),
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
                parameters=(ParameterSpec("page_size", "How many spaces should I show?", "10", required=False),),
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
                parameters=(ParameterSpec("name", "Conference name", "spaces/AAAA1234"),),
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
                parameters=(ParameterSpec("page_size", "How many notes should I show?", "10", required=False),),
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
            "get_note": ActionSpec(
                key="get_note",
                label="Get note",
                description="Get a specific Google Keep note by name. Returns: {name, title, body}.",
                keywords=("get", "show", "read", "note", "keep"),
                parameters=(
                    ParameterSpec(
                        "name", "What is the note name (e.g. notes/...) to fetch?", "notes/123", required=True
                    ),
                ),
            ),
            "delete_note": ActionSpec(
                key="delete_note",
                label="Delete note",
                description="Delete a Google Keep note.",
                keywords=("delete", "remove", "note", "keep"),
                parameters=(
                    ParameterSpec(
                        "name", "What is the note name (e.g. notes/...) to delete?", "notes/123", required=True
                    ),
                ),
            ),
        },
    ),
    "search": ServiceSpec(
        key="search",
        label="Web Search",
        aliases=("search", "web", "find"),
        description="Search the web for external information not available in the user's Workspace. Use for 'top X', 'best Y', 'latest Z' queries.",
        actions={
            "web_search": ActionSpec(
                key="web_search",
                label="Search the web",
                description="Run a web search query and return structured results. Returns: {summary, rows: [[col1, col2], ...]}. Use $web_search_summary for doc content, $web_search_rows or $web_search_table_values for sheet cell values.",
                keywords=("search", "find", "lookup", "info", "information", "web"),
                parameters=(ParameterSpec("query", "What would you like to search for?", "Top Agentic AI frameworks"),),
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
                parameters=(ParameterSpec("data", "Metadata or activity to log", "User performed X"),),
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
    "tasks": ServiceSpec(
        key="tasks",
        label="Google Tasks",
        aliases=("tasks", "todo", "todo list", "task list"),
        description="Manage task lists and tasks in Google Tasks.",
        actions={
            "list_tasklists": ActionSpec(
                key="list_tasklists",
                label="List task lists",
                description="Returns all the authenticated user's task lists. Returns: {items: [{id, title, updated}]}.",
                keywords=("list", "show", "tasklists", "task lists", "todo lists"),
                parameters=(ParameterSpec("max_results", "Max results to return", "10", required=False),),
            ),
            "list_tasks": ActionSpec(
                key="list_tasks",
                label="List tasks",
                description="Returns all tasks in the specified task list. Returns: {items: [{id, title, status, due}]}.",
                keywords=("list", "show", "tasks", "todos"),
                parameters=(
                    ParameterSpec("tasklist", "Task list ID", "@default"),
                    ParameterSpec("show_completed", "Show completed tasks?", "true", required=False),
                ),
            ),
            "create_task": ActionSpec(
                key="create_task",
                label="Create task",
                description="Creates a new task on the specified task list. Returns: {id, title, status}.",
                keywords=("create", "new", "add", "task", "todo"),
                parameters=(
                    ParameterSpec("title", "Task title", "Buy milk"),
                    ParameterSpec("tasklist", "Task list ID", "@default", required=False),
                    ParameterSpec("notes", "Optional task notes", "", required=False),
                    ParameterSpec("due", "Due date (RFC3339)", "", required=False),
                ),
            ),
            "get_task": ActionSpec(
                key="get_task",
                label="Get task",
                description="Returns the specified task. Returns: {id, title, status, updated, due, notes}.",
                keywords=("get", "show", "read", "task", "todo"),
                parameters=(
                    ParameterSpec("task_id", "The ID of the task", "task-123"),
                    ParameterSpec("tasklist", "Task list ID", "@default", required=False),
                ),
            ),
            "update_task": ActionSpec(
                key="update_task",
                label="Update task",
                description="Updates an existing task. Returns: {id, title, status}.",
                keywords=("update", "edit", "change", "modify", "task", "todo"),
                parameters=(
                    ParameterSpec("task_id", "The ID of the task", "task-123"),
                    ParameterSpec("tasklist", "Task list ID", "@default", required=False),
                    ParameterSpec("title", "New task title", "Buy organic milk", required=False),
                    ParameterSpec("status", "Task status (needsAction, completed)", "completed", required=False),
                    ParameterSpec("notes", "New task notes", "Get 2% milk", required=False),
                    ParameterSpec("due", "Due date (RFC3339)", "2026-04-18T12:00:00Z", required=False),
                ),
            ),
            "delete_task": ActionSpec(
                key="delete_task",
                label="Delete task",
                description="Deletes a task by ID. Returns: {id}.",
                keywords=("delete", "remove", "trash", "task", "todo"),
                parameters=(
                    ParameterSpec("task_id", "The ID of the task", "task-123"),
                    ParameterSpec("tasklist", "Task list ID", "@default", required=False),
                ),
            ),
        },
    ),
    "classroom": ServiceSpec(
        key="classroom",
        label="Google Classroom",
        aliases=("classroom", "class", "course", "courses"),
        description="Manage classes, rosters, and invitations in Google Classroom.",
        actions={
            "list_courses": ActionSpec(
                key="list_courses",
                label="List courses",
                description="Returns a list of courses that the requesting user is permitted to view. Returns: {courses: [{id, name, section, description}]}.",
                keywords=("list", "show", "courses", "classes"),
                parameters=(ParameterSpec("page_size", "Max results", "10", required=False),),
            ),
            "get_course": ActionSpec(
                key="get_course",
                label="Get course",
                description="Returns a specific course by ID. Returns: {id, name, section, description, alternateLink}.",
                keywords=("get", "details", "course", "class"),
                parameters=(ParameterSpec("id", "Course ID", "12345678"),),
            ),
        },
    ),
    "script": ServiceSpec(
        key="script",
        label="Google Apps Script",
        aliases=("script", "gas", "apps script"),
        description="Manages and executes Google Apps Script projects.",
        actions={
            "list_projects": ActionSpec(
                key="list_projects",
                label="List projects",
                description="List the Apps Script projects. Returns: {projects: [{scriptId, title, createTime, updateTime}]}.",
                keywords=("list", "show", "projects", "scripts"),
                parameters=(ParameterSpec("page_size", "Max results", "10", required=False),),
            ),
            "get_project": ActionSpec(
                key="get_project",
                label="Get project",
                description="Get a specific Apps Script project by scriptId. Returns: {scriptId, title, createTime, updateTime}.",
                keywords=("get", "details", "project", "script"),
                parameters=(ParameterSpec("script_id", "Script project ID", "abc12345"),),
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
                parameters=(ParameterSpec("title", "What should the form title be?", "Untitled Form"),),
            ),
            "get_form": ActionSpec(
                key="get_form",
                label="Get form",
                description="Fetch metadata for a Google Form by ID. Returns: {formId, info, items}.",
                keywords=("get", "open", "read", "form"),
                parameters=(ParameterSpec("form_id", "Enter the Google Form ID", "1AbCdEFg123"),),
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
                description="Run a block of Python code. Captured results are available as $code_output.",
                keywords=("run", "execute", "python", "code", "sort", "calculate", "math", "compute"),
                parameters=(
                    ParameterSpec("code", "Python code to execute", "sorted([3, 1, 2])"),
                    ParameterSpec(
                        "file_path",
                        "Optional: Local path to write the output to (e.g. 'data.txt')",
                        "data.txt",
                        required=False,
                    ),
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
                    ParameterSpec(
                        "file_path", "Optional: Local path to write the output to", "calc.txt", required=False
                    ),
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
                parameters=(ParameterSpec("message", "The update message to send", "Completed task X"),),
            ),
        },
    ),
    "workflow": ServiceSpec(
        key="workflow",
        label="GWorkspace Workflow",
        aliases=("workflow", "wf", "pipeline"),
        description="Cross-service productivity workflows managed by the agent.",
        actions={
            "list_workflows": ActionSpec(
                key="list_workflows",
                label="List workflows",
                description="List available automation workflows. Returns: {workflows: [...]}.",
                keywords=("list", "show", "workflows"),
                parameters=(),
            ),
        },
    ),
    "events": ServiceSpec(
        key="events",
        label="Google Workspace Events",
        aliases=("events", "subscriptions", "webhooks"),
        description="Subscribe to events and manage change notifications across Google Workspace applications.",
        actions={
            "list_subscriptions": ActionSpec(
                key="list_subscriptions",
                label="List subscriptions",
                description="Returns all subscriptions for the authenticated user. Returns: {subscriptions: [{name, targetResource, eventTypes}]}.",
                keywords=("list", "show", "subscriptions", "events"),
                parameters=(ParameterSpec("page_size", "Max results", "10", required=False),),
            ),
        },
    ),
    "modelarmor": ServiceSpec(
        key="modelarmor",
        label="Model Armor",
        aliases=("modelarmor", "safety", "filter", "sanitize"),
        description="Protect against risks like prompt injection and harmful content.",
        actions={
            "sanitize_text": ActionSpec(
                key="sanitize_text",
                label="Sanitize text",
                description="Sanitize a block of text through a Model Armor template. Returns: {sanitizedText, findings: [...]}.",
                keywords=("sanitize", "filter", "check", "safety", "clean"),
                parameters=(
                    ParameterSpec("text", "Text to sanitize", "User input here"),
                    ParameterSpec("template", "Model Armor template path", "projects/..."),
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
