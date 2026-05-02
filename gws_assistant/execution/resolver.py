import json
import logging
import os
import re
from typing import Any

_UNRESOLVED_MARKER = "___UNRESOLVED_PLACEHOLDER___"
logger = logging.getLogger(__name__)

LEGACY_PLACEHOLDER_MAP = {
    "$last_spreadsheet_id":     "last_spreadsheet_id",
    "$last_spreadsheet_url":    "last_spreadsheet_url",
    "$last_document_id":        "last_document_id",
    "$last_document_url":       "last_document_url",
    "$last_presentation_id":    "last_presentation_id",
    "$last_presentation_url":   "last_presentation_url",
    "$last_form_id":            "last_form_id",
    "$last_form_url":           "last_form_url",
    "$last_meeting_url":        "last_meeting_url",
    "$last_event_url":          "last_event_url",
    "$gmail_message_body": "gmail_message_body_text",
    "$gmail_message_id": "gmail_message_id",
    "$gmail_message_ids":       "gmail_message_ids",
    "$gmail_details_values":    "gmail_details_values",
    "$calendar_events":         "calendar_events",
    "$calendar_items":          "calendar_events",
    "$drive_file_ids":          "drive_file_ids",
    "$last_folder_id":          "last_folder_id",
    "$last_folder_url":         "last_folder_url",
    "$drive_export_content":    "drive_export_content",
    "$drive_export_file":       "drive_export_content",
    "$drive_export_path":       "drive_export_path",
    "$last_export_file_content": "last_export_file_content",
    "$last_export_content":      "last_export_file_content",
    "$last_file_content":        "last_export_file_content",
    "$last_contacts_list":       "last_contacts_list",
    "$contacts_summary_table":   "contacts_summary_table",
    "$contacts_summary_count":   "contacts_summary_count",
    "$last_admin_activities":    "last_admin_activities",
    "$admin_summary_table":      "admin_summary_table",
    "$admin_summary_count":      "admin_summary_count",
    "$last_chat_spaces":         "last_chat_spaces",
    "$chat_summary_table":       "chat_summary_table",
    "$chat_summary_count":       "chat_summary_count",

    # Standardized output contracts mapping (legacy -> new)
    "$drive_summary_values":    "drive_summary_rows",
    "$last_code_stdout":        "code_output",
    "$last_code_result":        "last_code_result",
    "$gmail_summary_values":    "gmail_summary_rows",
    "$web_search_table_values": "search_summary_rows",
    "$web_search_markdown":     "search_summary_table",
    "$web_search_rows":         "search_summary_rows",
    "$web_search_summary":      "search_summary_table",
    "$sheet_email_body":        "sheet_summary_table",
    "$search_rows":             "search_summary_rows",
    "$search_results":          "search_summary_rows",

    # Include the new standardized ones too to resolve if called explicitly
    "$drive_metadata_rows":     "drive_metadata_rows",
    "$drive_file_count":        "drive_file_count",
    "$drive_metadata_table":    "drive_metadata_table",
    "$code_output":             "code_output",
    "$code_exit_code":          "code_exit_code",
    "$code_error":              "code_error",
    "$drive_summary_rows":      "drive_summary_rows",
    "$drive_summary_table":     "drive_summary_table",
    "$drive_summary_count":     "drive_summary_count",
    "$gmail_summary_rows":      "gmail_summary_rows",
    "$gmail_summary_table":     "gmail_summary_table",
    "$gmail_summary_count":     "gmail_summary_count",
    "$search_summary_rows":     "search_summary_rows",
    "$search_summary_table":    "search_summary_table",
    "$search_summary_count":    "search_summary_count",
    "$sheet_summary_rows":      "sheet_summary_rows",
    "$sheet_summary_table":     "sheet_summary_table",
}

