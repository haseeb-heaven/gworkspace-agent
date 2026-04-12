"""Action validation and command planning."""

from __future__ import annotations

import base64
import email as email_lib
import email.mime.application
import email.mime.multipart
import email.mime.text
import json
import os
import re
import tempfile
from typing import Any

from .exceptions import ValidationError
from .models import ActionSpec, ParameterSpec
from .service_catalog import SERVICES, normalize_service, supported_services

# ---------------------------------------------------------------------------
# Drive query helpers
# ---------------------------------------------------------------------------

# Services that are recognised by the LLM but have no real CLI backing.
_UNSUPPORTED_STUB_SERVICES = frozenset({"admin", "analytics", "bigquery"})

# Fix #1 — regex that matches an ALREADY-VALID Drive API v3 operator clause.
# If a clause already starts with a known operator we must NOT rewrite it.
_DRIVE_VALID_CLAUSE_RE = re.compile(
    r"""^\s*(?:
        (?:name|fullText)\s+contains\s+'[^']*'         # name contains '...'
      | mimeType\s*=\s*'[^']*'                          # mimeType='...'
      | (?:trashed|starred|sharedWithMe)\s*=\s*(?:true|false)
      | (?:parents|in)\s+in\s+'[^']*'
      | (?:modifiedTime|createdTime|viewedByMeTime)\s*[<>=!]+\s*\S+
    )\s*$""",
    re.IGNORECASE | re.VERBOSE,
)

# Fix #2 — matches every malformed mimeType variant the LLM can produce:
#   mimeType="..."  mimeType='...'  mimeType:...  mimeType = "..."
_MIME_EQ_RE = re.compile(
    r"""mimeType\s*[=:]\s*["']?\s*([^"'\s,)]+)\s*["']?""",
    re.IGNORECASE,
)

# Logical conjunction tokens used as split boundaries in Fix #3.
_CONJUNCTION_RE = re.compile(r"\b(and|or)\b", re.IGNORECASE)

# Fix #5 — detects whether a raw text token contains any Drive operator word.
_DRIVE_OPS_RE = re.compile(
    r"\b(contains|and|or|not|in|parents|mimeType|name|fullText"
    r"|trashed|starred|sharedWithMe|modifiedTime|createdTime"
    r"|viewedByMeTime|quotaBytesUsed|properties|appProperties|visibility)\b",
    re.IGNORECASE,
)

# Matches a value wrapped only in double-quotes with no operator, e.g. "foo bar"
_BARE_DQUOTE_RE = re.compile(r'^"([^"]+)"$')


def _escape(value: str) -> str:
    """Fix #8 — escape single quotes inside a Drive query value."""
    return value.replace("'", "\\'")


def _is_valid_clause(clause: str) -> bool:
    """Fix #6 — return True if clause is already a valid Drive API v3 expression."""
    return bool(_DRIVE_VALID_CLAUSE_RE.match(clause.strip()))


def _tokenize_raw_query(raw: str) -> tuple[list[str], list[str]]:
    """Fix #3 — split raw query into (clauses, conjunctions) using token-based parsing.

    Splits on bare 'and'/'or' words that are NOT embedded inside quoted strings.
    Returns parallel lists; len(conjunctions) == len(clauses) - 1.
    """
    # First handle quoted substrings so we don't split inside them.
    parts: list[str] = []
    conjunctions: list[str] = []
    # Walk through splitting on conjunction tokens that appear outside quotes.
    buffer = ""
    i = 0
    in_single = False
    in_double = False
    while i < len(raw):
        ch = raw[i]
        if ch == "'" and not in_double:
            in_single = not in_single
            buffer += ch
        elif ch == '"' and not in_single:
            in_double = not in_double
            buffer += ch
        elif not in_single and not in_double:
            # Try to match a conjunction keyword at this position
            m = _CONJUNCTION_RE.match(raw, i)
            if m:
                if buffer.strip():
                    parts.append(buffer.strip())
                conjunctions.append(m.group(1).lower())
                buffer = ""
                i = m.end()
                continue
            else:
                buffer += ch
        else:
            buffer += ch
        i += 1
    if buffer.strip():
        parts.append(buffer.strip())
    return parts, conjunctions


