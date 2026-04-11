"""Configuration loading for the assistant."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

from .models import AppConfigModel


OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
OPENAI_DEFAULT_MODEL = "gpt-4.1-mini"
OPENROUTER_DEFAULT_MODEL = "openai/gpt-4.1-mini"


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class AppConfig:
    """Reads and normalizes environment configuration."""

    @staticmethod
    def from_env() -> AppConfigModel:
        env_file_path = Path(".env").expanduser().resolve()
        load_dotenv(dotenv_path=env_file_path if env_file_path.exists() else None, override=False)

        provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
        openai_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        openrouter_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()

        if not provider:
            provider = "openrouter" if openrouter_key else "openai"

        if provider == "openrouter":
            api_key = openrouter_key or openai_key or None
            model = (os.getenv("OPENROUTER_MODEL") or OPENROUTER_DEFAULT_MODEL).strip()
            base_url = (os.getenv("OPENROUTER_BASE_URL") or OPENROUTER_DEFAULT_BASE_URL).strip()
        else:
            provider = "openai"
            api_key = openai_key or None
            model = (os.getenv("OPENAI_MODEL") or OPENAI_DEFAULT_MODEL).strip()
            base_url = (os.getenv("OPENAI_BASE_URL") or "").strip() or None

        timeout_seconds = int((os.getenv("LLM_TIMEOUT_SECONDS") or "30").strip())
        gws_binary_value = os.getenv("GWS_BINARY_PATH", "gws.exe")
        gws_binary_path = _resolve_gws_binary_path(gws_binary_value)
        log_dir = Path(os.getenv("APP_LOG_DIR", "logs")).expanduser().resolve()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = log_dir / "gws_assistant.log"
        log_level = (os.getenv("APP_LOG_LEVEL") or "INFO").strip().upper()
        verbose = _to_bool(os.getenv("APP_VERBOSE"), default=True)
        setup_complete = env_file_path.exists() and gws_binary_path.exists() and gws_binary_path.is_file()
        
        max_retries = int((os.getenv("MAX_RETRIES") or "3").strip())
        langchain_enabled = _to_bool(os.getenv("LANGCHAIN_ENABLED"), default=True)

        return AppConfigModel(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            gws_binary_path=gws_binary_path,
            log_file_path=log_file_path,
            log_level=log_level,
            verbose=verbose,
            env_file_path=env_file_path,
            setup_complete=setup_complete,
            max_retries=max_retries,
            langchain_enabled=langchain_enabled,
        )


def _resolve_gws_binary_path(value: str) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.exists() and candidate.name == value:
        discovered = shutil.which(value)
        if discovered:
            return Path(discovered).resolve()
    return candidate.resolve()
