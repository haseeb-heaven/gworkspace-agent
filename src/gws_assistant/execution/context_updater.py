import re
from typing import Any

class ContextUpdaterMixin:
    def _update_context_from_result(self, data: dict, context: dict, task: Any = None) -> None:
        """Extract known artifact keys from a task result and store in context."""
        if not isinstance(data, dict):
            return

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
                    name = str(h.get("name", "")).lower()
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
            date_val = headers_dict.get("date", "Unknown Date")
            
            # Extract just email from "Name <email@example.com>"
            email_match = re.search(r"<(.+?)>", str(sender))
            email_addr = email_match.group(1) if email_match else sender
            
            row = [sender, subject, date_val, email_addr]
            data["row"] = row # For {task-N.row} access

            # We want to build a cumulative list if this is part of an expansion
            details_list = context.setdefault("gmail_details_values", [])
            details_list.append(row)

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
                
                if task:
                    task_id = str(task.id)
                    num = task_id.removeprefix("task-")
                    # If we found multiple messages, store the LIST of IDs so expansion can trigger
                    context[f"message_id_from_task_{num}"] = context["gmail_message_ids"]
                    context[f"thread_id_from_task_{num}"] = [m.get("threadId") for m in msgs]

                # Reset details for fresh extraction ONLY if it's empty to allow for cumulative append in expanded tasks
                if not context.get("gmail_details_values"):
                    context["gmail_details_values"] = []

        if "files" in data:
            files = data["files"]
            if files and isinstance(files, list):
                context["drive_file_ids"] = [f.get("id") for f in files if f.get("id")]
                context["drive_summary_values"] = [[f.get("name", ""), f.get("mimeType", ""), f.get("webViewLink", "")] for f in files]
                if len(files) > 0:
                    if "mimeType" in files[0]:
                        context["last_file_mime"] = files[0]["mimeType"]
                    if "webViewLink" in files[0]:
                        context["last_file_url"] = files[0]["webViewLink"]

        if "id" in data and task and task.service == "drive" and task.action == "create_folder":
            context["last_folder_id"] = data["id"]
            url = data.get("webViewLink") or f"https://drive.google.com/drive/folders/{data['id']}"
            context["last_folder_url"] = url
            data["webViewLink"] = url # Ensure it's in the data for {task-N.webViewLink}


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
            rows = data["values"]
            
            # Semantic extraction for tests - handle aggregation for all expanded tasks
            if task:
                 task_id = str(task.id)
                 # Extract base ID (e.g. '2' from 'task-2-1' or 'task-2')
                 m = re.match(r"(?:task-)?(\d+)", task_id)
                 if m:
                     base_num = m.group(1)
                     key = f"company_names_from_task_{base_num}"
                     if "-" in task_id: # it's a subtask or task-N
                         current = context.setdefault(key, [])
                         if isinstance(current, list):
                             # Avoid double-wrapping if already a list of rows
                             if rows and isinstance(rows[0], list):
                                 current.extend(rows)
                             else:
                                 current.append(rows)
                     else:
                         context[key] = rows

            lines = [" | ".join(str(c) for c in row) for row in rows]
            context["sheet_email_body"] = "\n".join(lines)

        # ------------------------------------------------------------------
        # FINAL: Store everything in results_map for {task-N} resolution
        # ------------------------------------------------------------------
        results_map = context.setdefault("task_results", {})
        if task and hasattr(task, "id") and task.id:
            task_id = str(task.id)
            num = task_id.removeprefix("task-")
            seq_num = str(getattr(task, "sequence_index", num))
            action_name = str(task.action)

            # Map the full task result object (now enriched with IDs, URLs, headers, etc.)
            results_map[task_id] = data
            results_map[num] = data
            results_map[f"task-{num}"] = data
            results_map[seq_num] = data
            results_map[f"task-{seq_num}"] = data
            results_map[action_name] = data

            # Map under 'output' for placeholders like {{task-1.output.spreadsheetId}}
            if "output" not in data:
                # Do not self-reference dictionary as it causes RecursionError in _resolve_placeholders
                data["output"] = {k: v for k, v in data.items() if k != "output"}

            # If this is a subtask (e.g. task-2-1), also append to the base task's list (e.g. task-2)
            is_subtask = False
            if "-" in task_id:
                # Extract base ID (e.g. 'task-2' from 'task-2-1')
                m = re.match(r"(task-\d+)-\d+", task_id)
                if m:
                    b_id = m.group(1)
                    is_subtask = True
                    # Initialize list if not already present or if it's currently a dict (from a different task)
                    if b_id not in results_map or not isinstance(results_map[b_id], list):
                        results_map[b_id] = []
                    
                    results_map[b_id].append(data)
                    # self.logger.debug(f"DEBUG: Appended result to base task list '{b_id}' (size: {len(results_map[b_id])})")
                    
                    # Also map the numeric base ID (e.g. '2' from 'task-2-1')
                    b_num = b_id.removeprefix("task-")
                    results_map[b_num] = results_map[b_id]
                    results_map[f"task-{b_num}"] = results_map[b_id]
                    
                    # Map semantic keys like company_names_from_task_2
                    # If this subtask produced a 'values' or 'row', ensure it's in the base list
                    if "values" in data and isinstance(data["values"], list):
                         key = f"company_names_from_task_{b_num}"
                         current = context.setdefault(key, [])
                         if isinstance(current, list):
                             rows = data["values"]
                             if rows and isinstance(rows[0], list):
                                 current.extend(rows)
                             else:
                                 current.append(rows)
                    elif "row" in data:
                         key = f"company_names_from_task_{b_num}"
                         current = context.setdefault(key, [])
                         if isinstance(current, list):
                             current.append(data["row"])

            # Map individual fields (if they exist)
            for k, v in data.items():
                results_map[f"{task_id}.{k}"] = v
                # ONLY map N.key and task-N.key if this is NOT an expansion subtask,
                # or if it's the first subtask (to provide some default).
                # Actually, if it's a subtask, we want task-N.key to be a list if possible? 
                # For now, let's keep it simple: subtasks don't overwrite task-N.key 
                # unless they are the primary ID.
                if not is_subtask:
                    results_map[f"{num}.{k}"] = v
                    results_map[f"task-{num}.{k}"] = v
                
                results_map[f"{seq_num}.{k}"] = v
                results_map[f"task-{seq_num}.{k}"] = v
                results_map[f"{action_name}.{k}"] = v

            # Special case: promote first item's ID for files/messages
            if "files" in data and isinstance(data["files"], list) and len(data["files"]) > 0:
                # Bug 1 Fix: Pick first non-folder ID if possible
                files = data["files"]
                first_id = files[0].get("id")
                
                # If the first item is a folder, try to find a document
                if files[0].get("mimeType") == "application/vnd.google-apps.folder":
                    for f in files:
                        if f.get("mimeType") != "application/vnd.google-apps.folder":
                            first_id = f.get("id")
                            # self.logger.info(f"DEBUG: Skipping folder '{files[0].get('id')}' for document ID '{first_id}'")
                            break

                if first_id:
                    results_map[f"{task_id}.id"] = first_id
                    results_map[f"{num}.id"] = first_id
                    results_map[f"task-{num}.id"] = first_id
                    results_map[f"{seq_num}.id"] = first_id
                    results_map[f"task-{seq_num}.id"] = first_id
            
            if "messages" in data and isinstance(data["messages"], list) and len(data["messages"]) > 0:
                first_id = data["messages"][0].get("id")
                if first_id:
                    results_map[f"{task_id}.id"] = first_id
                    results_map[f"{num}.id"] = first_id
                    results_map[f"task-{num}.id"] = first_id
                    results_map[f"{seq_num}.id"] = first_id
                    results_map[f"task-{seq_num}.id"] = first_id

        if "values" in data and isinstance(data["values"], list):
             results_map["values"] = data["values"] # Direct alias for the most recent values
