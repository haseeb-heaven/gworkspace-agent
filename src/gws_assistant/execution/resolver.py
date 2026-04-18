import json
import logging
import re
from typing import Any

_UNRESOLVED_MARKER = "___UNRESOLVED_PLACEHOLDER___"
logger = logging.getLogger(__name__)

class ResolverMixin:
    def _expand_task(self, task: Any, context: dict) -> list:
        """Expand a single task into a list of executable tasks.
        Example: gmail.get_message with message_id=['id1', 'id2']
        """
        # Resolve placeholders in parameters FIRST to see if we have a list
        import copy
        resolved_params = self._resolve_placeholders(copy.deepcopy(task.parameters), context)

        if task.service == "gmail" and task.action == "get_message":
            msg_ids = resolved_params.get("message_id")
            # If no message_id provided, but we have legacy $gmail_message_ids in context, use them!
            if (not msg_ids or msg_ids == "{{message_id}}" or msg_ids == _UNRESOLVED_MARKER) and "gmail_message_ids" in context:
                 msg_ids = context["gmail_message_ids"]
                 self.logger.info(f"Auto-injected {len(msg_ids)} IDs from context for expansion.")

            if isinstance(msg_ids, list) and msg_ids:
                expanded = []
                for i, m_id in enumerate(msg_ids):
                    if not m_id or not isinstance(m_id, str) or m_id == _UNRESOLVED_MARKER:
                        continue
                    new_task = copy.deepcopy(task)
                    new_task.id = f"{task.id}-{i+1}"
                    new_task.parameters["message_id"] = m_id
                    expanded.append(new_task)
                return expanded if expanded else [task]

        if task.service == "drive" and task.action == "move_file":
            file_ids = resolved_params.get("file_id")
            if isinstance(file_ids, list) and file_ids:
                expanded = []
                for i, f_id in enumerate(file_ids):
                    if not f_id or not isinstance(f_id, str) or f_id == _UNRESOLVED_MARKER:
                        continue
                    new_task = copy.deepcopy(task)
                    new_task.id = f"{task.id}-{i+1}"
                    new_task.parameters["file_id"] = f_id
                    expanded.append(new_task)
                return expanded if expanded else [task]

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

        # 4. Strict email recipient enforcement (Security Policy)
        if task.service == "gmail" and task.action == "send_message":
            if self.config and self.config.default_recipient_email:
                target = self.config.default_recipient_email
                current = task.parameters.get("to_email")
                # Force override everything to default_recipient_email
                if current != target:
                    self.logger.warning(f"SECURITY: Redirecting email recipient from '{current}' to forced default '{target}'")
                    task.parameters["to_email"] = target

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
                    return ""
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
                
                # Smart unwrap: 
                # 1. If the resolved value is a dict with 'content', promote the content.
                if isinstance(resolved, dict) and "content" in resolved:
                    resolved = resolved["content"]

                # 2. If we resolved to a list, but we are a single-token placeholder 
                # (e.g. {{task-1.id}}), pick the first item.
                singular_suffixes = ['.id', '.name', '.url', '.title', '.email', '.spreadsheet_id', '.document_id']
                if isinstance(resolved, list) and resolved and any(path.endswith(s) for s in singular_suffixes):
                    self.logger.debug(f"DEBUG: Smart-unwrapping list result for '{path}' to first item.")
                    resolved = resolved[0]

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

                res = context.get(p)
                if res is None:
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
                
                # If we explicitly found a None value in context, return empty string
                if res is None and p in context:
                    return ""

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

        # 2. Split path into tokens, handling dots and brackets
        tokens = re.findall(r'[^.\[\]]+|\[\d+\]', path)
        if not tokens:
            return None

        curr: Any = data
        for i, token in enumerate(tokens):
            if token.startswith('['):
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
                    return None
            else:
                # Key access
                if isinstance(curr, dict):
                    if token in curr:
                        curr = curr[token]
                    else:
                        # Auto-unwrap: if current level is a dict and we have a list inside,
                        # and the token exists in the list elements, we can auto-unwrap.
                        unwrapped = False
                        for list_key in ["files", "messages", "items", "events", "values", "threads"]:
                            if list_key in curr and isinstance(curr[list_key], list) and curr[list_key]:
                                if isinstance(curr[list_key][0], dict) and token in curr[list_key][0]:
                                    curr = [item.get(token) for item in curr[list_key]]
                                    unwrapped = True
                                    break
                        if not unwrapped:
                            curr = None
                elif isinstance(curr, list):
                    # Map the token across the list elements
                    curr = [item.get(token) if isinstance(item, dict) else None for item in curr]
                    # Filter out None if some items don't have it? 
                    # Usually we want to keep the list structure.
                else:
                    return None

            if curr is None:
                return None

        return curr

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
