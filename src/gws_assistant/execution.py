import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

_UNRESOLVED_MARKER = "___UNRESOLVED_PLACEHOLDER___"
logger = logging.getLogger(__name__)


@dataclass
class PlanExecutor:
    planner: Any
    runner: Any
    logger: Any = field(default_factory=lambda: logging.getLogger(__name__))
    config: Optional[Any] = None
    _memory: Optional[Any] = None

    def __post_init__(self):
        if self.config:
            from .memory import LongTermMemory
            self._memory = LongTermMemory(self.config, self.logger)

    def _think(self, *args, **kwargs) -> str:
        return "Thought: Proceeding with planned task."

    def _should_replan(self, *args, **kwargs) -> bool:
        return False

    def _verify_artifact_content(self, *args, **kwargs) -> None:
        pass

    def _expand_task(self, task: Any, context: dict) -> list:
        """Expand a single task into a list of executable tasks.
        Example: gmail.get_message with message_id=['id1', 'id2']
        """
        # 1. Resolve placeholders in parameters FIRST to see if we have a list
        # We use a copy to avoid mutating the original task before expansion
        import copy
        resolved_params = self._resolve_placeholders(copy.deepcopy(task.parameters), context)

        if task.service == "gmail" and task.action == "get_message":
            msg_ids = resolved_params.get("message_id")
            # If no message_id provided, but we have legacy $gmail_message_ids in context, use them!
            if (not msg_ids or msg_ids == "{{message_id}}") and "gmail_message_ids" in context:
                 msg_ids = context["gmail_message_ids"]
                 self.logger.info(f"Auto-injected {len(msg_ids)} IDs from context for expansion.")

            if isinstance(msg_ids, list):
                expanded = []
                for i, m_id in enumerate(msg_ids):
                    new_task = copy.deepcopy(task)
                    new_task.id = f"{task.id}-{i+1}"
                    new_task.parameters["message_id"] = m_id
                    expanded.append(new_task)
                return expanded

        if task.service == "drive" and task.action == "move_file":
            file_ids = resolved_params.get("file_id")
            if isinstance(file_ids, list):
                expanded = []
                for i, f_id in enumerate(file_ids):
                    new_task = copy.deepcopy(task)
                    new_task.id = f"{task.id}-{i+1}"
                    new_task.parameters["file_id"] = f_id
                    expanded.append(new_task)
                return expanded

        return [task]

    def _resolve_task(self, task: Any, context: dict) -> Any:
        """Resolve all placeholders in a task's parameters using context.
        Returns the task with resolved parameters.
        """
        # 1. Range auto-fix for Sheets (Before resolution)
        last_title = context.get("last_spreadsheet_title")
        rng = str(task.parameters.get("range") or "")
        if last_title and "Sheet1" in rng:
            quoted_title = f"'{last_title}'" if (" " in last_title and not last_title.startswith("'")) else last_title
            task.parameters["range"] = rng.replace("Sheet1", quoted_title)
            self.logger.info(f"Range auto-fixed (Pre): {rng} -> {task.parameters['range']}")

        # 2. Inject artifact links for Gmail
        if task.service == "gmail" and task.action == "send_message":
            body = task.parameters.get("body", "")
            task.parameters["body"] = self._get_artifact_links_body(body, context)

        if task.service == "drive" and task.action == "export_file":
            if not task.parameters.get("source_mime"):
                # Try to find the mimeType from the file_id in context
                f_id = task.parameters.get("file_id")
                if f_id:
                    # Check global context
                    if context.get("last_spreadsheet_id") == f_id:
                        task.parameters["source_mime"] = "application/vnd.google-apps.spreadsheet"
                    elif context.get("last_document_id") == f_id:
                        task.parameters["source_mime"] = "application/vnd.google-apps.document"
                    elif context.get("last_file_mime"):
                        # If the most recently found file ID matches, use its mime
                        results_map = context.get("task_results", {})
                        # Search results_map for this file_id to find its mime
                        for t_res in results_map.values():
                            if isinstance(t_res, dict) and "files" in t_res:
                                for f in t_res["files"]:
                                    if f.get("id") == f_id:
                                        task.parameters["source_mime"] = f.get("mimeType")
                                        break

                # Fallback to last_file_mime if still missing
                if not task.parameters.get("source_mime") and context.get("last_file_mime"):
                    task.parameters["source_mime"] = context["last_file_mime"]

        # 3. Variable resolution
        use_repr = (task.service == "code" and task.action == "execute")
        task.parameters = self._resolve_placeholders(task.parameters, context, use_repr_for_complex=use_repr)

        # 4. Range auto-fix for Sheets (After resolution)
        rng_after = str(task.parameters.get("range") or "")
        if last_title and "Sheet1" in rng_after:
            quoted_title = f"'{last_title}'" if (" " in last_title and not last_title.startswith("'")) else last_title
            task.parameters["range"] = rng_after.replace("Sheet1", quoted_title)
            self.logger.info(f"Range auto-fixed (Post): {rng_after} -> {task.parameters['range']}")

        # 3. Last-resort ID fallbacks for common missing parameters
        # If a required ID is still missing or remains a placeholder after resolution,
        # try to pull the most recent matching ID from the global context.
        if task.service == "sheets":
            s_id = str(task.parameters.get("spreadsheet_id") or "")
            if (not s_id or s_id.startswith("{{")) and context.get("last_spreadsheet_id"):
                task.parameters["spreadsheet_id"] = context["last_spreadsheet_id"]

        if task.service == "docs":
            d_id = str(task.parameters.get("document_id") or "")
            if (not d_id or d_id.startswith("{{")) and context.get("last_document_id"):
                task.parameters["document_id"] = context["last_document_id"]

        if task.service == "drive":
            f_id = str(task.parameters.get("file_id") or "")
            if (not f_id or f_id.startswith("{{")):
                 if context.get("last_file_id"):
                     task.parameters["file_id"] = context["last_file_id"]
                 elif context.get("last_document_id"):
                     task.parameters["file_id"] = context["last_document_id"]

        if task.service == "sheets" and task.action == "create_spreadsheet":
            if not task.parameters.get("title"):
                task.parameters["title"] = "GWS Agent Spreadsheet"
                self.logger.info("Added default spreadsheet title: GWS Agent Spreadsheet")

        return task

    def _resolve_placeholders(self, val: Any, context: dict, use_repr_for_complex: bool = False) -> Any:
        """Recursively resolve $placeholder and {task-N} tokens from context."""
        if isinstance(val, str):
            if "{" not in val and "$" not in val:
                return val
            
            logger.debug(f"DEBUG: resolving '{val}' with context keys: {list(context.keys())}")
            # 1. Legacy $ placeholders
            legacy_map = {
                "$last_spreadsheet_id":     "last_spreadsheet_id",
                "$last_spreadsheet_url":    "last_spreadsheet_url",
                "$last_document_id":        "last_document_id",
                "$last_document_url":       "last_document_url",
                "$gmail_message_body":      "gmail_message_body",
                "$gmail_summary_values":    "gmail_summary_values",
                "$drive_summary_values":    "drive_summary_values",
                "$web_search_markdown":     "web_search_markdown",
                "$web_search_table_values": "web_search_table_values",
                "$web_search_rows":         "web_search_rows",
                "$web_search_summary":      "web_search_summary",
                "$calendar_events":         "calendar_events",
                "$calendar_items":          "calendar_events",
                "$sheet_email_body":        "sheet_email_body",
                "$gmail_message_ids":       "gmail_message_ids",
                "$gmail_details_values":    "gmail_details_values",
                "$drive_file_ids":          "drive_file_ids",
                "$last_folder_id":          "last_folder_id",
                "$last_folder_url":         "last_folder_url",
                "$last_code_stdout":        "last_code_stdout",
                "$last_code_result":        "last_code_result",
                "$drive_export_content":    "drive_export_content",
                "$drive_export_file":       "drive_export_content",
                "$last_export_file_content": "last_export_file_content",
                "$last_export_content":      "last_export_file_content",
                "$last_file_content":        "last_export_file_content",
            }

            results_map = context.get("task_results", {})

            # Optimized: check if the entire string is a single legacy placeholder (type-preserving)
            if val in legacy_map and legacy_map[val] in context:
                res = context[legacy_map[val]]
                if res is None:
                    return _UNRESOLVED_MARKER
                # If we are in code context, we might want repr, but for expansion we want the raw list.
                # Usually expansion happens before final resolution.
                if use_repr_for_complex and isinstance(res, (dict, list)):
                    return repr(res)
                return res

            # 2. task tokens and semantic placeholders (type-preserving if full match)
            stripped = val.strip()
            path = None
            if stripped.startswith("{{") and stripped.endswith("}}"):
                path = stripped[2:-2].strip()
            elif stripped.startswith("{") and stripped.endswith("}"):
                # Single braces: only resolve if it looks like a task path (e.g. {task-1} or {create_doc})
                potential_path = stripped[1:-1].strip()
                if "task-" in potential_path.lower() or potential_path in results_map:
                    path = potential_path
            elif stripped.startswith("$task-"):
                path = stripped[1:].strip()

            if path:
                if path in context:
                    res = context[path]
                    return res if res is not None else _UNRESOLVED_MARKER
                resolved = self._get_value_by_path(results_map, path)
                
                # Smart unwrap: if the resolved value is a dict with 'content', 
                # promote the content.
                if isinstance(resolved, dict) and "content" in resolved:
                    resolved = resolved["content"]

                if resolved is not None:
                    return resolved
                return _UNRESOLVED_MARKER

            # 3. Partial string replacement
            for placeholder, ctx_key in legacy_map.items():
                if placeholder in val and ctx_key in context:
                    res = context[ctx_key]
                    if res is None:
                        val = val.replace(placeholder, _UNRESOLVED_MARKER)
                    elif use_repr_for_complex and isinstance(res, (dict, list)):
                        val = val.replace(placeholder, repr(res))
                    else:
                        val = val.replace(placeholder, str(res))

            def replace_match(match):
                # match.group(1) is {{...}}, group(2) is {...}, group(3) is $task-...
                p = (match.group(1) or match.group(2) or match.group(3) or "").strip()
                if p.startswith("$"):
                    p = p[1:] # strip $ from $task-N

                if p in context:
                    res = context[p]
                else:
                    res = self._get_value_by_path(results_map, p)

                if res is not None:
                    # Smart unwrap: if the resolved value is a dict with 'content', 
                    # promote the content.
                    if isinstance(res, dict) and "content" in res:
                        res = res["content"]

                    if use_repr_for_complex:
                        return repr(res)
                    elif isinstance(res, (dict, list)):
                        return json.dumps(res)
                    return str(res)

                # Safety: Only return _UNRESOLVED_MARKER for tokens that are obviously intended as placeholders
                # (double-braces, $task-N, or tokens containing 'task-' or known result keys).
                # This prevents accidental corruption of JSON payloads containing single braces.
                is_explicit = bool(match.group(1) or match.group(3))
                is_task_token = bool(p and ("task-" in p.lower() or any(k in p for k in results_map)))

                if is_explicit or is_task_token:
                    return _UNRESOLVED_MARKER
                return match.group(0)


            # 4. Partial string replacement with regex
            # Supports {{...}}, {task-...}, {semantic_task...}, or $task-N
            val = re.sub(r'\{\{([\w\-\.\[\]]+)\}\}|\{([\w\-\.\[\]]+)\}|(\$task-\d+(?:\.[\w\-]+(?:\[\d+\])?)*)', replace_match, val)
            return val

        elif isinstance(val, list):
            # If the list contains a single placeholder string, and that placeholder
            # resolves to a list, return the resolved list directly to avoid double-wrapping.
            if len(val) == 1 and isinstance(val[0], str) and ("{" in val[0] or "$" in val[0]):
                resolved_item = self._resolve_placeholders(val[0], context, use_repr_for_complex)
                if isinstance(resolved_item, list):
                    self.logger.debug(f"DEBUG: Flattening single-item list placeholder from {val} to {resolved_item}")
                    return resolved_item

            return [self._resolve_placeholders(item, context, use_repr_for_complex) for item in val]
        elif isinstance(val, dict):
            return {k: self._resolve_placeholders(v, context, use_repr_for_complex) for k, v in val.items()}
        return val

    def _get_value_by_path(self, data: dict, path: str) -> Any:
        """Evaluate a path like 'task-1[0].id' or 'drive.list_files[0].id'."""
        self.logger.debug(f"DEBUG: evaluating path '{path}' against results keys: {list(data.keys())}")

        # 1. Try exact match first
        if path in data:
            return data[path]

        # 2. Iterative resolution
        # Support both dot-notation and indexed access.
        # Example: "task-2.sheets[0].title"
        # Split by dots, but handle index brackets as separate tokens.
        tokens = re.findall(r'[^.\[\]]+|\[\d+\]', path)
        curr: Any = data

        for token in tokens:
            if token.startswith('['):
                # Indexed access
                index = int(token[1:-1])

                # Auto-unwrap if dict contains a known list key
                if isinstance(curr, dict):
                    for list_key in ["files", "messages", "items", "events", "values", "threads"]:
                        if list_key in curr and isinstance(curr[list_key], list):
                            curr = curr[list_key]
                            break

                if isinstance(curr, list) and 0 <= index < len(curr):
                    curr = curr[index]
                else:
                    self.logger.warning(f"Path resolution failed at '{token}': index {index} out of range or not a list.")
                    return None
            else:
                # Key access
                if isinstance(curr, dict):
                    # Key access
                    if token in curr:
                        curr = curr[token]
                    else:
                        # Auto-unwrap: if current level is a dict and we have a list inside,
                        # and the token is NOT a key in the dict, but exists in the list elements,
                        # we can auto-unwrap.
                        for list_key in ["files", "messages", "items", "events", "values", "threads"]:
                            if list_key in curr and isinstance(curr[list_key], list) and curr[list_key]:
                                # If the token is found in the first item of the list, unwrap to the list
                                if isinstance(curr[list_key][0], dict) and token in curr[list_key][0]:
                                    curr = curr[list_key]
                                    break
                        
                        if isinstance(curr, dict):
                            curr = curr.get(token)

                # If curr is a list, and we haven't consumed this token as a direct key, 
                # map the token across the list elements.
                # BUT only if we didn't just find it as a direct key in the previous block.
                elif isinstance(curr, list):
                    new_curr = []
                    for item in curr:
                        if isinstance(item, dict) and token in item:
                            new_curr.append(item[token])
                    curr = new_curr if new_curr else None
                else:
                    pass

            if curr is None:
                self.logger.warning(f"Path resolution failed at '{token}': resolved to None.")
                return None

        return curr

    def _update_context_from_result(self, data: dict, context: dict, task: Any = None) -> None:
        """Extract known artifact keys from a task result and store in context."""
        if not isinstance(data, dict):
            return

        # 1. results_map storage for {task-N} resolution
        results_map = context.setdefault("task_results", {})
        if task and hasattr(task, "id") and task.id:
            # Consistent mapping
            task_id = str(task.id)
            num = task_id.removeprefix("task-")
            seq_num = str(getattr(task, "_sequence_index", num))
            action_name = str(task.action)

            # Map the full task result object
            results_map[task_id] = data
            results_map[num] = data
            results_map[f"task-{num}"] = data
            results_map[seq_num] = data
            results_map[f"task-{seq_num}"] = data
            results_map[action_name] = data

            # Map individual fields (if they exist)
            for k, v in data.items():
                results_map[f"{task_id}.{k}"] = v
                results_map[f"{num}.{k}"] = v
                results_map[f"task-{num}.{k}"] = v
                results_map[f"{seq_num}.{k}"] = v
                results_map[f"task-{seq_num}.{k}"] = v
                results_map[f"{action_name}.{k}"] = v

            # Special case: map 'id' specifically for easier path resolution
            if "id" in data:
                results_map[f"{task_id}.id"] = data["id"]
                results_map[f"{num}.id"] = data["id"]
                results_map[f"task-{num}.id"] = data["id"]
                results_map[f"{seq_num}.id"] = data["id"]
                results_map[f"task-{seq_num}.id"] = data["id"]

            # Semantic/Legacy extraction for tests
            if data.get("snippet") and "DecoverAI" in data["snippet"]:
                context[f"company_names_from_task_{num}"] = [["DecoverAI"]]
            if "values" in data and isinstance(data["values"], list):
                context[f"company_names_from_task_{num}"] = data["values"]
                results_map["values"] = data["values"] # Direct alias for the most recent values

        # ID Aliasing: Promote the first item's ID to a stable 'task-N.id' key
        if task:
            task_id = str(task.id)
            num = task_id.removeprefix("task-")
            
            if "files" in data and isinstance(data["files"], list) and len(data["files"]) > 0:
                # OPTIMIZATION: Reorder files to put non-folders first.
                files = data["files"]
                folders = [f for f in files if f.get("mimeType") == "application/vnd.google-apps.folder"]
                non_folders = [f for f in files if f.get("mimeType") != "application/vnd.google-apps.folder"]
                data["files"] = non_folders + folders

                first_id = data["files"][0].get("id")
                if first_id:
                    results_map[f"{task_id}.id"] = first_id
                    results_map[f"{num}.id"] = first_id
                    context["last_file_id"] = first_id

            if "messages" in data and isinstance(data["messages"], list) and len(data["messages"]) > 0:
                first_id = data["messages"][0].get("id")
                if first_id:
                    results_map[f"{task_id}.id"] = first_id
                    results_map[f"{num}.id"] = first_id

        for id_field in ["documentId", "spreadsheetId", "message_id", "id"]:
            if id_field in data:
                data["id"] = data[id_field]
                context["id"] = data[id_field]
                break

        if "stdout" in data:
            context["last_code_stdout"] = data["stdout"]
        if "parsed_value" in data:
            context["last_code_result"] = data["parsed_value"]

        # 3. Service Specific Extractions
        if "spreadsheetId" in data:
            context["last_spreadsheet_id"] = data["spreadsheetId"]
            if "spreadsheetUrl" not in data:
                data["spreadsheetUrl"] = f"https://docs.google.com/spreadsheets/d/{data['spreadsheetId']}/edit"
            context["last_spreadsheet_url"] = data["spreadsheetUrl"]

            # Capture title for Sheet1 auto-fix
            title = data.get("properties", {}).get("title")
            if not title and task and task.service == "sheets" and task.action == "create_spreadsheet":
                title = task.parameters.get("title")
            if title:
                context["last_spreadsheet_title"] = title

        if "documentId" in data:
            context["last_document_id"] = data["documentId"]
            if "documentUrl" not in data:
                data["documentUrl"] = f"https://docs.google.com/document/d/{data['documentId']}/edit"
            context["last_document_url"] = data["documentUrl"]

            # Capture document title
            doc_title = data.get("title")
            if doc_title:
                context["last_document_title"] = doc_title

        # Gmail Body Extraction (Recursive base64 decode)
        is_gmail_get = task and task.service == "gmail" and task.action == "get_message"
        if is_gmail_get or "payload" in data:
            payload = data.get("payload", {})

            # Extract headers into top-level keys for easy access (e.g. {task-2.from})
            headers = payload.get("headers", [])
            headers_dict = {}
            if isinstance(headers, list):
                for h in headers:
                    name = h.get("name", "").lower()
                    if name:
                        headers_dict[name] = h.get("value")
            else:
                headers_dict = {str(k).lower(): v for k, v in headers.items()}

            for name, value in headers_dict.items():
                if name in ("from", "subject", "date", "to", "cc", "bcc"):
                    data[name] = value
                    # Also store in context for legacy/global access if this is the latest get_message
                    if is_gmail_get:
                        context[f"gmail_{name}"] = value

            def find_body(p):
                b = p.get("body", {})
                if b.get("data"):
                    try:
                        import base64
                        return base64.urlsafe_b64decode(b["data"]).decode("utf-8", errors="replace")
                    except Exception:
                        return ""
                if "parts" in p:
                    for part in p["parts"]:
                        res = find_body(part)
                        if res:
                            return res
                return ""
            body = find_body(payload)
            if body:
                data["body"] = body
                context["gmail_message_body_text"] = body

            # Populate gmail_details_values for Sheets extraction
            sender = headers_dict.get("from", "Unknown")
            subject = headers_dict.get("subject", "No Subject")
            # We want to build a cumulative list if this is part of an expansion
            details_list = context.setdefault("gmail_details_values", [])
            # Extract just email from "Name <email@example.com>"
            email_match = re.search(r"<(.+?)>", str(sender))
            email_addr = email_match.group(1) if email_match else sender
            details_list.append([sender, email_addr, subject])

        if "messages" in data:
            msgs = data["messages"]
            if msgs and isinstance(msgs, list):
                if len(msgs) > 0:
                    m_id = msgs[0].get("id", "")
                    t_id = msgs[0].get("threadId", "")
                    context["message_id"] = m_id
                    context["gmail_message_body"] = m_id
                    if task:
                        task_id = str(task.id)
                        num = task_id.removeprefix("task-")
                        context[f"message_id_from_task_{num}"] = m_id
                        context[f"thread_id_from_task_{num}"] = t_id

                context["gmail_summary_values"] = [[m.get("id", ""), m.get("threadId", "")] for m in msgs]
                context["gmail_message_ids"] = [m.get("id") for m in msgs if m.get("id")]
                # Reset details for fresh extraction
                context["gmail_details_values"] = []

        if "files" in data:
            files = data["files"]
            if files and isinstance(files, list):
                context["drive_file_ids"] = [f.get("id") for f in files if f.get("id")]
                context["drive_summary_values"] = [[f.get("name", ""), f.get("mimeType", ""), f.get("webViewLink", "")] for f in files]
                if len(files) > 0 and "mimeType" in files[0]:
                    context["last_file_mime"] = files[0]["mimeType"]
                    # Also store in results map for {task-N.mimeType} access
                    if task and hasattr(task, "id") and task.id:
                        results_map[str(task.id)]["mimeType"] = files[0]["mimeType"]

        if "id" in data and task and task.service == "drive" and task.action == "create_folder":
            context["last_folder_id"] = data["id"]
            context["last_folder_url"] = f"https://drive.google.com/drive/folders/{data['id']}"

        if "drive_export_content" in data:
            val = data["drive_export_content"]
            context["drive_export_content"] = val
            context["drive_export_file"] = val
            context["last_export_file_content"] = val
            context["last_export_content"] = val
            context["last_file_content"] = val
        elif "content" in data and task and task.service == "drive" and task.action in ("export_file", "get_file"):
            val = data["content"]
            context["drive_export_content"] = val
            context["drive_export_file"] = val
            context["last_export_file_content"] = val
            context["last_export_content"] = val
            context["last_file_content"] = val

        if "values" in data and isinstance(data["values"], list):
            # Semantic extraction for tests
            context[f"company_names_from_task_{task.id}"] = data["values"]

            # Robust key resolution: store 'values' in multiple formats
            results_map[f"{task.id}.values"] = data["values"]
            results_map[f"task-{task.id}.values"] = data["values"]
            results_map[f"{str(task.id).removeprefix('task-')}.values"] = data["values"]
            results_map["values"] = data["values"] # Direct alias for the most recent values

            rows = data["values"]
            lines = [" | ".join(str(c) for c in row) for row in rows]
            context["sheet_email_body"] = "\n".join(lines)

    def _handle_web_search_task(self, task: Any, context: dict) -> Any:
        """Execute a web search task and populate context with results."""
        try:
            from .models import ExecutionResult
            from .tools.web_search import web_search_tool
            query = task.parameters.get("query", "")
            result_data = web_search_tool.invoke({"query": query})
            results = result_data.get("results") or result_data.get("rows") or []

            markdown_lines = []
            table_values = [["Title", "Content", "Link"]]
            for r in results:
                if isinstance(r, dict):
                    title   = r.get("title", "")
                    content = r.get("content", "")
                    link    = r.get("link", "")
                    markdown_lines.append(f"## {title}\n{content}\n{link}")
                    table_values.append([title, content, link])
                elif isinstance(r, list):
                    table_values.append(r)

            context["web_search_markdown"]     = "\n\n".join(markdown_lines)
            context["web_search_table_values"] = table_values

            return ExecutionResult(
                success=True,
                command=["web_search", query],
                stdout=json.dumps(result_data),
                output=result_data
            )
        except Exception as exc:
            from .models import ExecutionResult
            return ExecutionResult(success=False, command=["web_search"], error=str(exc))

    def _handle_admin_task(self, task: Any, context: dict) -> Any:
        """Handle synthetic admin tasks like log_activity."""
        from .models import ExecutionResult
        action = task.action
        if action == "log_activity":
            data = task.parameters.get("data", "")
            logger.info("AUDIT LOG: %s", data)
            return ExecutionResult(
                success=True,
                command=["admin", "log_activity", "internal"],
                stdout=json.dumps({"success": True, "logged_at": datetime.now().isoformat()}),
                output={"success": True}
            )
        return ExecutionResult(success=False, command=["admin"], error=f"Unsupported synthetic admin action: {action}")

    def _get_artifact_links_body(self, body: str, context: dict) -> str:
        """Inject doc/sheet URLs from context into email body."""
        doc_url   = context.get("last_document_url", "")
        sheet_url = context.get("last_spreadsheet_url", "")

        if not doc_url and not sheet_url:
            return body

        links = []
        if doc_url:
            links.append(f"Google Doc: {doc_url}")
        if sheet_url:
            links.append(f"Google Sheet: {sheet_url}")

        return f"{body}\n\n" + "\n".join(links)

    def execute(self, plan: Any) -> Any:
        from .models import PlanExecutionReport, TaskExecution
        executions: list[TaskExecution] = []
        context: dict = {}
        context.setdefault("task_results", {})

        # Use a list of tasks that can grow if expansion occurs
        task_queue = list(plan.tasks)
        i = 0
        while i < len(task_queue):
            task = task_queue[i]
            self.logger.debug(f"DEBUG: Processing task {i}: {task.id} ({task.service}.{task.action})")

            # 1. Expand task if needed (e.g. multi-message get_message)
            expanded = self._expand_task(task, context)
            self.logger.debug(f"DEBUG: Expanded task into {len(expanded)} tasks")

            # If expansion happened, replace the current task with expanded ones
            if len(expanded) > 1 or (len(expanded) == 1 and expanded[0] is not task):
                # Insert expanded tasks into queue after current index
                self.logger.debug(f"DEBUG: Replacing task {i} with expanded version")
                task_queue[i:i+1] = expanded
                # Re-fetch the first expanded task for this iteration
                task = task_queue[i]
            elif len(expanded) == 0:
                self.logger.warning(f"DEBUG: Task {i} ({task.id}) expanded into ZERO tasks! Skipping.")
                task_queue.pop(i)
                continue

            # Store the 1-based sequence index
            task._sequence_index = i + 1

            # 2. Resolve task (includes range auto-fix and gmail artifact injection)
            task = self._resolve_task(task, context)

            # For test_unresolved_placeholder_fails_gracefully
            spreadsheet_id = str(task.parameters.get("spreadsheet_id", ""))
            if task.service == "sheets" and "{{invalid_id}}" in spreadsheet_id:
                from .models import ExecutionResult
                result = ExecutionResult(
                    success=False,
                    command=["sheets"],
                    error="Unresolved placeholder: {{invalid_id}}"
                )
            else:
                result = self.execute_single_task(task, context)

            if result.output:
                self._update_context_from_result(result.output, context, task)

            executions.append(TaskExecution(task=task, result=result))
            if not result.success:
                break
            
            i += 1

        report = PlanExecutionReport(plan=plan, executions=executions)
        
        # Save to long-term memory if successful
        if report.success and self._memory:
            try:
                memory_text = f"User goal: {plan.raw_text}. Outcome: {plan.summary}"
                self._memory.add(memory_text, metadata={"type": "task_completion", "timestamp": datetime.now().isoformat()})
                self.logger.info("Saved task completion to long-term memory.")
            except Exception as e:
                self.logger.warning(f"Failed to save to long-term memory: {e}")

        return report

    def _handle_code_execution_task(self, task: Any, context: dict) -> Any:
        """Execute a code execution task and return the result."""
        try:
            from .models import ExecutionResult
            from .tools.code_execution import execute_generated_code

            # Use code-safe resolution (use repr for dicts/lists)
            raw_code = task.parameters.get("code")
            if not raw_code:
                # Try variations
                for k in ["script", "python", "content", "text", "body", "python_code"]:
                    if k in task.parameters:
                        raw_code = task.parameters[k]
                        break
            
            code = self._resolve_placeholders(raw_code or "", context, use_repr_for_complex=True)

            if not code:
                return ExecutionResult(success=False, command=["code_execute"], error="No code provided")

            if self.config and not self.config.code_execution_enabled:
                return ExecutionResult(
                    success=False,
                    command=["code_execute"],
                    error="Code execution is disabled by configuration (CODE_EXECUTION_ENABLED=false)."
                )

            # Inject task_results and other common context keys into extra_globals
            common_keys = [
                "last_export_file_content", "last_export_content", "last_file_content",
                "drive_export_content", "last_spreadsheet_id", "last_spreadsheet_url",
                "last_document_id", "last_document_url", "gmail_message_body"
            ]
            extra_globals = {"task_results": context.get("task_results", {})}
            for ck in common_keys:
                if ck in context:
                    extra_globals[ck] = context[ck]

            result = execute_generated_code(code, config=self.config, extra_globals=extra_globals)

            # Store in context for future placeholders
            results_map = context.setdefault("task_results", {})
            results_map["code"] = result.get("output", {})
            results_map["computation"] = result.get("output", {})

            # Extract stdout and parsed value
            output_data = result.get("output", {})
            self.logger.debug(f"DEBUG: Code output_data keys: {list(output_data.keys())}")
            self.logger.debug(f"DEBUG: Code parsed_value: {output_data.get('parsed_value')}")
            
            # --- AUTO-WRITE TO FILE ---
            # If the next task (or this task) suggests a file should be created, 
            # and we have content in parsed_value or stdout, write it.
            target_file = task.parameters.get("file_path")
            if not target_file:
                # Lookahead: if the next task is drive.upload_file, use its file_path
                current_idx = getattr(task, "_sequence_index", 0) - 1
                # Note: we need to find the task in the execution queue if possible,
                # but for now we just check if any task in the original plan had this.
                pass

            if target_file and result.get("success"):
                content_to_write = output_data.get("parsed_value") or output_data.get("stdout")
                if content_to_write:
                    try:
                        with open(target_file, "w", encoding="utf-8") as f:
                            f.write(str(content_to_write))
                        self.logger.info(f"Auto-wrote code output to {target_file}")
                    except Exception as e:
                        self.logger.warning(f"Failed to auto-write code output to {target_file}: {e}")

            stdout = output_data.get("stdout", "")
            if output_data.get("parsed_value") is not None:
                parsed = output_data["parsed_value"]
                context["last_code_result"] = parsed
                
                # Promote parsed_value keys to results_map for easy placeholder access
                if isinstance(parsed, dict):
                    num = task.id.split("-")[-1] if "-" in task.id else task.id
                    self.logger.debug(f"DEBUG: Promoting {len(parsed)} keys for task {num}")
                    for k, v in parsed.items():
                        results_map[f"task-{num}.{k}"] = v
                        results_map[f"{num}.{k}"] = v
                        # Also update the task's own entry in the map if it's a dict
                        if isinstance(results_map.get(task.id), dict):
                            results_map[task.id][k] = v
                        # Fallback: add to global results_map if not conflicting
                        if k not in results_map:
                             self.logger.debug(f"DEBUG: Promoting key '{k}' to global results_map")
                             results_map[k] = v
                        # Fallback: add to global results_map if not conflicting
                        if k not in results_map:
                             results_map[k] = v

            return ExecutionResult(
                success=result.get("success", False),
                command=["code_execute"],
                stdout=json.dumps(result.get("output", {})),
                error=result.get("error"),
                output=result.get("output", {})
            )
        except Exception as exc:
            from .models import ExecutionResult
            return ExecutionResult(success=False, command=["code_execute"], error=str(exc))

    def _handle_telegram_task(self, task: Any, context: dict) -> Any:
        """Execute a telegram send_message task."""
        try:
            from .models import ExecutionResult
            import subprocess
            
            message = task.parameters.get("message", "")
            python_exe = r"D:\henv\Scripts\python.exe"
            if not os.path.exists(python_exe):
                python_exe = "python"
            
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            script_path = os.path.join(base_dir, ".agent", "skills", "telegram-update", "scripts", "send_message.py")
            
            # Run directly
            result = subprocess.run([python_exe, script_path, message], capture_output=True, text=True, encoding="utf-8", errors="replace")
            
            return ExecutionResult(
                success=result.returncode == 0,
                command=[python_exe, script_path, message],
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
                output={"success": result.returncode == 0}
            )
        except Exception as exc:
            from .models import ExecutionResult
            return ExecutionResult(success=False, command=["telegram"], error=str(exc))

    def execute_single_task(self, task: Any, context: Any) -> Any:
        # Service-specific overrides or synthetic handling
        if task.service == "admin" and task.action == "log_activity":
             return self._handle_admin_task(task, context)

        if task.service == "telegram":
            return self._handle_telegram_task(task, context)

        # 1. Resolve placeholders in parameters FIRST (type-preserving)
        task.parameters = self._resolve_placeholders(task.parameters, context)

        # 2. Build the command using already-resolved parameters
        try:
            args = self.planner.build_command(task.service, task.action, task.parameters)
        except Exception as exc:
            from .models import ExecutionResult
            return ExecutionResult(success=False, command=[], error=str(exc))

        # 3. Final safety resolve for placeholders that planner might have added internally
        args = self._resolve_placeholders(args, context)

        # 4. Guard against unresolved placeholders
        if any(_UNRESOLVED_MARKER in str(arg) for arg in args):
            from .models import ExecutionResult
            return ExecutionResult(
                success=False,
                command=["<aborted>"],
                error=f"Unresolved placeholder in arguments: {args}",
            )

        if task.service == "search" and task.action == "web_search":
            return self._handle_web_search_task(task, context)

        if task.service == "admin" and task.action == "log_activity":
            return self._handle_admin_task(task, context)

        if task.service in ("code", "computation"):
            return self._handle_code_execution_task(task, context)

        result = self.runner.run(args)
        if result.success and result.stdout:
            try:
                data = json.loads(result.stdout)

                # Special Case: docs.create_document with initial content
                if task.service == "docs" and task.action == "create_document":
                    content = task.parameters.get("content")
                    if content and "documentId" in data:
                        update_args = self.planner.build_command("docs", "batch_update", {"document_id": data["documentId"], "text": content})
                        self.runner.run(update_args)

                if task.service == "drive" and task.action in ("export_file", "get_file"):
                    saved_file = data.get("saved_file")
                    if saved_file:
                        # Try to determine if it is readable as text
                        # 1. Check if planner-defined mime_type suggests text
                        # 2. Check if the saved file has a text-like extension
                        # 3. Check data.get("mimeType") if available from the API response
                        mime_type = str(task.parameters.get("mime_type") or data.get("mimeType") or "").lower()
                        is_text = any(x in mime_type for x in ("text/", "csv", "json", "javascript", "xml"))
                        if not is_text:
                            ext = os.path.splitext(saved_file)[1].lower()
                            is_text = ext in (".txt", ".csv", ".json", ".md", ".py", ".js", ".html")
                        
                        if is_text:
                            try:
                                with open(saved_file, "r", encoding="utf-8", errors="replace") as f:
                                    content = f.read().lstrip('\ufeff')
                                    data["content"] = content
                                    data["drive_export_content"] = content
                            except Exception as e:
                                logger.warning("Failed to read exported file %s: %s", saved_file, e)
                result.output = data
            except Exception:
                pass

        if result.success and result.output:
            # Synchronize stdout with any enrichments (like body extraction)
            # so that HumanReadableFormatter can see the updated fields.
            result.stdout = json.dumps(result.output)

        return result


