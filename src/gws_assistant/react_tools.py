"""Native LangChain @tool wrappers for all Google Workspace actions.

Every tool in this module is a proper LangChain tool that can be bound to an
LLM via `llm.bind_tools(ALL_TOOLS)`.  The ReAct agent calls these tools in its
Thought → Action → Observation loop — the LLM always sees the raw observation
before deciding its next step, which is the core of the ReAct pattern.

Architecture:
  GWSRunner (subprocess wrapper)
      └── PlanExecutor._execute_web_search / _execute_code_task
              └── @tool functions here  (thin wrappers)
                      └── ReAct agent (react_agent.py)

All tools return a JSON-serialisable dict so the LLM can read them cleanly.
"""

from __future__ import annotations

import json
import logging
import traceback
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level mutable references injected at runtime by build_gws_tools().
# ---------------------------------------------------------------------------
_executor: Any = None   # PlanExecutor instance
_config:   Any = None   # AppConfigModel instance


def _run_gws_action(service: str, action: str, parameters: dict[str, Any]) -> dict[str, Any]:
    """Internal helper — resolves, executes, and returns a structured dict result."""
    if _executor is None:
        return {"success": False, "error": "GWS executor not initialised. Call build_gws_tools() first."}
    from .models import PlannedTask
    task = PlannedTask(id=f"{service}-{action}", service=service, action=action,
                       parameters=parameters, reason="ReAct agent invocation")
    context: dict[str, Any] = {}
    try:
        result = _executor.execute_single_task(task, context)
        return {
            "success":    result.success,
            "stdout":     result.stdout or "",
            "stderr":     result.stderr or "",
            "error":      result.error or None,
            "parsed":     result.output.get("parsed_payload") if isinstance(result.output, dict) else None,
            "output":     result.output or None,
        }
    except Exception as exc:
        logger.error("_run_gws_action %s.%s failed: %s", service, action, exc)
        return {"success": False, "error": str(exc), "traceback": traceback.format_exc()}


# ===========================================================================
# Gmail tools
# ===========================================================================

@tool
def gmail_list_messages(q: str = "", max_results: int = 10) -> dict:
    """List Gmail messages matching a query.

    Use Gmail search syntax for `q` (e.g. 'from:boss@company.com subject:invoice').
    Returns a list of message stubs with id and threadId.

    Args:
        q: Gmail search query string.
        max_results: Maximum number of messages to return (default 10).
    """
    return _run_gws_action("gmail", "list_messages", {"q": q, "max_results": max_results})


@tool
def gmail_get_message(message_id: str) -> dict:
    """Fetch the full content of a specific Gmail message by its ID.

    Use this after gmail_list_messages to read the body, headers, and
    attachments of a specific email.

    Args:
        message_id: The Gmail message ID obtained from gmail_list_messages.
    """
    return _run_gws_action("gmail", "get_message", {"message_id": message_id})


