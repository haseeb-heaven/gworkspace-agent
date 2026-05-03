"""Intent parsing with OpenAI/OpenRouter and local fallback."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from .file_types import RE_FILE_PATH
from .models import AppConfigModel, Intent
from .service_catalog import SERVICES, normalize_service

RE_INTENT_GMAIL_GET = re.compile(r"([a-zA-Z0-9_-]{35,65})")
RE_INTENT_QUOTED_KV = re.compile(r"([a-zA-Z0-9_-]+)=(['\"])(.+?)\2")
RE_INTENT_UNQUOTED_KV = re.compile(r"([a-zA-Z0-9_-]+)=([^\s\"']+)")
RE_INTENT_ID_MATCH = re.compile(r"\b([a-zA-Z0-9_-]{35,65})\b")
RE_INTENT_QUERY_MATCH_QUOTED = re.compile(
    r"(?:about|for|matching|with|named|find|list|show|all|my)\s+['\"](.+?)['\"]", re.IGNORECASE
)
RE_INTENT_QUERY_MATCH_UNQUOTED = re.compile(
    r"(?:about|for|matching|with|named|find|list|show|all|my)\s+([a-zA-Z0-9 _.-]{3,60})", re.IGNORECASE
)
RE_INTENT_QUERY_CLEAN_MYALL = re.compile(r"^(my|all)\s+", re.IGNORECASE)
RE_INTENT_QUERY_CLEAN_IN = re.compile(r"\s+in\s+(gmail|drive|google\s+docs?|sheets?)$", re.IGNORECASE)
RE_INTENT_QUERY_SPLIT = re.compile(r"\s+(and|then|to|save|write|export|extract)\s+", re.IGNORECASE)
RE_INTENT_TITLE_MATCH_QUOTED = re.compile(r"(?:titled|named|called)\s+['\"](.+?)['\"]")
RE_INTENT_TITLE_MATCH_UNQUOTED = re.compile(r"(?:titled|named|called)\s+([a-zA-Z0-9_-]+)")
RE_INTENT_VALUES_MATCH = re.compile(r"(\[\[.+?\]\])")
RE_INTENT_SUBJECT_MATCH = re.compile(r"subject ['\"](.+?)['\"]")
# Matches file paths after upload/add/put keywords, or bare absolute/relative paths.

try:
    from openai import OpenAI

    HAS_OPENAI_SDK = True
except Exception:  # pragma: no cover
    HAS_OPENAI_SDK = False


class IntentParser:
    """Extracts service/action/parameters from user text."""

    def __init__(self, config: AppConfigModel, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self.client = self._build_client()

    def _build_client(self) -> Any | None:
        if not self.config.api_key:
            self.logger.warning("No API key configured, using heuristic intent parsing.")
            return None
        if not HAS_OPENAI_SDK:
            self.logger.warning("OpenAI SDK import failed, using heuristic intent parsing.")
            return None
        try:
            client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout_seconds,
            )
            self.logger.debug("Initialized LLM client for provider=%s", self.config.provider)
            return client
        except Exception as exc:
            self.logger.exception("Failed to initialize LLM client: %s", exc)
            return None

    def parse(self, user_text: str, force_heuristic: bool = False) -> Intent:
        text = (user_text or "").strip()
        if not text:
            return Intent(
                raw_text=user_text,
                needs_clarification=True,
                clarification_reason="Empty input received.",
            )

        if force_heuristic:
            return self.parse_heuristically(text)

        if self.client:
            llm_intent = self._parse_with_llm(text)
            if llm_intent is not None:
                return llm_intent

        return self.parse_heuristically(text)

    def _parse_with_llm(self, text: str) -> Intent | None:
        if not self.client:
            return None

        max_retries = self.config.max_retries
        for attempt in range(max_retries):
            try:
                services = ", ".join(sorted(SERVICES.keys()))
                prompt = (
                    "Extract a structured intent for Google Workspace command execution. "
                    "Return valid JSON only with keys: service, action, parameters, confidence, needs_clarification, clarification_reason. "
                    f"service must be one of: {services}. "
                    "action should be snake_case and map to user request. "
                    "parameters must be an object. "
                    "If service is missing or unsupported, set needs_clarification=true."
                )
                from typing import cast
                client = cast(Any, self.client)
                completion = client.chat.completions.create(
                    model=self.config.api_model_name(),
                    temperature=0,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": text},
                    ],
                )
                content = completion.choices[0].message.content or "{}"
                data = json.loads(content)
                service = normalize_service(str(data.get("service") or "").strip())
                action = str(data.get("action") or "").strip() or None
                parameters = data.get("parameters") if isinstance(data.get("parameters"), dict) else {}
                confidence = float(data.get("confidence") or 0.0)
                needs_clarification = bool(data.get("needs_clarification") or False)
                reason = str(data.get("clarification_reason") or "").strip() or None
                if not service:
                    needs_clarification = True
                    reason = reason or "Service was not recognized from your request."
                return Intent(
                    raw_text=text,
                    service=service,
                    action=action,
                    parameters=parameters,
                    confidence=confidence,
                    needs_clarification=needs_clarification,
                    clarification_reason=reason,
                )
            except Exception as exc:
                msg = str(exc).lower()
                is_rate_limit = "429" in msg or "rate limit" in msg or "quota" in msg
                if is_rate_limit and attempt < max_retries - 1:
                    import time

                    delay = 2**attempt
                    self.logger.warning(
                        "LLM rate limit detected in IntentParser. Rotating key and retrying in %ds...", delay
                    )
                    self.config.rotate_api_key()
                    self.client = self._build_client()  # Re-init client with new key
                    time.sleep(delay)
                    continue

                self.logger.warning("LLM parsing failed, using heuristic fallback: %s", exc)
                return None
        return None

    def parse_heuristically(self, text: str) -> Intent:
        service = self._detect_service(text)
        action = self._detect_action(service, text) if service else None

        # IDs are case-sensitive, so we need original text
        parameters = self._extract_simple_parameters(text)

        needs_clarification = not service
        reason = None
        if not service:
            reason = "I could not detect a supported Google service."
        elif not action:
            reason = "I found the service but could not detect the action."

        return Intent(
            raw_text=text,
            service=service,
            action=action,
            parameters=parameters,
            confidence=0.4 if service else 0.1,
            needs_clarification=needs_clarification,
            clarification_reason=reason,
        )

    def _detect_service(self, text: str) -> str | None:
        # Sort aliases by length descending to match 'google docs' before 'docs' or 'google'
        all_aliases = []
        for service_key, spec in SERVICES.items():
            all_aliases.append((service_key, service_key))
            for alias in spec.aliases:
                all_aliases.append((alias, service_key))

        all_aliases.sort(key=lambda x: len(x[0]), reverse=True)

        # High-signal word check first (whole word)
        for alias, service_key in all_aliases:
            pattern = re.compile(rf"\b{re.escape(alias)}\b", re.IGNORECASE)
            if pattern.search(text):
                # If we detect a specific Workspace service, prioritize it over generic 'search'
                if service_key != "search":
                    return service_key

        # Fallback to substring if no whole word match
        for alias, service_key in all_aliases:
            if alias.lower() in text.lower():
                return service_key
        return None

    def _detect_action(self, service: str | None, text: str) -> str | None:
        if not service or service not in SERVICES:
            return None
        actions = SERVICES[service].actions
        lowered = text.lower()

        # Priority 1: Strong verb match
        if service == "gmail":
            if any(kw in lowered for kw in ("send", "compose", "write", "share")):
                return "send_message"
            if any(kw in lowered for kw in ("list", "search", "find", "show", "inbox", "get")):
                # If ID is present, it's a 'get', else 'list'
                if RE_INTENT_GMAIL_GET.search(text):
                    return "get_message"
                return "list_messages"

        if service == "docs":
            if any(kw in lowered for kw in ("create", "new", "draft")):
                return "create_document"
            if any(kw in lowered for kw in ("read", "get", "open", "show", "fetch")):
                return "get_document"
            if any(kw in lowered for kw in ("update", "append", "insert", "write", "add")):
                return "batch_update"

        if service == "sheets":
            if any(kw in lowered for kw in ("create", "new")):
                return "create_spreadsheet"
            if any(kw in lowered for kw in ("append", "add", "save", "write", "insert", "rows")):
                return "append_values"
            if any(kw in lowered for kw in ("read", "fetch", "get", "show", "values", "data", "search")):
                # Prefer get_values for data retrieval, but could be get_spreadsheet
                if "id" in lowered and "spreadsheet" in lowered:
                    return "get_spreadsheet"
                return "get_values"

        if service == "drive":
            if any(kw in lowered for kw in ("list", "search", "find", "show", "view", "files")):
                return "list_files"
            if any(kw in lowered for kw in ("upload", "add", "put")):
                return "upload_file"
            if any(kw in lowered for kw in ("get", "details", "open")):
                return "get_file"
            if any(kw in lowered for kw in ("export", "download", "attach", "attachment", "pdf", "csv")):
                return "export_file"
            if any(kw in lowered for kw in ("delete", "remove", "trash", "cancel")):
                return "delete_file"
            if any(kw in lowered for kw in ("move", "relocate", "transfer", "organize")):
                return "move_file"
            if "folder" in lowered:
                return "create_folder"

        if service == "calendar":
            # Priority: find/search/list events before get/update/delete which need event_id
            if any(kw in lowered for kw in ("find", "search", "list", "show", "upcoming", "next", "view")):
                return "list_events"
            if any(kw in lowered for kw in ("create", "schedule", "add", "new", "make")):
                return "create_event"
            if any(kw in lowered for kw in ("delete", "remove", "cancel", "trash")):
                return "delete_event"
            if any(kw in lowered for kw in ("update", "edit", "modify", "change", "reschedule")):
                return "update_event"
            # get_event requires event_id, only use if we have an ID in the text
            if any(kw in lowered for kw in ("get", "details", "fetch")):
                # Check if we have an event ID (calendar event IDs are typically 20+ chars)
                if RE_INTENT_ID_MATCH.search(text):
                    return "get_event"
                # Without ID, default to list_events
                return "list_events"

        # Fallback to scoring for other services
        best_action = None
        best_score = -999
        for action_key, action_spec in actions.items():
            score = sum(
                2 if keyword in lowered.split() else 1 if keyword in lowered else 0 for keyword in action_spec.keywords
            )

            # Penalize list actions if 'send' is present (generic)
            if "list" in action_key and "send" in lowered:
                score -= 10

            # Apply heavy penalty for negative keywords
            if hasattr(action_spec, "negative_keywords"):
                for neg in action_spec.negative_keywords:
                    if neg in lowered:
                        score -= 20

            if score > best_score:
                best_score = score
                best_action = action_key

        return best_action if best_score > 0 else None

    def _extract_simple_parameters(self, text: str) -> dict[str, Any]:
        params: dict[str, Any] = {}
        lowered = text.lower()

        # 1a. Handle quoted values first (e.g. key="value with spaces")
        quoted_kv = RE_INTENT_QUOTED_KV.findall(text)
        for k, quote, v in quoted_kv:
            params[k] = v
            self.logger.debug(f"DEBUG: Found quoted KV: {k}={v}")

        # 1b. Handle unquoted values (e.g. key=value or key=$placeholder)
        # We look for key= followed by non-whitespace characters
        unquoted_kv = RE_INTENT_UNQUOTED_KV.findall(text)
        for k, v in unquoted_kv:
            if k not in params:
                params[k] = v
                self.logger.debug(f"DEBUG: Found unquoted KV: {k}={v}")

        # 2. Extract Google IDs (fallback for bare IDs)
        id_match = RE_INTENT_ID_MATCH.search(text)
        if id_match:
            doc_id = id_match.group(1)
            if "document_id" not in params:
                params["document_id"] = doc_id
            if "spreadsheet_id" not in params:
                params["spreadsheet_id"] = doc_id
            if "file_id" not in params:
                params["file_id"] = doc_id
            if "presentation_id" not in params:
                params["presentation_id"] = doc_id

        # 3. Extract Search Query (Gmail / Drive)
        query_match = RE_INTENT_QUERY_MATCH_QUOTED.search(text)
        if not query_match:
            query_match = RE_INTENT_QUERY_MATCH_UNQUOTED.search(text)

        if query_match:
            query = query_match.group(1).strip()
            # Clean up
            query = RE_INTENT_QUERY_CLEAN_MYALL.sub("", query)
            query = RE_INTENT_QUERY_CLEAN_IN.sub("", query)
            query = RE_INTENT_QUERY_SPLIT.split(query)[0].strip()

            if query and query.lower() not in ("gmail", "drive", "file", "document", "spreadsheet", "sheet"):
                params["q"] = query

        # 4. Extract Title (for Docs/Sheets)
        title_match = RE_INTENT_TITLE_MATCH_QUOTED.search(text)
        if not title_match:
            title_match = RE_INTENT_TITLE_MATCH_UNQUOTED.search(text)
        if title_match:
            params["title"] = title_match.group(1).strip()

        # 4. Extract Values (for Sheets)
        values_match = RE_INTENT_VALUES_MATCH.search(text)
        if values_match:
            try:
                params["values"] = json.loads(values_match.group(1).replace("'", '"'))
            except Exception:
                params["values"] = values_match.group(1)

        # 5. Handle specific Gmail fields
        if " to " in lowered:
            try:
                to_part = lowered.split(" to ")[1].split()[0]
                if "@" in to_part:
                    params["to_email"] = to_part.strip().rstrip(".")
            except IndexError:
                pass

        if "subject" in lowered:
            match = RE_INTENT_SUBJECT_MATCH.search(lowered)
            if match:
                params["subject"] = match.group(1)
            else:
                try:
                    params["subject"] = lowered.split("subject ")[1].split("body")[0].strip()
                except IndexError:
                    pass

        if "body" in lowered:
            try:
                params["body"] = lowered.split("body ")[1].strip()
            except IndexError:
                pass

        # 6. Extract file path for upload operations
        path_match = RE_FILE_PATH.search(text)
        if path_match:
            file_path = next(g for g in path_match.groups() if g is not None)
            if file_path:
                params["file_path"] = file_path
                self.logger.debug("DEBUG: Found file_path=%s", file_path)

        return params
