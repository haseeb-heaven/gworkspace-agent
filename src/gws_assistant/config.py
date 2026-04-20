"""Configuration loading for the assistant."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

from .models import AppConfigModel

OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_DEFAULT_MODEL = "openrouter/free"


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

        gws_binary_value = (os.getenv("GWS_BINARY_PATH") or "").strip()
        if not gws_binary_value:
            raise ValueError("GWS_BINARY_PATH must be set in .env")
        gws_binary_path = _resolve_gws_binary_path(gws_binary_value)

        default_recipient_email = (os.getenv("DEFAULT_RECIPIENT_EMAIL") or "").strip()
        if not default_recipient_email:
            raise ValueError("DEFAULT_RECIPIENT_EMAIL must be set in .env")

        provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
        openrouter_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
        generic_key = (os.getenv("LLM_API_KEY") or "").strip()

        if not provider:
            provider = "openrouter"

        if provider != "openrouter":
            raise ValueError("Only OpenRouter free models are supported. Set LLM_PROVIDER=openrouter.")

        api_key = generic_key or openrouter_key or None
        model = (os.getenv("LLM_MODEL") or os.getenv("OPENROUTER_MODEL") or OPENROUTER_DEFAULT_MODEL).strip()
        if model != "openrouter/free" and not model.endswith(":free"):
            raise ValueError("OpenRouter model must be a free model ending with ':free' or equal to 'openrouter/free'.")
        base_url: str | None = (os.getenv("OPENROUTER_BASE_URL") or OPENROUTER_DEFAULT_BASE_URL).strip()

        timeout_seconds = int((os.getenv("LLM_TIMEOUT_SECONDS") or "30").strip())

        log_dir = Path(os.getenv("APP_LOG_DIR", "logs")).expanduser().resolve()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = log_dir / "gws_assistant.log"
        log_level = (os.getenv("APP_LOG_LEVEL") or "INFO").strip().upper()
        verbose = _to_bool(os.getenv("APP_VERBOSE"), default=True)
        setup_complete = env_file_path.exists() and gws_binary_path.exists() and gws_binary_path.is_file()

        max_retries = int((os.getenv("MAX_RETRIES") or "3").strip())
        max_replans = int((os.getenv("MAX_REPLANS") or "1").strip())
        langchain_enabled = _to_bool(os.getenv("LANGCHAIN_ENABLED"), default=True)

        # Default True — always recover via heuristic planner when LLM fails.
        # Set USE_HEURISTIC_FALLBACK=false in .env only if you want hard failures
        # on LLM planning errors (useful for strict CI/test environments).
        use_heuristic_fallback = _to_bool(os.getenv("USE_HEURISTIC_FALLBACK"), default=True)

        code_execution_enabled = _to_bool(os.getenv("CODE_EXECUTION_ENABLED"), default=True)
        code_execution_backend = (os.getenv("CODE_EXECUTION_BACKEND") or "local").strip().lower()
        e2b_api_key = (os.getenv("E2B_API_KEY") or "").strip() or None

        gws_timeout_seconds = int((os.getenv("GWS_TIMEOUT_SECONDS") or "0").strip())
        gws_max_retries = int((os.getenv("GWS_MAX_RETRIES") or "3").strip())

        # Support multiple API keys for rotation (only for openrouter)
        openrouter_api_keys = []
        if provider == "openrouter":
            openrouter_api_keys_list = [
                os.getenv("OPENROUTER_API_KEY1"),
                os.getenv("OPENROUTER_API_KEY2"),
                os.getenv("OPENROUTER_API_KEY3"),
                os.getenv("OPENROUTER_API_KEY"), # Default fallback
            ]
            openrouter_api_keys = [k.strip() for k in openrouter_api_keys_list if k and k.strip()]
        if not openrouter_api_keys and api_key:
            openrouter_api_keys = [api_key]

        max_snippet_len = int((os.getenv("MAX_CONTEXT_SNIPPET_LEN") or "300").strip())
        mem0_api_key = (os.getenv("MEM0_API_KEY") or "").strip() or None
        mem0_user_id = (os.getenv("MEM0_USER_ID") or "").strip() or None
        mem0_host = (os.getenv("MEM0_HOST") or "").strip() or None
        mem0_local_storage_path = (os.getenv("MEM0_LOCAL_STORAGE_PATH") or ".gemini/memories.jsonl").strip()
        telegram_bot_token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip() or None
        telegram_chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip() or None

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
            max_replans=max_replans,
            langchain_enabled=langchain_enabled,
            use_heuristic_fallback=use_heuristic_fallback,
            code_execution_enabled=code_execution_enabled,
            code_execution_backend=code_execution_backend,
            e2b_api_key=e2b_api_key,
            gws_timeout_seconds=gws_timeout_seconds,
            gws_max_retries=gws_max_retries,
            openrouter_api_keys=openrouter_api_keys,
            max_context_snippet_len=max_snippet_len,
            default_recipient_email=default_recipient_email,
            mem0_api_key=mem0_api_key,
            mem0_user_id=mem0_user_id,
            mem0_host=mem0_host,
            mem0_local_storage_path=mem0_local_storage_path,
            telegram_bot_token=telegram_bot_token,
            telegram_chat_id=telegram_chat_id,
        )



def _resolve_gws_binary_path(value: str) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.exists() and candidate.name == value:
        discovered = shutil.which(value)
        if discovered:
            return Path(discovered).resolve()
    return candidate.resolve()