@tool
def gmail_send_message(to_email: str, subject: str, body: str,
                       cc: str = "", bcc: str = "", attachments: str = "") -> dict:
    """Send an email via Gmail.

    Compose and send an email to one or more recipients. The body can be
    plain text or HTML.

    Args:
        to_email: Recipient email address.
        subject:  Email subject line.
        body:     Email body text (plain text or basic HTML).
        cc:       Optional CC recipients (comma-separated).
        bcc:      Optional BCC recipients (comma-separated).
        attachments: Optional workspace-relative file path to attach (e.g., 'output/file.pdf').
    """
    import os
    import pathlib

    params: dict[str, Any] = {"to_email": to_email, "subject": subject, "body": body}
    if cc:          params["cc"] = cc
    if bcc:         params["bcc"] = bcc

    # Validate and normalize attachment path if provided
    if attachments:
        workspace_root = os.getenv("GWS_WORKSPACE_ROOT", "/tmp/gws_workspace")
        try:
            # Reject absolute paths
            if os.path.isabs(attachments):
                return {
                    "success": False,
                    "error": f"Absolute paths are not allowed for attachments. Use workspace-relative paths only. Got: {attachments}"
                }

            # Reject paths containing '..'
            if ".." in attachments:
                return {
                    "success": False,
                    "error": f"Path traversal (..) is not allowed in attachments. Got: {attachments}"
                }

            # Build the full path and resolve it
            full_path = pathlib.Path(workspace_root) / attachments
            canonical_path = full_path.resolve()

            # Ensure the canonical path is within the workspace root
            workspace_canonical = pathlib.Path(workspace_root).resolve()
            if not str(canonical_path).startswith(str(workspace_canonical)):
                return {
                    "success": False,
                    "error": f"Attachment path escapes workspace boundary. Workspace: {workspace_canonical}, Requested: {canonical_path}"
                }

            # Reject symlinks
            if canonical_path.is_symlink():
                return {
                    "success": False,
                    "error": f"Symlinks are not allowed for attachments. Got: {attachments}"
                }

            # Verify file exists
            if not canonical_path.exists():
                return {
                    "success": False,
                    "error": f"Attachment file does not exist in workspace: {attachments}"
                }

            if not canonical_path.is_file():
                return {
                    "success": False,
                    "error": f"Attachment path is not a file: {attachments}"
                }

            # Use the validated canonical path
            params["attachments"] = str(canonical_path)

        except Exception as exc:
            return {
                "success": False,
                "error": f"Attachment path validation failed: {exc}"
            }

    return _run_gws_action("gmail", "send_message", params)


@tool
def gmail_search_emails(q: str, max_results: int = 10) -> dict:
    """Search Gmail for messages matching a query and return their full content.

    This is a convenience tool that combines list + get into one call.
    Use this when you need both the list of messages AND their bodies.

    Args:
        q: Gmail search query.
        max_results: How many messages to fetch (default 10, max 50).
    """
    # Enforce max_results cap
    max_results = min(max_results, 50)

    # First, list message IDs
    list_result = _run_gws_action("gmail", "list_messages", {"q": q, "max_results": max_results})
    if not list_result.get("success"):
        return list_result

    # Extract message IDs from the result
    message_ids = []
    output = list_result.get("output") or {}
    parsed = list_result.get("parsed") or output.get("parsed_payload")

    if isinstance(parsed, dict):
        messages = parsed.get("messages", [])
        if isinstance(messages, list):
            message_ids = [msg.get("id") for msg in messages if isinstance(msg, dict) and msg.get("id")]

    # If no messages found, return the list result
    if not message_ids:
        return list_result

    # Fetch full content for each message
    full_messages = []
    for msg_id in message_ids:
        msg_result = _run_gws_action("gmail", "get_message", {"message_id": msg_id})
        if msg_result.get("success"):
            full_messages.append(msg_result.get("output") or msg_result.get("parsed"))
        else:
            # Include error info for failed fetches
            full_messages.append({"id": msg_id, "error": msg_result.get("error")})

    # Return combined result
    return {
        "success": True,
        "messages": full_messages,
        "count": len(full_messages),
        "query": q,
    }


# ===========================================================================
# Google Sheets tools
# ===========================================================================

@tool
def sheets_create_spreadsheet(title: str) -> dict:
    """Create a new Google Spreadsheet with the given title.

    Returns the spreadsheetId and spreadsheetUrl of the newly created sheet.

    Args:
        title: The name/title to give the new spreadsheet.
    """
    return _run_gws_action("sheets", "create_spreadsheet", {"title": title})


@tool
def sheets_append_values(spreadsheet_id: str, range: str, values: list) -> dict:
    """Append rows of data to a Google Spreadsheet.

    Appends data starting from the first empty row below the given range.
    Use `range` like 'Sheet1!A1' or 'Tab Name!A1'.

    Args:
        spreadsheet_id: The ID of the target spreadsheet.
        range:          The A1 notation range to start appending (e.g. 'Sheet1!A1').
        values:         A 2-D list of rows to append (e.g. [['Name', 'Age'], ['Alice', 30]]).
    """
    return _run_gws_action("sheets", "append_values",
                           {"spreadsheet_id": spreadsheet_id, "range": range, "values": values})