class ResolverMixin:
    # Type hints for mypy
    logger: logging.Logger
    config: Any
    runner: Any

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
            if (
                not msg_ids or msg_ids == "{{message_id}}" or msg_ids == _UNRESOLVED_MARKER
            ) and "gmail_message_ids" in context:
                msg_ids = context["gmail_message_ids"]
                self.logger.info(f"Auto-injected {len(msg_ids)} IDs from context for expansion.")

            if isinstance(msg_ids, list) and msg_ids:
                expanded = []
                for i, m_id in enumerate(msg_ids):
                    if not m_id or not isinstance(m_id, str) or m_id == _UNRESOLVED_MARKER:
                        continue
                    new_task = copy.deepcopy(task)
                    new_task.id = f"{task.id}-{i + 1}"
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
                    new_task.id = f"{task.id}-{i + 1}"
                    new_task.parameters["file_id"] = f_id
                    expanded.append(new_task)
                return expanded if expanded else [task]

        if task.service == "drive" and task.action == "delete_file":
            file_ids = resolved_params.get("file_id")
            # If no file_id provided, but we have legacy $drive_file_ids in context, use them!
            if (
                not file_ids or file_ids == "$placeholder" or file_ids == _UNRESOLVED_MARKER
            ) and "drive_file_ids" in context:
                file_ids = context["drive_file_ids"]
                self.logger.info(f"Auto-injected {len(file_ids)} Drive IDs from context for deletion expansion.")

            if isinstance(file_ids, list) and file_ids:
                expanded = []
                for i, f_id in enumerate(file_ids):
                    if not f_id or not isinstance(f_id, str) or f_id == _UNRESOLVED_MARKER:
                        continue
                    new_task = copy.deepcopy(task)
                    new_task.id = f"{task.id}-{i + 1}"
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
        use_repr = task.service == "code" and task.action == "execute"
        task.parameters = self._resolve_placeholders(task.parameters, context, use_repr_for_complex=use_repr)

        # 4. Range auto-fix for Sheets (After resolution)
        rng_after = str(task.parameters.get("range") or "")
        if last_title and "Sheet1" in rng_after:
            quoted_title = f"'{last_title}'" if (" " in last_title and not last_title.startswith("'")) else last_title
            task.parameters["range"] = rng_after.replace("Sheet1", quoted_title)
            self.logger.info(f"Range auto-fixed (Post): {rng_after} -> {task.parameters['range']}")

        # 5. Last-resort ID fallbacks for common missing parameters
        # If a required ID is still missing or remains a placeholder after resolution,
        # try to pull the most recent matching ID from the global context.
        if task.service == "sheets":
            s_id = str(task.parameters.get("spreadsheet_id") or "")
            if (not s_id or s_id.startswith("{{") or s_id == _UNRESOLVED_MARKER) and context.get("last_spreadsheet_id"):
                task.parameters["spreadsheet_id"] = context["last_spreadsheet_id"]

        if task.service == "docs":
            d_id = str(task.parameters.get("document_id") or "")
            if (not d_id or d_id.startswith("{{") or d_id == _UNRESOLVED_MARKER) and context.get("last_document_id"):
                task.parameters["document_id"] = context["last_document_id"]

        if task.service == "drive":
            f_id = str(task.parameters.get("file_id") or "")
            if not f_id or f_id.startswith("{{") or f_id == _UNRESOLVED_MARKER:
                if context.get("last_file_id"):
                    task.parameters["file_id"] = context["last_file_id"]
                elif context.get("last_document_id"):
                    task.parameters["file_id"] = context["last_document_id"]
                elif context.get("last_presentation_id"):
                    task.parameters["file_id"] = context["last_presentation_id"]
                elif context.get("last_form_id"):
                    task.parameters["file_id"] = context["last_form_id"]

        if task.service == "slides":
            p_id = str(task.parameters.get("presentation_id") or "")
            if (not p_id or p_id.startswith("{{") or p_id == _UNRESOLVED_MARKER) and context.get("last_presentation_id"):
                task.parameters["presentation_id"] = context["last_presentation_id"]

        if task.service == "forms":
            f_id = str(task.parameters.get("form_id") or "")
            if (not f_id or f_id.startswith("{{") or f_id == _UNRESOLVED_MARKER) and context.get("last_form_id"):
                task.parameters["form_id"] = context["last_form_id"]

        if task.service == "sheets" and task.action == "create_spreadsheet":
            if not task.parameters.get("title"):
                # The default spreadsheet title is configurable via the
                # ``DEFAULT_SPREADSHEET_TITLE`` env var so test environments
                # (and per-deployment naming conventions) don't have to patch
                # source code.
                default_title = os.getenv("DEFAULT_SPREADSHEET_TITLE") or "GWS Agent Spreadsheet"
                task.parameters["title"] = default_title
                self.logger.info(f"Added default spreadsheet title: {default_title}")

        # 4. Strict email recipient enforcement (Security Policy)
        if task.service == "gmail" and task.action == "send_message":
            if self.config and self.config.default_recipient_email:
                target = self.config.default_recipient_email
                current = task.parameters.get("to_email")
                # Force override to target if set and different (Security Policy)
                if target and current != target:
                    self.logger.warning(
                        f"SECURITY: Redirecting email recipient from '{current}' to forced default '{target}'"
                    )
                    task.parameters["to_email"] = target

        return task

    def _resolve_placeholders(self, val: Any, context: dict, use_repr_for_complex: bool = False, depth: int = 0) -> Any:
        """Recursively resolve $placeholder and {task-N} tokens from context.

        The depth guard prevents infinite recursion when resolved values themselves
        contain brace/dollar characters (e.g. JSON tool output, base64 content).
        Depth is incremented only when descending into dict/list structures, NOT
        when substituting a value from context — that substitution is always final.
        """
        if depth > 15:
            # Depth exceeded — return as-is to prevent stack overflow.
            self.logger.warning("_resolve_placeholders: max depth reached for val=%r", repr(val)[:200])
            return val

        # Additional safety: check for circular references in context
        if isinstance(val, dict) or isinstance(val, list):
            # Use id() to detect if we've seen this object before
            if not hasattr(self, '_resolve_cache'):
                self._resolve_cache: dict[int, Any] = {}
            obj_id = id(val)
            if obj_id in self._resolve_cache:
                self.logger.warning("_resolve_placeholders: circular reference detected for obj_id=%d, returning memoized clone", obj_id)
                return self._resolve_cache[obj_id]
            # Create an empty clone and store it in the cache before recursion
            clone = {} if isinstance(val, dict) else []
            self._resolve_cache[obj_id] = clone
            try:
                result = self._resolve_placeholders_impl(val, context, use_repr_for_complex, depth, clone=clone)
                return result
            finally:
                del self._resolve_cache[obj_id]
        else:
            return self._resolve_placeholders_impl(val, context, use_repr_for_complex, depth)

    def _resolve_placeholders_impl(self, val: Any, context: dict, use_repr_for_complex: bool = False, depth: int = 0, clone: Any = None) -> Any:
        if isinstance(val, str):
            if "{" not in val and "$" not in val:
                return val

            logger.debug(f"DEBUG: resolving '{val}' with context keys: {list(context.keys())}")
            # 1. Legacy $ placeholders
            results_map = context.get("task_results", {})
            logger.debug(f"DEBUG: results_map keys: {list(results_map.keys())}")

            # Optimized: check if the entire string is a single legacy placeholder (type-preserving)
            if val in LEGACY_PLACEHOLDER_MAP and LEGACY_PLACEHOLDER_MAP[val] in context:
                res = context[LEGACY_PLACEHOLDER_MAP[val]]
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
                if "task-" in potential_path.lower() or potential_path in results_map or potential_path.startswith(":"):
                    path = potential_path
                elif potential_path in context:
                    # Also resolve plain context keys like {last_code_result}
                    path = potential_path
            elif stripped.startswith("$task-"):
                path = stripped[1:].strip()

            def resolve_shorthand(shorthand_path):
                shorthand_tokens = [t for t in re.split(r"[._]", shorthand_path.lower()) if t]
                for key, val_item in reversed(list(results_map.items())):
                    # Skip numeric keys and task-N keys for shorthand matching to avoid noise
                    if re.match(r"^task-\d+$|^\d+$", str(key)):
                        continue

                    key_tokens = [t for t in re.split(r"[._]", str(key).lower()) if t]
                    matches = 0
                    for st in shorthand_tokens:
                        # Check exact, plural, or synonyms
                        is_match = any(
                            st == kt
                            or st + "s" == kt
                            or kt + "s" == st
                            or (st == "sheet" and kt == "spreadsheet")
                            or (st == "doc" and kt == "document")
                            or (st == "msg" and kt == "message")
                            or (st == "mail" and kt == "message")
                            for kt in key_tokens
                        )
                        if is_match:
                            matches += 1

                    if matches > 0 and matches >= len(shorthand_tokens):
                        # If we have a perfect or better match, take it.
                        # Since we are reversed, this is the most recent one.
                        return val_item
                return None

            if path:
                logger.debug(f"DEBUG: Found path='{path}'")
                if path in context:
                    res = context[path]
                    if res is not None:
                        return res

                resolved = None
                if path.startswith(":"):
                    resolved = resolve_shorthand(path[1:])
                else:
                    resolved = self._get_value_by_path(results_map, path)

                    # Fallback: if {{task-N.key}} failed, try to find 'key' in ANY task.
                    # This handles LLM off-by-one errors in task indexing.
                    if resolved is None and "." in path:
                        parts = path.split(".")
                        if parts[0].startswith("task-") or parts[0].isdigit():
                            key_to_find = parts[-1]
                            self.logger.info(f"RESOLVER: '{path}' failed. Trying fallback for '{key_to_find}'...")
                            resolved = resolve_shorthand(key_to_find)

                    if resolved is None:
                         keys_summary = {k: type(v).__name__ for k, v in results_map.items()}
                         self.logger.warning(f"RESOLVER: Failed to resolve '{val}'. Path: '{path}'. Available keys/types: {keys_summary}")

                # Smart unwrap:
                # 1. If the resolved value is a dict with 'content', promote the content.
                if isinstance(resolved, dict) and "content" in resolved:
                    resolved = resolved["content"]

                # 2. If we resolved to a list, but we are a single-token placeholder
                # (e.g. {{task-1.id}}), pick the first item.
                singular_suffixes = [
                    ".id",
                    ".name",
                    ".url",
                    ".title",
                    ".email",
                    ".spreadsheet_id",
                    ".document_id",
                    ".spreadsheetId",
                    ".documentId",
                ]
                if isinstance(resolved, list) and resolved and any(path.endswith(s) for s in singular_suffixes):
                    self.logger.debug(f"DEBUG: Smart-unwrapping list result for '{path}' to first item.")
                    # We have a list. Check if we need to do the folder heuristic.
                    # Since resolved is likely just strings here (e.g. ['folder_id', 'doc_id']),
                    # we can't easily check mime types unless we look at the original objects.
                    # Let's get the original objects using a parent path.
                    parent_path = path.rsplit('.', 1)[0]
                    parent_objects = self._get_value_by_path(results_map, parent_path)

                    picked = resolved[0]
                    if isinstance(parent_objects, list) and len(parent_objects) == len(resolved):
                        for i, obj in enumerate(parent_objects):
                            if isinstance(obj, dict) and obj.get("mimeType") != "application/vnd.google-apps.folder":
                                picked = resolved[i]
                                break
                    resolved = picked

                if resolved is not None:
                    return resolved

                self.logger.warning(
                    f"Placeholder '{path}' resolved to None in context. "
                    f"Available context keys: {list(context.keys())}"
                )
                return _UNRESOLVED_MARKER

            # 3. Partial string replacement
            if "$" in val:
                for placeholder, ctx_key in LEGACY_PLACEHOLDER_MAP.items():
                    if placeholder in val and ctx_key in context:
                        res = context[ctx_key]
                        if res is None:
                            val = val.replace(placeholder, _UNRESOLVED_MARKER)
                        elif use_repr_for_complex and isinstance(res, (dict, list, str)):
                            val = val.replace(placeholder, repr(res))
                        else:
                            val = val.replace(placeholder, str(res))

            def replace_match(match):
                # match.group(1) is {{...}}, group(2) is {...}, group(3) is $task-...
                p = (match.group(1) or match.group(2) or match.group(3) or "").strip()
                if p.startswith("$"):
                    p = p[1:]  # strip $ from $task-N

                res = context.get(p)
                if res is None:
                    # Semantic/Shorthand resolution: if it starts with a colon like :get_message
                    if p.startswith(":"):
                        shorthand = p[1:].lower().replace("_", "")
                        # Try to find a match in results_map keys
                        for key, val_item in results_map.items():
                            norm_key = str(key).lower().replace("_", "")
                            # Direct match or containment
                            if shorthand == norm_key or norm_key in shorthand or shorthand in norm_key:
                                res = val_item
                                break
                    else:
                        res = self._get_value_by_path(results_map, p)

                if p in context and context[p] is None:
                    return ""

                if res is not None:
                    # Smart unwrap: if the resolved value is a dict with 'content',
                    # promote the content.
                    if isinstance(res, dict) and "content" in res:
                        res = res["content"]

                    if use_repr_for_complex:
                        if "injected_vars" not in context:
                            context["injected_vars"] = []
                        idx = len(context["injected_vars"])
                        context["injected_vars"].append(res)
                        return f"injected_vars[{idx}]"
                    elif isinstance(res, (dict, list)):
                        return json.dumps(res)
                    return str(res)

                # Safety: Only return _UNRESOLVED_MARKER for tokens that are obviously intended as placeholders
                # (double-braces, $task-N, or tokens containing 'task-' or known result keys).
                # This prevents accidental corruption of JSON payloads containing single braces.
                is_explicit = bool(match.group(1) or match.group(3))
                is_task_token = bool(
                    p and ("task-" in p.lower() or any(k in p for k in results_map) or p.startswith(":"))
                )

                if is_explicit or is_task_token:
                    return _UNRESOLVED_MARKER
                return match.group(0)

            # 3. Large Artifact Guard (Issue 14)
            # If the string is very long, skip regex scanning if it lacks placeholder indicators.
            if len(val) > 5000:
                if not ("{{" in val or "$task-" in val or "{task-" in val or "{:" in val):
                    self.logger.debug(f"DEBUG: Skipping regex scan for large string (len={len(val)})")
                    return val

            # 4. Partial string replacement with regex
            # Supports {{...}}, {task-...}, {semantic_task...}, or $task-N
            # Added ':' to support shorthand like {{:get_message}}
            val = re.sub(
                r"\{\{([\w\-\.\[\]:]+)\}\}|\{([\w\-\.\[\]:]+)\}|(\$task-\d+(?:\.[\w\-]+(?:\[\d+\])?)*)",
                replace_match,
                val,
            )
            return val

        elif isinstance(val, list):
            # If the list contains a single placeholder string, and that placeholder
            # resolves to a list, return the resolved list directly to avoid double-wrapping.
            if len(val) == 1 and isinstance(val[0], str) and ("{" in val[0] or "$" in val[0]):
                resolved_item = self._resolve_placeholders(val[0], context, use_repr_for_complex, depth + 1)
                if isinstance(resolved_item, list):
                    self.logger.debug(f"DEBUG: Flattening single-item list placeholder from {val} to {resolved_item}")
                    return resolved_item

            if clone is not None:
                # Use the memoized clone for circular reference handling
                for i, item in enumerate(val):
                    clone.append(self._resolve_placeholders(item, context, use_repr_for_complex, depth + 1))
                return clone
            return [self._resolve_placeholders(item, context, use_repr_for_complex, depth + 1) for item in val]
        elif isinstance(val, dict):
            if clone is not None:
                # Use the memoized clone for circular reference handling
                for k, v in val.items():
                    clone[k] = self._resolve_placeholders(v, context, use_repr_for_complex, depth + 1)
                return clone
            return {k: self._resolve_placeholders(v, context, use_repr_for_complex, depth + 1) for k, v in val.items()}
        return val

    def _get_value_by_path(self, data: dict, path: str) -> Any:
        """Evaluate a path like 'task-1[0].id' or 'drive.list_files[0].id'."""
        self.logger.debug(f"DEBUG: evaluating path '{path}' against results keys: {list(data.keys())}")

        # 1. Try exact match first
        if path in data:
            return data[path]

        # 2. Split path into tokens, handling dots and brackets
        tokens = re.findall(r"[^.\[\]]+|\[\d+\]", path)
        if not tokens:
            return None

        curr: Any = data
        for i, token in enumerate(tokens):
            if token.startswith("["):
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
        """Inject artifact URLs (Doc/Sheet/Slide/Form/Meet) from context into email body."""
        doc_url = context.get("last_document_url", "")
        sheet_url = context.get("last_spreadsheet_url", "")
        slide_url = context.get("last_presentation_url", "")
        form_url = context.get("last_form_url", "")
        meet_url = context.get("last_meeting_url", "")

        if not any([doc_url, sheet_url, slide_url, form_url, meet_url]):
            return body

        links = []
        if doc_url:
            links.append(f"Google Doc: {doc_url}")
        if sheet_url:
            links.append(f"Google Sheet: {sheet_url}")
        if slide_url:
            links.append(f"Google Slides: {slide_url}")
        if form_url:
            links.append(f"Google Form: {form_url}")
        if meet_url:
            links.append(f"Google Meet: {meet_url}")

        final_body = f"{body}\n\n" + "\n".join(links)
        self.logger.info(
            "Generated email body with artifact links. Body length: %s, Links count: %s", len(final_body), len(links)
        )
        return final_body
