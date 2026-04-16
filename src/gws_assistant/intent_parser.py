"""Intent parsing with OpenAI/OpenRouter and local fallback."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from .models import AppConfigModel, Intent
from .service_catalog import SERVICES, normalize_service

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

    def parse(self, user_text: str) -> Intent:
        text = (user_text or "").strip()
        if not text:
            return Intent(
                raw_text=user_text,
                needs_clarification=True,
                clarification_reason="Empty input received.",
            )

        if self.client:
            llm_intent = self._parse_with_llm(text)
            if llm_intent is not None:
                return llm_intent

        return self._parse_with_heuristics(text)

    def _parse_with_llm(self, text: str) -> Intent | None:
        if not self.client:
            return None
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
            completion = self.client.chat.completions.create(
                model=self.config.model,
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
            action = (str(data.get("action") or "").strip() or None)
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
            self.logger.warning("LLM parsing failed, using heuristic fallback: %s", exc)
            return None

    def _parse_with_heuristics(self, text: str) -> Intent:
        lowered = text.lower()
        service = self._detect_service(lowered)
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

        detected_service = None
        for alias, service_key in all_aliases:
            if alias in text:
                detected_service = service_key
                # If we detect 'docs', prioritize it immediately over 'drive'
                if service_key == "docs":
                    return "docs"
                # Keep looking for more specific matches unless we found docs

        return detected_service

    def _detect_action(self, service: str | None, text: str) -> str | None:
        if not service or service not in SERVICES:
            return None
        actions = SERVICES[service].actions
        lowered = text.lower()

        # Priority 1: Strong verb match
        if service == "gmail":
            if "send" in lowered or "compose" in lowered or "write" in lowered:
                return "send_message"
            if "list" in lowered or "search" in lowered or "find" in lowered or "show" in lowered or "inbox" in lowered:
                return "list_messages"
            if "get" in lowered or "read" in lowered or "open" in lowered:
                return "get_message"

        if service == "docs":
            if "read" in lowered or "get" in lowered or "open" in lowered or "show" in lowered:
                return "get_document"
            if "create" in lowered or "new" in lowered:
                return "create_document"
            if "update" in lowered or "append" in lowered or "insert" in lowered or "write" in lowered:
                return "batch_update"

        if service == "drive":
            if "list" in lowered or "search" in lowered or "find" in lowered or "show" in lowered:
                return "list_files"
            if "get" in lowered or "open" in lowered:
                return "get_file"
            if "upload" in lowered or "add" in lowered:
                return "upload_file"
            if "export" in lowered or "download" in lowered:
                return "export_file"
            if "delete" in lowered or "remove" in lowered:
                return "delete_file"
            if "move" in lowered or "relocate" in lowered:
                return "move_file"
            if "folder" in lowered:
                return "create_folder"

        # Fallback to scoring for other services
        best_action = None
        best_score = -999
        for action_key, action_spec in actions.items():
            score = sum(2 if keyword in lowered.split() else 1 if keyword in lowered else 0
                        for keyword in action_spec.keywords)

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

        # 1. Look for explicit key=value pairs (highest priority)
        kv_pairs = re.findall(r"([a-zA-Z0-9_-]+)=([a-zA-Z0-9_-]+)", text)
        for k, v in kv_pairs:
            params[k] = v

        # 2. Extract Google IDs (fallback for bare IDs)
        id_match = re.search(r"\b([a-zA-Z0-9_-]{35,65})\b", text)
        if id_match:
            doc_id = id_match.group(1)
            # Only use if not already found via kv
            if "document_id" not in params:
                params["document_id"] = doc_id
            if "spreadsheet_id" not in params:
                params["spreadsheet_id"] = doc_id
            if "file_id" not in params:
                params["file_id"] = doc_id
            if "presentation_id" not in params:
                params["presentation_id"] = doc_id

        lowered = text.lower()

        # 3. Extract Title (for Docs/Sheets)
        title_match = re.search(r"(?:titled|named|called)\s+['\"](.+?)['\"]", text)
        if not title_match:
            title_match = re.search(r"(?:titled|named|called)\s+([a-zA-Z0-9_-]+)", text)
        if title_match:
            params["title"] = title_match.group(1).strip()
            self.logger.info("Found title: %s", params["title"])

        # 4. Extract Values (for Sheets) - Look for [[...]] or list-like content
        values_match = re.search(r"(\[\[.+?\]\])", text)
        if values_match:
             try:
                 params["values"] = json.loads(values_match.group(1).replace("'", '"'))
                 self.logger.info("Found values array: %s", params["values"])
             except Exception:
                 params["values"] = values_match.group(1)

        # 5. Handle specific Gmail fields
        digits = "".join(ch for ch in lowered if ch.isdigit())
        if digits:
            params["page_size"] = digits[:3]
            params["max_results"] = digits[:3]

        # Simple extraction for Gmail send_message
        if " to " in lowered:
            try:
                to_part = lowered.split(" to ")[1].split()[0]
                if "@" in to_part:
                    params["to_email"] = to_part.strip().rstrip(".")
            except IndexError:
                pass

        if "subject" in lowered:
            # Look for quoted subject or just the rest of the string
            match = re.search(r"subject ['\"](.+?)['\"]", lowered)
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

        return params