@tool
def sheets_get_values(spreadsheet_id: str, range: str) -> dict:
    """Read cell values from a Google Spreadsheet range.

    Returns the grid of values found in the specified range.

    Args:
        spreadsheet_id: The ID of the target spreadsheet.
        range:          A1 notation range to read (e.g. 'Sheet1!A1:D10').
    """
    return _run_gws_action("sheets", "get_values",
                           {"spreadsheet_id": spreadsheet_id, "range": range})


@tool
def sheets_update_values(spreadsheet_id: str, range: str, values: list) -> dict:
    """Update (overwrite) cell values in a Google Spreadsheet range.

    Args:
        spreadsheet_id: The ID of the target spreadsheet.
        range:          A1 notation range to overwrite (e.g. 'Sheet1!A2:C5').
        values:         A 2-D list of values to write.
    """
    return _run_gws_action("sheets", "update_values",
                           {"spreadsheet_id": spreadsheet_id, "range": range, "values": values})


# ===========================================================================
# Google Docs tools
# ===========================================================================

@tool
def docs_create_document(title: str) -> dict:
    """Create a new Google Document with the given title.

    Returns the documentId and document URL.

    Args:
        title: The name/title to give the new document.
    """
    return _run_gws_action("docs", "create_document", {"title": title})


@tool
def docs_get_document(document_id: str) -> dict:
    """Fetch the full content of a Google Document by its ID.

    Returns the document body as structured content.

    Args:
        document_id: The Google Docs document ID.
    """
    return _run_gws_action("docs", "get_document", {"document_id": document_id})


@tool
def docs_batch_update(document_id: str, text: str) -> dict:
    """Insert or replace text content in a Google Document.

    Performs a batchUpdate operation to write content into the document body.

    Args:
        document_id: The Google Docs document ID.
        text:        The text content to insert/write into the document.
    """
    return _run_gws_action("docs", "batch_update", {"document_id": document_id, "text": text})


# ===========================================================================
# Google Drive tools
# ===========================================================================

@tool
def drive_list_files(q: str = "", max_results: int = 10) -> dict:
    """Search and list files in Google Drive.

    Use Drive search syntax for `q` (e.g. 'name contains \"report\"' or
    'mimeType = \"application/vnd.google-apps.spreadsheet\"').

    Args:
        q:           Drive search query string.
        max_results: Maximum number of files to return (default 10).
    """
    return _run_gws_action("drive", "list_files", {"q": q, "max_results": max_results})


@tool
def drive_export_file(file_id: str, mime_type: str = "text/plain") -> dict:
    """Export and download the content of a Google Drive file.

    Use this to read the raw content of Google Docs, Sheets, or Slides.
    Returns the local path where the exported file was saved.

    Args:
        file_id:   The Google Drive file ID.
        mime_type: Export format (default 'text/plain'; use 'text/csv' for sheets).
    """
    return _run_gws_action("drive", "export_file", {"file_id": file_id, "mime_type": mime_type})


@tool
def drive_upload_file(name: str, local_path: str, folder_id: str = "") -> dict:
    """Upload a local file to Google Drive.

    IMPORTANT: Only files within the designated workspace directory can be uploaded.
    Absolute paths, paths containing '..', and symlinks are rejected for security.

    Args:
        name:       The name for the file in Google Drive.
        local_path: The workspace-relative path of the file to upload (e.g., 'output/report.csv').
        folder_id:  Optional parent folder ID in Drive.
    """
    import os
    import pathlib

    # Define workspace root (can be configured via environment or config)
    workspace_root = os.getenv("GWS_WORKSPACE_ROOT", "/tmp/gws_workspace")

    # Validate and canonicalize the path
    try:
        # Reject absolute paths
        if os.path.isabs(local_path):
            return {
                "success": False,
                "error": f"Absolute paths are not allowed. Use workspace-relative paths only. Got: {local_path}"
            }

        # Reject paths containing '..'
        if ".." in local_path:
            return {
                "success": False,
                "error": f"Path traversal (..) is not allowed. Got: {local_path}"
            }

        # Build the full path and resolve it
        full_path = pathlib.Path(workspace_root) / local_path
        canonical_path = full_path.resolve()

        # Ensure the canonical path is within the workspace root
        workspace_canonical = pathlib.Path(workspace_root).resolve()
        if not str(canonical_path).startswith(str(workspace_canonical)):
            return {
                "success": False,
                "error": f"Path escapes workspace boundary. Workspace: {workspace_canonical}, Requested: {canonical_path}"
            }

        # Reject symlinks
        if canonical_path.is_symlink():
            return {
                "success": False,
                "error": f"Symlinks are not allowed. Got: {local_path}"
            }

        # Verify file exists
        if not canonical_path.exists():
            return {
                "success": False,
                "error": f"File does not exist in workspace: {local_path}"
            }

        if not canonical_path.is_file():
            return {
                "success": False,
                "error": f"Path is not a file: {local_path}"
            }

        # Use the validated canonical path
        verified_path = str(canonical_path)

    except Exception as exc:
        return {
            "success": False,
            "error": f"Path validation failed: {exc}"
        }

    # Build params with validated path
    params: dict[str, Any] = {
        "name": name,
        "local_path": verified_path,
        "workspace_root": workspace_root,
        "original_path": local_path,
    }
    if folder_id:
        params["folder_id"] = folder_id
    return _run_gws_action("drive", "upload_file", params)