def _classify_and_fix_clause(clause: str) -> list[str]:
    """Fix #4 & #5 — classify a single clause and return one or more valid Drive clauses.

    A raw LLM clause may itself contain multiple semantic components jammed
    together without a conjunction, e.g.:
        "CcaaS - AI Product" mimeType="application/vnd.google-apps.document"
    These are split into separate fixed clauses and the caller injects 'and'.
    """
    clause = clause.strip()
    if not clause:
        return []

    # Fix #6 — already valid, pass through untouched.
    if _is_valid_clause(clause):
        return [clause]

    # Fix #2 — extract mimeType component first (may be embedded in a larger string).
    mime_clauses: list[str] = []
    def _collect_mime(m: re.Match) -> str:
        value = m.group(1).strip().strip("\"'")
        mime_clauses.append(f"mimeType='{_escape(value)}'")
        return ""  # remove from remainder

    remainder = _MIME_EQ_RE.sub(_collect_mime, clause).strip()

    # remainder is now whatever was left after stripping out mimeType=...
    text_clauses: list[str] = []
    if remainder:
        # Strip surrounding double-quotes from bare quoted tokens.
        dq = _BARE_DQUOTE_RE.match(remainder)
        if dq:
            remainder = dq.group(1).strip()

        # Fix #5 — if remainder still has no Drive operator it is bare text.
        if not _DRIVE_OPS_RE.search(remainder):
            safe = _escape(remainder.strip("\"' "))
            if safe:
                text_clauses.append(f"name contains '{safe}'")
        else:
            # Remainder already has an operator — keep as-is (e.g. "name contains 'x'")
            if _is_valid_clause(remainder):
                text_clauses.append(remainder)
            else:
                safe = _escape(remainder.strip("\"' "))
                if safe:
                    text_clauses.append(f"name contains '{safe}'")

    return text_clauses + mime_clauses


def _sanitize_drive_query(raw: str) -> str:
    """Normalise an LLM-generated Drive query string to valid Drive API v3 syntax.

    Handles all observed failure modes:
      "CcaaS - AI Product" mimeType="application/vnd.google-apps.document"
      CcaaS - AI Product mimeType:application/vnd.google-apps.document
      CcaaS - AI Product

    All become:
      name contains 'CcaaS - AI Product' and mimeType='application/vnd.google-apps.document'
    """
    q = raw.strip()
    if not q:
        return q

    # Fix #3 — token-based split preserving logical operators.
    raw_clauses, conjunctions = _tokenize_raw_query(q)

    # Fix #4/#5 — classify each clause; a single raw clause may expand to multiple.
    fixed_groups: list[list[str]] = [_classify_and_fix_clause(c) for c in raw_clauses]

    # Flatten with explicit 'and' injected between sub-clauses from the same group
    # (Fix #4) and preserve original conjunctions between groups.
    all_clauses: list[str] = []
    all_conjs: list[str] = []

    for g_idx, group in enumerate(fixed_groups):
        for c_idx, clause in enumerate(group):
            all_clauses.append(clause)
            if c_idx < len(group) - 1:
                # Inject explicit 'and' between components from the same raw clause
                all_conjs.append("and")
        if g_idx < len(conjunctions):
            # Preserve the original conjunction between groups
            all_conjs.append(conjunctions[g_idx])

    if not all_clauses:
        # Ultimate fallback for completely empty result
        safe = _escape(q.strip("\"' "))
        return f"name contains '{safe}'"

    # Fix #7 — final fallback only if the assembled result has NO Drive operator.
    result_parts: list[str] = []
    for idx, clause in enumerate(all_clauses):
        result_parts.append(clause)
        if idx < len(all_conjs):
            result_parts.append(all_conjs[idx])
    result = " ".join(result_parts).strip()

    if result and not _DRIVE_OPS_RE.search(result):
        # Still completely bare — wrap as name contains
        safe = _escape(result.strip("\"' "))
        result = f"name contains '{safe}'"

    return result