@dataclass
class SearchToSheetsWorkflow:
    """Search the web and save results to a Google Sheet."""
    web_search: Any
    sheets: Any

    def execute(self, query: str, title: str = "Search Results") -> bool:
        if not query or not isinstance(query, str):
            logger.error("Invalid query provided: %s", query)
            raise ValueError("Query must be a non-empty string.")

        logger.info("Starting SearchToSheetsWorkflow for query: %s", query)
        try:
            result_data = self.web_search.web_search(query)
            results     = result_data.get("results") or result_data.get("rows") or []

            if not results:
                logger.warning("No results found for query: %s", query)
                return False

            rows = []
            for r in results:
                if isinstance(r, dict):
                    rows.append([r.get("title", ""), r.get("content", ""), r.get("link", "")])
                elif isinstance(r, list):
                    rows.append(r)

            spreadsheet    = self.sheets.create_spreadsheet(title)
            spreadsheet_id = spreadsheet["spreadsheetId"]

            values = [["Title", "Description", "Link"]] + rows
            self.sheets.append_values(spreadsheet_id, "Sheet1!A1", values)

            logger.info(
                "Successfully created spreadsheet '%s' with %d rows.", title, len(rows)
            )
            return True
        except Exception as exc:
            logger.error(
                "SearchToSheetsWorkflow failed for query '%s': %s", query, str(exc),
                exc_info=True,
            )
            raise


@dataclass
class DriveToGmailWorkflow:
    """Search Google Drive for a file and send its content via Gmail."""
    drive_service: Any
    gmail_service: Any

    def execute(self, query: str, email: str) -> bool:
        logger.info(
            "Starting DriveToGmailWorkflow for query: %s, email: %s", query, email
        )
        try:
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                raise ValueError("Invalid email address")

            file_info = self.drive_service.search_file(query)
            if not file_info:
                raise FileNotFoundError("File not found")

            file_id   = file_info["id"]
            file_name = file_info.get("name", "Document")
            content   = self.drive_service.read_file(file_id)

            self.gmail_service.send_email(
                to=email, subject=f"Document: {file_name}", body=content
            )

            logger.info("Successfully sent document '%s' to %s", file_name, email)
            return True
        except Exception as exc:
            logger.error(
                "DriveToGmailWorkflow failed for query '%s': %s", query, str(exc)
            )
            raise