# ===========================================================================
# Google Calendar tools
# ===========================================================================

@tool
def calendar_list_events(time_min: str = "", time_max: str = "", max_results: int = 10) -> dict:
    """List upcoming events from Google Calendar.

    Args:
        time_min:    RFC3339 datetime lower bound (e.g. '2025-01-01T00:00:00Z').
        time_max:    RFC3339 datetime upper bound.
        max_results: Maximum number of events to return (default 10).
    """
    params: dict[str, Any] = {"max_results": max_results}
    if time_min: params["time_min"] = time_min
    if time_max: params["time_max"] = time_max
    return _run_gws_action("calendar", "list_events", params)


@tool
def calendar_create_event(summary: str, start: str, end: str,
                          description: str = "", attendees: str = "") -> dict:
    """Create a new event in Google Calendar.

    Args:
        summary:     Event title.
        start:       RFC3339 start datetime (e.g. '2025-06-01T10:00:00Z').
        end:         RFC3339 end datetime.
        description: Optional event description.
        attendees:   Optional comma-separated list of attendee email addresses.
    """
    params: dict[str, Any] = {"summary": summary, "start": start, "end": end}
    if description: params["description"] = description
    if attendees:   params["attendees"] = attendees
    return _run_gws_action("calendar", "create_event", params)


# ===========================================================================
# Web Search tool (re-exported for the ReAct agent's tool list)
# ===========================================================================

@tool
def web_search(query: str, max_results: int = 5) -> dict:
    """Search the web for real-time information using DuckDuckGo or Tavily.

    Use this when the user asks for external facts, current news, prices,
    documentation, or any information not available in Google Workspace.

    Args:
        query:       The search query.
        max_results: Number of results to return (default 5).
    """
    try:
        from .tools.web_search import web_search_tool
        return web_search_tool.invoke({"query": query, "max_results": max_results})
    except Exception as exc:
        logger.error("web_search tool failed: %s", exc)
        return {"success": False, "error": str(exc), "results": []}


# ===========================================================================
# Code Execution tool
# ===========================================================================

@tool
def execute_python_code(code: str) -> dict:
    """Execute a snippet of Python code in a sandboxed environment.

    Use this for calculations, data transformations, currency conversions,
    or any computation that requires code. The code MUST store its final
    answer in a variable named `result` and may use `print()` freely.
    Do NOT use import statements — only built-in functions are available.

    Args:
        code: Valid Python code to execute. Must be self-contained.
    """
    if _config is None:
        return {"success": False, "error": "Config not initialised. Call build_gws_tools() first."}
    try:
        from .tools.code_execution import execute_generated_code
        structured = execute_generated_code(code, config=_config)
        output = structured.get("output") or {}
        return {
            "success": structured.get("success", False),
            "stdout":  output.get("stdout") or "",
            "stderr":  output.get("stderr") or "",
            "error":   structured.get("error") or None,
            "result":  structured.get("result") or None,
        }
    except Exception as exc:
        logger.error("execute_python_code failed: %s", exc)
        return {"success": False, "error": str(exc)}