class CommandPlanner:
    """Validates service/action and builds gws command arguments."""

    def list_services(self) -> list[str]:
        return supported_services()

    def list_actions(self, service: str) -> list[ActionSpec]:
        service_key = normalize_service(service)
        if not service_key or service_key not in SERVICES:
            raise ValidationError(f"Unsupported service: {service}")
        return list(SERVICES[service_key].actions.values())

    def ensure_service(self, service: str | None) -> str:
        normalized = normalize_service(service)
        if not normalized:
            raise ValidationError(
                f"Unsupported or missing service. Supported services: {', '.join(self.list_services())}"
            )
        return normalized

    def ensure_action(self, service: str, action: str | None) -> str:
        if not action:
            raise ValidationError("Action is required.")
        service_key = self.ensure_service(service)
        if action not in SERVICES[service_key].actions:
            available = ", ".join(sorted(SERVICES[service_key].actions.keys()))
            raise ValidationError(f"Unsupported action '{action}' for {service_key}. Available: {available}")
        return action

    def required_parameters(self, service: str, action: str) -> tuple[ParameterSpec, ...]:
        service_key = self.ensure_service(service)
        action_key = self.ensure_action(service_key, action)
        return SERVICES[service_key].actions[action_key].parameters

    def build_command(self, service: str, action: str, parameters: dict[str, Any]) -> list[str]:
        if str(service).lower() in _UNSUPPORTED_STUB_SERVICES:
            raise UnsupportedServiceError(
                f"No command builder for service: {service}"
            )

        service_key = self.ensure_service(service)
        action_key = self.ensure_action(service_key, action)
        params = parameters or {}

        if service_key == "drive":
            return self._build_drive_command(action_key, params)
        if service_key == "sheets":
            return self._build_sheets_command(action_key, params)
        if service_key == "gmail":
            return self._build_gmail_command(action_key, params)
        if service_key == "calendar":
            return self._build_calendar_command(action_key, params)
        if service_key == "docs":
            return self._build_docs_command(action_key, params)
        if service_key == "slides":
            return self._build_slides_command(action_key, params)
        if service_key == "contacts":
            return self._build_contacts_command(action_key, params)
        if service_key == "chat":
            return self._build_chat_command(action_key, params)
        if service_key == "meet":
            return self._build_meet_command(action_key, params)
        raise ValidationError(f"No command builder for service: {service_key}")

    def _build_drive_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_files":
            page_size = self._safe_positive_int(params.get("page_size"), default=10)
            raw_query = str(params.get("q") or "").strip()
            request_params: dict[str, Any] = {
                "pageSize": page_size,
                "fields": "files(id,name,mimeType,modifiedTime,webViewLink,owners(displayName,emailAddress)),nextPageToken",
            }
            if raw_query:
                # Fix #9 — always pass through _sanitize_drive_query; no legacy fallback.
                request_params["q"] = _sanitize_drive_query(raw_query)
            return [
                "drive",
                "files",
                "list",
                "--params",
                json.dumps(request_params),
            ]
        if action == "create_folder":
            folder_name = self._required_text(params, "folder_name")
            return [
                "drive",
                "files",
                "create",
                "--json",
                json.dumps(
                    {"mimeType": "application/vnd.google-apps.folder", "name": folder_name},
                    ensure_ascii=True,
                ),
            ]
        if action == "get_file":
            file_id = self._required_text(params, "file_id")
            return ["drive", "files", "get", "--params", json.dumps({"fileId": file_id})]
        if action == "export_file":
            file_id = self._required_text(params, "file_id")
            mime_type = str(params.get("mime_type") or "text/plain").strip()
            return ["drive", "files", "export", "--params", json.dumps({"fileId": file_id, "mimeType": mime_type})]
        if action == "delete_file":
            file_id = self._required_text(params, "file_id")
            return ["drive", "files", "delete", "--params", json.dumps({"fileId": file_id})]
        raise ValidationError(f"Unsupported drive action: {action}")

    def _build_sheets_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "create_spreadsheet":
            title = self._required_text(params, "title")
            return [
                "sheets",
                "spreadsheets",
                "create",
                "--json",
                json.dumps({
                    "properties": {"title": title},
                    "sheets": [{"properties": {"title": title}}]
                }, ensure_ascii=True),
            ]
        if action == "get_spreadsheet":
            spreadsheet_id = self._required_text(params, "spreadsheet_id")
            return [
                "sheets",
                "spreadsheets",
                "get",
                "--params",
                json.dumps({"spreadsheetId": spreadsheet_id}),
            ]
        if action == "get_values":
            spreadsheet_id = self._required_text(params, "spreadsheet_id")
            range_name = self._format_range(str(params.get("range") or "Sheet1!A1:Z500"))
            return [
                "sheets",
                "spreadsheets",
                "values",
                "get",
                "--params",
                json.dumps({"spreadsheetId": spreadsheet_id, "range": range_name}),
            ]
        if action == "append_values":
            spreadsheet_id = self._required_text(params, "spreadsheet_id")
            range_name = self._format_range(str(params.get("range") or "Sheet1!A1"))
            values = params.get("values")
            if isinstance(values, str):
                values = [[values]]
            if not isinstance(values, list) or not values:
                values = [["No values supplied"]]
            return [
                "sheets",
                "spreadsheets",
                "values",
                "append",
                "--params",
                json.dumps(
                    {
                        "spreadsheetId": spreadsheet_id,
                        "range": range_name,
                        "valueInputOption": "RAW",
                        "insertDataOption": "INSERT_ROWS",
                    },
                    ensure_ascii=True,
                ),
                "--json",
                json.dumps({"range": range_name, "majorDimension": "ROWS", "values": values}, ensure_ascii=True),
            ]
        raise ValidationError(f"Unsupported sheets action: {action}")

    def _build_gmail_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_messages":
            max_results = self._safe_positive_int(params.get("max_results"), default=10)
            query = str(params.get("q") or "").strip()
            request_params: dict[str, Any] = {
                "userId": "me",
                "maxResults": max_results,
                "fields": "messages(id,threadId),nextPageToken,resultSizeEstimate",
            }
            if query:
                request_params["q"] = query
            return [
                "gmail",
                "users",
                "messages",
                "list",
                "--params",
                json.dumps(request_params),
            ]
        if action == "get_message":
            message_id = self._required_text(params, "message_id")
            return [
                "gmail",
                "users",
                "messages",
                "get",
                "--params",
                json.dumps({"userId": "me", "id": message_id}),
            ]
        if action == "send_message":
            to_email = self._required_text(params, "to_email")
            subject = self._required_text(params, "subject")
            body = self._required_text(params, "body")

            attachments = params.get("attachments")
            attachment_paths: list[str] = []
            if isinstance(attachments, str) and attachments.strip():
                attachment_paths = [attachments.strip()]
            elif isinstance(attachments, list):
                attachment_paths = [str(a).strip() for a in attachments if str(a).strip()]

            if attachment_paths:
                raw_email = self._build_raw_email_with_attachments(
                    to_email=to_email,
                    subject=subject,
                    body=body,
                    attachment_paths=attachment_paths,
                )
            else:
                raw_email = self._build_raw_email(to_email=to_email, subject=subject, body=body)

            return [
                "gmail",
                "users",
                "messages",
                "send",
                "--params",
                json.dumps({"userId": "me"}),
                "--json",
                json.dumps({"raw": raw_email}, ensure_ascii=True),
            ]
        raise ValidationError(f"Unsupported gmail action: {action}")

    def _build_calendar_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_events":
            calendar_id = str(params.get("calendar_id") or "primary").strip()
            return [
                "calendar",
                "events",
                "list",
                "--params",
                json.dumps(
                    {
                        "calendarId": calendar_id,
                        "singleEvents": True,
                        "orderBy": "startTime",
                        "maxResults": 20,
                    }
                ),
            ]
        if action == "create_event":
            summary = self._required_text(params, "summary")
            start_date_raw = self._required_text(params, "start_date")
            start_date = start_date_raw.split("T")[0]
            if len(start_date) > 10:
                start_date = start_date[:10]
            return [
                "calendar",
                "events",
                "insert",
                "--params",
                json.dumps({"calendarId": "primary"}),
                "--json",
                json.dumps({"summary": summary, "start": {"date": start_date}, "end": {"date": start_date}}, ensure_ascii=True),
            ]
        raise ValidationError(f"Unsupported calendar action: {action}")

    def _build_docs_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "create_document":
            title = self._required_text(params, "title") if params.get("title") else "Untitled Document"
            body_content = str(params.get("content") or "").strip()
            doc_body: dict[str, Any] = {"title": title}
            if body_content:
                doc_body["body"] = {
                    "content": [
                        {
                            "paragraph": {
                                "elements": [{"textRun": {"content": body_content}}]
                            }
                        }
                    ]
                }
            return [
                "docs",
                "documents",
                "create",
                "--json",
                json.dumps(doc_body, ensure_ascii=True),
            ]
        if action == "get_document":
            doc_id = (
                params.get("document_id")
                or params.get("documentId")
                or params.get("file_id")
                or params.get("fileId")
            )
            if not doc_id or not str(doc_id).strip():
                raise ValidationError("Missing required parameter: document_id")
            return [
                "docs",
                "documents",
                "get",
                "--params",
                json.dumps({"documentId": str(doc_id).strip()}),
            ]
        if action == "batch_update":
            document_id = self._required_text(params, "document_id")
            text = str(params.get("text") or "").strip()
            requests_payload = [
                {
                    "insertText": {
                        "location": {"index": 1},
                        "text": text,
                    }
                }
            ]
            return [
                "docs", "documents", "batchUpdate",
                "--params", json.dumps({"documentId": document_id}),
                "--json", json.dumps({"requests": requests_payload}, ensure_ascii=True),
            ]
        raise ValidationError(f"Unsupported docs action: {action}")

    def _build_slides_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "get_presentation":
            presentation_id = self._required_text(params, "presentation_id")
            return ["slides", "presentations", "get", "--params", json.dumps({"presentationId": presentation_id})]
        raise ValidationError(f"Unsupported slides action: {action}")

    def _build_contacts_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_contacts":
            page_size = self._safe_positive_int(params.get("page_size"), default=10)
            return [
                "people",
                "people",
                "connections",
                "list",
                "--params",
                json.dumps(
                    {
                        "resourceName": "people/me",
                        "pageSize": page_size,
                        "personFields": "names,emailAddresses,phoneNumbers",
                    }
                ),
            ]
        raise ValidationError(f"Unsupported contacts action: {action}")

    def _build_chat_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_spaces":
            page_size = self._safe_positive_int(params.get("page_size"), default=10)
            return [
                "chat",
                "spaces",
                "list",
                "--params",
                json.dumps({"pageSize": page_size}),
            ]
        if action == "send_message":
            space = self._required_text(params, "space")
            text = self._required_text(params, "text")
            return [
                "chat",
                "spaces",
                "messages",
                "create",
                "--params",
                json.dumps({"parent": space}),
                "--json",
                json.dumps({"text": text}, ensure_ascii=True),
            ]
        if action == "list_messages":
            space = self._required_text(params, "space")
            page_size = self._safe_positive_int(params.get("page_size"), default=10)
            return [
                "chat",
                "spaces",
                "messages",
                "list",
                "--params",
                json.dumps({"parent": space, "pageSize": page_size}),
            ]
        raise ValidationError(f"Unsupported chat action: {action}")

    def _build_meet_command(self, action: str, params: dict[str, Any]) -> list[str]:
        if action == "list_conferences":
            return ["meet", "spaces", "list"]
        if action == "get_conference":
            name = self._required_text(params, "name")
            return [
                "meet",
                "spaces",
                "get",
                "--params",
                json.dumps({"name": name}),
            ]
        if action == "create_meeting":
            return ["meet", "spaces", "create"]
        raise ValidationError(f"Unsupported meet action: {action}")

    def _format_range(self, range_str: str) -> str:
        """Ensure sheet names with spaces are quoted correctly."""
        range_str = range_str.strip()
        if "!" not in range_str:
            return range_str
        sheet_part, cell_part = range_str.split("!", 1)
        if " " in sheet_part and not (sheet_part.startswith("'") and sheet_part.endswith("'")):
            return f"'{sheet_part}'!{cell_part}"
        return range_str

    @staticmethod
    def _required_text(params: dict[str, Any], key: str) -> str:
        value = params.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
        variations = [key.lower().replace("_", ""), key.replace("_", "")]
        for k, v in params.items():
            if k.lower().replace("_", "") in variations and v is not None and str(v).strip():
                return str(v).strip()
        raise ValidationError(f"Missing required parameter: {key}")

    @staticmethod
    def _safe_positive_int(value: Any, default: int) -> int:
        try:
            parsed = int(str(value).strip())
            return parsed if parsed > 0 else default
        except Exception:
            return default

    @staticmethod
    def _build_raw_email(to_email: str, subject: str, body: str) -> str:
        """Build a plain text/plain RFC-2822 message (no attachment)."""
        message = (
            f"To: {to_email}\r\n"
            f"Subject: {subject}\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n"
            "MIME-Version: 1.0\r\n"
            "\r\n"
            f"{body}"
        )
        return base64.urlsafe_b64encode(message.encode("utf-8")).decode("ascii")

    @staticmethod
    def _build_raw_email_with_attachments(
        to_email: str,
        subject: str,
        body: str,
        attachment_paths: list[str],
    ) -> str:
        """
        Build a multipart/mixed RFC-2822 message with file attachments.

        Each entry in attachment_paths must be a readable local file path.
        Non-existent paths are silently skipped so the email still sends.
        """
        msg = email_lib.mime.multipart.MIMEMultipart("mixed")
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["MIME-Version"] = "1.0"

        msg.attach(email_lib.mime.text.MIMEText(body, "plain", "utf-8"))

        for path in attachment_paths:
            if not os.path.isfile(path):
                continue
            filename = os.path.basename(path)
            with open(path, "rb") as fh:
                data = fh.read()
            part = email_lib.mime.application.MIMEApplication(data, Name=filename)
            part["Content-Disposition"] = f'attachment; filename="{filename}"'
            msg.attach(part)

        raw_bytes = msg.as_bytes()
        return base64.urlsafe_b64encode(raw_bytes).decode("ascii")


# ---------------------------------------------------------------------------
# Custom exception for permanently unsupported services (no retry needed)
# ---------------------------------------------------------------------------

class UnsupportedServiceError(ValidationError):
    """Raised when a service has no CLI backing and must be skipped without retry."""
