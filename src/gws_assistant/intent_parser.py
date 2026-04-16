"""Intent parsing with OpenAI/OpenRouter and local fallback."""

from __future__ import annotations

import json
import logging
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
        action = self._detect_action(service, lowered) if service else None
        parameters = self._extract_simple_parameters(lowered)

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
        for service_key, spec in SERVICES.items():
            if service_key in text:
                return service_key
            for alias in spec.aliases:
                if alias in text:
                    return service_key
        return None

    def _detect_action(self, service: str | None, text: str) -> str | None:
        if not service or service not in SERVICES:
            return None
        actions = SERVICES[service].actions
        best_action = None
        best_score = 0
        for action_key, action_spec in actions.items():
            score = sum(1 for keyword in action_spec.keywords if keyword in text)
            if score > best_score:
                best_score = score
                best_action = action_key
        return best_action

    def _extract_simple_parameters(self, text: str) -> dict[str, Any]:
        params: dict[str, Any] = {}
        digits = "".join(ch for ch in text if ch.isdigit())
        if digits:
            params["page_size"] = digits[:3]
            params["max_results"] = digits[:3]
        return params