# ===========================================================================
# Tool registry
# ===========================================================================

ALL_TOOLS = [
    # Gmail
    gmail_list_messages,
    gmail_get_message,
    gmail_send_message,
    gmail_search_emails,
    # Sheets
    sheets_create_spreadsheet,
    sheets_append_values,
    sheets_get_values,
    sheets_update_values,
    # Docs
    docs_create_document,
    docs_get_document,
    docs_batch_update,
    # Drive
    drive_list_files,
    drive_export_file,
    drive_upload_file,
    # Calendar
    calendar_list_events,
    calendar_create_event,
    # Utilities
    web_search,
    execute_python_code,
]


def build_gws_tools(executor: Any, config: Any) -> list:
    """Build agent-specific bound tools without mutating global state.

    Creates wrapped versions of all tools that capture the provided executor
    and config in closures, preventing cross-request leakage.

    Args:
        executor: PlanExecutor instance.
        config:   AppConfigModel instance.

    Returns:
        List of bound tool callables with original metadata preserved.
    """
    import functools
    from langchain_core.tools import StructuredTool

    logger.info("react_tools: building bound tools for executor=%s config=%s",
                type(executor).__name__, type(config).__name__)

    # Create a closure that binds executor and config to the helper functions
    def make_run_gws_action(executor_instance: Any):
        """Create a bound version of _run_gws_action."""
        def bound_run_gws_action(service: str, action: str, parameters: dict[str, Any]) -> dict[str, Any]:
            from .models import PlannedTask
            task = PlannedTask(id=f"{service}-{action}", service=service, action=action,
                               parameters=parameters, reason="ReAct agent invocation")
            context: dict[str, Any] = {}
            try:
                result = executor_instance.execute_single_task(task, context)
                return {
                    "success":    result.success,
                    "stdout":     result.stdout or "",
                    "stderr":     result.stderr or "",
                    "error":      result.error or None,
                    "parsed":     result.output.get("parsed_payload") if isinstance(result.output, dict) else None,
                    "output":     result.output or None,
                }
            except Exception as exc:
                logger.error("bound_run_gws_action %s.%s failed: %s", service, action, exc)
                return {"success": False, "error": str(exc), "traceback": traceback.format_exc()}
        return bound_run_gws_action

    # Create bound helpers
    bound_run_gws = make_run_gws_action(executor)

    # Helper to wrap a tool function with bound executor/config
    def bind_tool_func(original_tool, executor_instance: Any, config_instance: Any):
        """Wrap a tool function to use bound executor and config."""
        tool_name = original_tool.name
        tool_description = original_tool.description
        tool_args_schema = original_tool.args_schema

        # Map tool names to their bound implementations
        if tool_name == "gmail_list_messages":
            def bound_func(q: str = "", max_results: int = 10) -> dict:
                return bound_run_gws("gmail", "list_messages", {"q": q, "max_results": max_results})
        elif tool_name == "gmail_get_message":
            def bound_func(message_id: str) -> dict:
                return bound_run_gws("gmail", "get_message", {"message_id": message_id})
        elif tool_name == "gmail_send_message":
            def bound_func(to_email: str, subject: str, body: str,
                           cc: str = "", bcc: str = "", attachments: str = "") -> dict:
                import os
                import pathlib

                params: dict[str, Any] = {"to_email": to_email, "subject": subject, "body": body}
                if cc:          params["cc"] = cc
                if bcc:         params["bcc"] = bcc

                # Validate and normalize attachment path if provided
                if attachments:
                    workspace_root = os.getenv("GWS_WORKSPACE_ROOT", "/tmp/gws_workspace")
                    try:
                        # Reject absolute paths
                        if os.path.isabs(attachments):
                            return {
                                "success": False,
                                "error": f"Absolute paths are not allowed for attachments. Use workspace-relative paths only. Got: {attachments}"
                            }

                        # Reject paths containing '..'
                        if ".." in attachments:
                            return {
                                "success": False,
                                "error": f"Path traversal (..) is not allowed in attachments. Got: {attachments}"
                            }

                        # Build the full path and resolve it
                        full_path = pathlib.Path(workspace_root) / attachments
                        canonical_path = full_path.resolve()

                        # Ensure the canonical path is within the workspace root
                        workspace_canonical = pathlib.Path(workspace_root).resolve()
                        if not str(canonical_path).startswith(str(workspace_canonical)):
                            return {
                                "success": False,
                                "error": f"Attachment path escapes workspace boundary. Workspace: {workspace_canonical}, Requested: {canonical_path}"
                            }

                        # Reject symlinks
                        if canonical_path.is_symlink():
                            return {
                                "success": False,
                                "error": f"Symlinks are not allowed for attachments. Got: {attachments}"
                            }

                        # Verify file exists
                        if not canonical_path.exists():
                            return {
                                "success": False,
                                "error": f"Attachment file does not exist in workspace: {attachments}"
                            }

                        if not canonical_path.is_file():
                            return {
                                "success": False,
                                "error": f"Attachment path is not a file: {attachments}"
                            }

                        # Use the validated canonical path
                        params["attachments"] = str(canonical_path)

                    except Exception as exc:
                        return {
                            "success": False,
                            "error": f"Attachment path validation failed: {exc}"
                        }

                return bound_run_gws("gmail", "send_message", params)
        elif tool_name == "gmail_search_emails":
            def bound_func(q: str, max_results: int = 10) -> dict:
                max_results = min(max_results, 50)
                list_result = bound_run_gws("gmail", "list_messages", {"q": q, "max_results": max_results})
                if not list_result.get("success"):
                    return list_result
                message_ids = []
                output = list_result.get("output") or {}
                parsed = list_result.get("parsed") or output.get("parsed_payload")
                if isinstance(parsed, dict):
                    messages = parsed.get("messages", [])
                    if isinstance(messages, list):
                        message_ids = [msg.get("id") for msg in messages if isinstance(msg, dict) and msg.get("id")]
                if not message_ids:
                    return list_result
                full_messages = []
                for msg_id in message_ids:
                    msg_result = bound_run_gws("gmail", "get_message", {"message_id": msg_id})
                    if msg_result.get("success"):
                        full_messages.append(msg_result.get("output") or msg_result.get("parsed"))
                    else:
                        full_messages.append({"id": msg_id, "error": msg_result.get("error")})
                return {
                    "success": True,
                    "messages": full_messages,
                    "count": len(full_messages),
                    "query": q,
                }
        elif tool_name == "sheets_create_spreadsheet":
            def bound_func(title: str) -> dict:
                return bound_run_gws("sheets", "create_spreadsheet", {"title": title})
        elif tool_name == "sheets_append_values":
            def bound_func(spreadsheet_id: str, range: str, values: list) -> dict:
                return bound_run_gws("sheets", "append_values",
                                     {"spreadsheet_id": spreadsheet_id, "range": range, "values": values})
        elif tool_name == "sheets_get_values":
            def bound_func(spreadsheet_id: str, range: str) -> dict:
                return bound_run_gws("sheets", "get_values",
                                     {"spreadsheet_id": spreadsheet_id, "range": range})
        elif tool_name == "sheets_update_values":
            def bound_func(spreadsheet_id: str, range: str, values: list) -> dict:
                return bound_run_gws("sheets", "update_values",
                                     {"spreadsheet_id": spreadsheet_id, "range": range, "values": values})
        elif tool_name == "docs_create_document":
            def bound_func(title: str) -> dict:
                return bound_run_gws("docs", "create_document", {"title": title})
        elif tool_name == "docs_get_document":
            def bound_func(document_id: str) -> dict:
                return bound_run_gws("docs", "get_document", {"document_id": document_id})
        elif tool_name == "docs_batch_update":
            def bound_func(document_id: str, text: str) -> dict:
                return bound_run_gws("docs", "batch_update", {"document_id": document_id, "text": text})
        elif tool_name == "drive_list_files":
            def bound_func(q: str = "", max_results: int = 10) -> dict:
                return bound_run_gws("drive", "list_files", {"q": q, "max_results": max_results})
        elif tool_name == "drive_export_file":
            def bound_func(file_id: str, mime_type: str = "text/plain") -> dict:
                return bound_run_gws("drive", "export_file", {"file_id": file_id, "mime_type": mime_type})
        elif tool_name == "drive_upload_file":
            def bound_func(name: str, local_path: str, folder_id: str = "") -> dict:
                import os
                import pathlib
                workspace_root = os.getenv("GWS_WORKSPACE_ROOT", "/tmp/gws_workspace")
                try:
                    if os.path.isabs(local_path):
                        return {"success": False, "error": f"Absolute paths are not allowed. Use workspace-relative paths only. Got: {local_path}"}
                    if ".." in local_path:
                        return {"success": False, "error": f"Path traversal (..) is not allowed. Got: {local_path}"}
                    full_path = pathlib.Path(workspace_root) / local_path
                    canonical_path = full_path.resolve()
                    workspace_canonical = pathlib.Path(workspace_root).resolve()
                    if not str(canonical_path).startswith(str(workspace_canonical)):
                        return {"success": False, "error": f"Path escapes workspace boundary. Workspace: {workspace_canonical}, Requested: {canonical_path}"}
                    if canonical_path.is_symlink():
                        return {"success": False, "error": f"Symlinks are not allowed. Got: {local_path}"}
                    if not canonical_path.exists():
                        return {"success": False, "error": f"File does not exist in workspace: {local_path}"}
                    if not canonical_path.is_file():
                        return {"success": False, "error": f"Path is not a file: {local_path}"}
                    verified_path = str(canonical_path)
                except Exception as exc:
                    return {"success": False, "error": f"Path validation failed: {exc}"}
                params: dict[str, Any] = {
                    "name": name,
                    "local_path": verified_path,
                    "workspace_root": workspace_root,
                    "original_path": local_path,
                }
                if folder_id:
                    params["folder_id"] = folder_id
                return bound_run_gws("drive", "upload_file", params)
        elif tool_name == "calendar_list_events":
            def bound_func(time_min: str = "", time_max: str = "", max_results: int = 10) -> dict:
                params: dict[str, Any] = {"max_results": max_results}
                if time_min: params["time_min"] = time_min
                if time_max: params["time_max"] = time_max
                return bound_run_gws("calendar", "list_events", params)
        elif tool_name == "calendar_create_event":
            def bound_func(summary: str, start: str, end: str,
                           description: str = "", attendees: str = "") -> dict:
                params: dict[str, Any] = {"summary": summary, "start": start, "end": end}
                if description: params["description"] = description
                if attendees:   params["attendees"] = attendees
                return bound_run_gws("calendar", "create_event", params)
        elif tool_name == "web_search":
            def bound_func(query: str, max_results: int = 5) -> dict:
                try:
                    from .tools.web_search import web_search_tool
                    return web_search_tool.invoke({"query": query, "max_results": max_results})
                except Exception as exc:
                    logger.error("web_search tool failed: %s", exc)
                    return {"success": False, "error": str(exc), "results": []}
        elif tool_name == "execute_python_code":
            def bound_func(code: str) -> dict:
                try:
                    from .tools.code_execution import execute_generated_code
                    structured = execute_generated_code(code, config=config_instance)
                    output = structured.get("output") or {}
                    return {
                        "success": structured.get("success", False),
                        "stdout":  output.get("stdout") or "",
                        "stderr":  output.get("stderr") or "",
                        "error":   structured.get("error") or None,
                        "result":  structured.get("result") or None,
                    }
                except Exception as exc:
                    logger.error("execute_python_code failed: %s", exc)
                    return {"success": False, "error": str(exc)}
        else:
            # Fallback: return original tool if not matched
            return original_tool

        # Create a StructuredTool with the bound function
        return StructuredTool(
            name=tool_name,
            description=tool_description,
            func=bound_func,
            args_schema=tool_args_schema,
        )

    # Build bound tools list
    bound_tools = []
    for original_tool in ALL_TOOLS:
        bound_tool = bind_tool_func(original_tool, executor, config)
        bound_tools.append(bound_tool)

    return bound_tools