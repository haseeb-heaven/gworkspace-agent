"""Configuration loading for the assistant."""

from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path

from dotenv import load_dotenv

from .model_registry import validate_tool_model
from .models import AppConfigModel

OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_DEFAULT_MODEL = "openrouter/free"


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_set(value: str | None, default: set[str]) -> set[str]:
    """Parse comma-separated string into set."""
    if value is None:
        return default
    return {item.strip() for item in value.split(",") if item.strip()}


def _to_list(value: str | None, default: list[str]) -> list[str]:
    """Parse comma-separated string into list."""
    if value is None:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _to_dict(value: str | None, default: dict[str, str]) -> dict[str, str]:
    """Parse comma-separated key:value pairs into dict."""
    if value is None:
        return default
    result = {}
    for item in value.split(","):
        item = item.strip()
        if ":" in item:
            key, val = item.split(":", 1)
            result[key.strip()] = val.strip()
    return result


class AppConfig:
    """Reads and normalizes environment configuration."""

    _cached_config: AppConfigModel | None = None
    _config_lock = threading.Lock()

    @classmethod
    def from_env(cls) -> AppConfigModel:
        if cls._cached_config is not None:
            return cls._cached_config

        with cls._config_lock:
            if cls._cached_config is not None:
                return cls._cached_config

            env_file_path = Path(".env").expanduser().resolve()
            load_dotenv(dotenv_path=env_file_path if env_file_path.exists() else None, override=False)

            ci_mode = _to_bool(os.getenv("CI"), default=False)

            gws_binary_value = (os.getenv("GWS_BINARY_PATH") or "").strip()
            if not gws_binary_value:
                if ci_mode:
                    gws_binary_path = Path(os.devnull)
                else:
                    raise ValueError("GWS_BINARY_PATH must be set in .env")
            else:
                gws_binary_path = _resolve_gws_binary_path(gws_binary_value)

            default_recipient_email = (os.getenv("DEFAULT_RECIPIENT_EMAIL") or "").strip()
            if not default_recipient_email:
                raise ValueError("DEFAULT_RECIPIENT_EMAIL must be set in .env")

            drive_folder_name = (os.getenv("DRIVE_FOLDER_NAME") or "New Folder").strip() or "New Folder"

            provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
            openrouter_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
            generic_key = (os.getenv("LLM_API_KEY") or "").strip()

            if not provider:
                provider = "openrouter"

            api_key = generic_key or openrouter_key or None

            # Rotation keys (Priority 1: LLM_API_KEY series)
            llm_api_keys = []
            for i in range(1, 4):
                key_name = f"LLM_API_KEY{i}" if i > 1 else "LLM_API_KEY"
                k = (os.getenv(key_name) or "").strip()
                if k:
                    llm_api_keys.append(k)

            # Fallback (Priority 2: Provider-specific keys if LLM_API_KEY series is empty)
            if not llm_api_keys:
                provider_specific_key = None
                if provider == "openrouter":
                    provider_specific_key = os.getenv("OPENROUTER_API_KEY")
                elif provider == "openai":
                    provider_specific_key = os.getenv("OPENAI_API_KEY")
                elif provider == "groq":
                    provider_specific_key = os.getenv("GROQ_API_KEY")
                elif provider in ("google", "gemini"):
                    provider_specific_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
                elif provider == "anthropic":
                    provider_specific_key = os.getenv("ANTHROPIC_API_KEY")
                elif provider == "mistral":
                    provider_specific_key = os.getenv("MISTRAL_API_KEY")

                if provider_specific_key:
                    llm_api_keys.append(provider_specific_key.strip())

            # If still no keys, try generic api_key from previous logic (if any)
            if not llm_api_keys and generic_key:
                llm_api_keys.append(generic_key)
            elif not llm_api_keys and openrouter_key:
                 llm_api_keys.append(openrouter_key)

            api_key = llm_api_keys[0] if llm_api_keys else None

            # Resolve primary model — prefer LLM_MODEL, fall back to OPENROUTER_MODEL alias
            model = (
                os.getenv("LLM_MODEL") or os.getenv("OPENROUTER_MODEL") or "openrouter/nvidia/nemotron-super-49b-v1:free"
            ).strip()

            if provider == "openrouter" and not model.startswith("openrouter/") and "/" not in model:
                model = f"openrouter/{model}"

            # Resolve fallback models
            fallback_raw = [
                os.getenv("LLM_FALLBACK_MODEL") or "",
                os.getenv("LLM_FALLBACK_MODEL2") or "",
                os.getenv("LLM_FALLBACK_MODEL3") or "",
            ]
            llm_fallback_models = []
            for m in fallback_raw:
                m = m.strip()
                if m:
                    if provider == "openrouter" and not m.startswith("openrouter/"):
                        m = f"openrouter/{m}"
                    llm_fallback_models.append(m)

            # Enforce tool-calling support on primary model
            if not ci_mode:
                validate_tool_model(model, "LLM_MODEL")

                # Enforce tool-calling support on each fallback model
                for idx, fb_model in enumerate(llm_fallback_models):
                    env_label = "LLM_FALLBACK_MODEL" if idx == 0 else f"LLM_FALLBACK_MODEL{idx + 1}"
                    validate_tool_model(fb_model, env_label)

            base_url: str | None = (os.getenv("OPENROUTER_BASE_URL") or OPENROUTER_DEFAULT_BASE_URL).strip()

            timeout_seconds = int((os.getenv("LLM_TIMEOUT_SECONDS") or "30").strip())
            max_tokens_val = (os.getenv("LLM_MAX_TOKENS") or "").strip()
            max_tokens = int(max_tokens_val) if max_tokens_val else None
            temperature = float((os.getenv("LLM_TEMPERATURE") or "0.0").strip())

            log_dir = Path(os.getenv("APP_LOG_DIR", "logs")).expanduser().resolve()
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file_path = log_dir / "gws_assistant.log"
            log_level = (os.getenv("APP_LOG_LEVEL") or "INFO").strip().upper()
            verbose = _to_bool(os.getenv("APP_VERBOSE"), default=True)

            # Provider specific keys
            groq_api_key = (os.getenv("GROQ_API_KEY") or "").strip() or api_key
            openai_api_key = (os.getenv("OPENAI_API_KEY") or "").strip() or api_key
            google_api_key = (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip() or api_key
            anthropic_api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip() or api_key
            mistral_api_key = (os.getenv("MISTRAL_API_KEY") or "").strip() or api_key
            ollama_api_base = (os.getenv("OLLAMA_API_BASE") or "").strip() or None
            memory_type = (os.getenv("MEMORY_TYPE") or "local").strip().lower()
            setup_complete = env_file_path.exists() and (ci_mode or (gws_binary_path.exists() and gws_binary_path.is_file()))

            max_retries = int((os.getenv("MAX_RETRIES") or "3").strip())
            max_replans = int((os.getenv("MAX_REPLANS") or "1").strip())
            langchain_enabled = _to_bool(os.getenv("LANGCHAIN_ENABLED"), default=True)

            # Default True — always recover via heuristic planner when LLM fails.
            # Set USE_HEURISTIC_FALLBACK=false in .env only if you want hard failures
            # on LLM planning errors (useful for strict CI/test environments).
            use_heuristic_fallback = _to_bool(os.getenv("USE_HEURISTIC_FALLBACK"), default=True)

            code_execution_enabled = _to_bool(os.getenv("CODE_EXECUTION_ENABLED"), default=True)
            code_execution_backend = (os.getenv("CODE_EXECUTION_BACKEND") or "local").strip().lower()
            if code_execution_backend == "restricted_subprocess":
                code_execution_backend = "local"
            code_execution_timeout_seconds = int((os.getenv("CODE_EXECUTION_TIMEOUT_SECONDS") or "5").strip())
            e2b_api_key = (os.getenv("E2B_API_KEY") or "").strip() or None

            gws_timeout_seconds = int((os.getenv("GWS_TIMEOUT_SECONDS") or "0").strip())
            gws_max_retries = int((os.getenv("GWS_MAX_RETRIES") or "3").strip())

            max_snippet_len = int((os.getenv("MAX_CONTEXT_SNIPPET_LEN") or "300").strip())
            mem0_api_key = (os.getenv("MEM0_API_KEY") or "").strip() or None
            mem0_user_id = (os.getenv("MEM0_USER_ID") or "").strip() or None
            mem0_host = (os.getenv("MEM0_HOST") or "").strip() or None
            mem0_local_storage_path = (os.getenv("MEM0_LOCAL_STORAGE_PATH") or ".gemini/memories.jsonl").strip()
            telegram_bot_token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip() or None
            telegram_chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip() or None
            telegram_confirmation_timeout_seconds = float(
                (os.getenv("TELEGRAM_CONFIRMATION_TIMEOUT_SECONDS") or "60").strip()
            )
            # Removed redundant re-fetch of groq_api_key, ollama_api_base, memory_type
            # as they are now resolved above.

            sandbox_enabled = _to_bool(os.getenv("SANDBOX_ENABLED"), default=True)
            read_only_mode = _to_bool(os.getenv("READ_ONLY_MODE"), default=False)
            no_confirm = _to_bool(os.getenv("NO_CONFIRM"), default=False)
            force_dangerous = _to_bool(os.getenv("FORCE_DANGEROUS"), default=False)

            # Verification Engine Configuration
            verification_exact_placeholders = _to_set(
                os.getenv("VERIFICATION_EXACT_PLACEHOLDERS"),
                default={
                    "none", "null", "n/a", "na", "undefined",
                    "todo", "fixme", "placeholder", "example", "sample", "dummy",
                    "your_value", "insert_here", "replace_me", "changeme", "default",
                    "fake", "mock", "temporary", "tbd", "missing"
                }
            )
            verification_numeric_placeholders = _to_set(
                os.getenv("VERIFICATION_NUMERIC_PLACEHOLDERS"),
                default={"0000", "1234", "9999", "00000000"}
            )
            verification_exact_emails = _to_set(
                os.getenv("VERIFICATION_EXACT_EMAILS"),
                default={"noreply@domain.com", "noreply@example.com"}
            )
            verification_email_placeholder_domains = _to_list(
                os.getenv("VERIFICATION_EMAIL_PLACEHOLDER_DOMAINS"),
                default=["@test.com"]
            )
            verification_destructive_operations = _to_set(
                os.getenv("VERIFICATION_DESTRUCTIVE_OPERATIONS"),
                default={
                    "drive_delete_file", "drive_empty_trash", "drive_move_to_trash",
                    "gmail_delete_message", "gmail_trash_message", "gmail_batch_delete", "gmail_empty_trash",
                    "sheets_delete_spreadsheet", "sheets_clear_all_data", "sheets_delete_sheet_tab",
                    "docs_delete_document",
                    "calendar_delete_event", "calendar_delete_calendar",
                    "contacts_delete_contact",
                }
            )
            verification_bulk_indicators = _to_list(
                os.getenv("VERIFICATION_BULK_INDICATORS"),
                default=["batch", "bulk", "multiple", "all"]
            )
            verification_id_fields = _to_list(
                os.getenv("VERIFICATION_ID_FIELDS"),
                default=["file_id", "document_id", "spreadsheet_id", "message_id", "event_id", "task_id", "contact_id"]
            )
            verification_content_fields = _to_list(
                os.getenv("VERIFICATION_CONTENT_FIELDS"),
                default=["body", "content", "message", "text", "description"]
            )
            verification_create_id_fields = _to_list(
                os.getenv("VERIFICATION_CREATE_ID_FIELDS"),
                default=["id", "documentId", "spreadsheetId", "fileId", "messageId", "resourceName", "threadId", "name", "formId", "taskId", "contactId"]
            )
            verification_suspicious_patterns = _to_dict(
                os.getenv("VERIFICATION_SUSPICIOUS_PATTERNS"),
                default={
                    "delete_all": r"delete.*all",
                    "remove_everything": r"remove.*everything",
                    "wipe_all": r"wipe.*all",
                    "clear_all": r"clear.*all",
                }
            )

            cls._cached_config = AppConfigModel(
                provider=provider,
                model=model,
                api_key=api_key,
                base_url=base_url,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
                temperature=temperature,
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
                code_execution_timeout_seconds=code_execution_timeout_seconds,
                e2b_api_key=e2b_api_key,
                gws_timeout_seconds=gws_timeout_seconds,
                gws_max_retries=gws_max_retries,
                llm_api_keys=llm_api_keys,
                max_context_snippet_len=max_snippet_len,
                default_recipient_email=default_recipient_email,
                drive_folder_name=drive_folder_name,
                mem0_api_key=mem0_api_key,
                mem0_user_id=mem0_user_id,
                mem0_host=mem0_host,
                mem0_local_storage_path=mem0_local_storage_path,
                telegram_bot_token=telegram_bot_token,
                telegram_chat_id=telegram_chat_id,
                telegram_confirmation_timeout_seconds=telegram_confirmation_timeout_seconds,
                sandbox_enabled=sandbox_enabled,
                read_only_mode=read_only_mode,
                no_confirm=no_confirm,
                force_dangerous=force_dangerous,
                llm_fallback_models=llm_fallback_models,
                groq_api_key=groq_api_key,
                openai_api_key=openai_api_key,
                google_api_key=google_api_key,
                anthropic_api_key=anthropic_api_key,
                mistral_api_key=mistral_api_key,
                ollama_api_base=ollama_api_base,
                memory_type=memory_type,
                verification_exact_placeholders=verification_exact_placeholders,
                verification_numeric_placeholders=verification_numeric_placeholders,
                verification_exact_emails=verification_exact_emails,
                verification_email_placeholder_domains=verification_email_placeholder_domains,
                verification_destructive_operations=verification_destructive_operations,
                verification_bulk_indicators=verification_bulk_indicators,
                verification_id_fields=verification_id_fields,
                verification_content_fields=verification_content_fields,
                verification_create_id_fields=verification_create_id_fields,
                verification_suspicious_patterns=verification_suspicious_patterns,
            )
            return cls._cached_config

    @classmethod
    def clear_cache(cls):
        """Clears the cached configuration singleton (useful for tests)."""
        with cls._config_lock:
            cls._cached_config = None


def _resolve_gws_binary_path(value: str) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.exists() and candidate.name == value:
        discovered = shutil.which(value)
        if discovered:
            return Path(discovered).resolve()
    return candidate.resolve()
