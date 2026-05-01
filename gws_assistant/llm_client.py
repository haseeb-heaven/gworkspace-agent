"""
LiteLLM-based LLM client for gws-assistant.
Single entry point for all LLM calls. Handles:
  - Tool-capable model enforcement
  - API key injection per provider
  - Automatic fallback between models on RateLimitError / AuthenticationError
  - API key rotation (LLM_API_KEY, LLM_API_KEY2, LLM_API_KEY3)
"""

from __future__ import annotations

import logging
from typing import Any

import litellm
from litellm import completion
from litellm.exceptions import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

# Silence litellm's verbose default logging
litellm.suppress_debug_info = True


def _build_api_kwargs(model: str, config: Any) -> dict:
    """
    Return the correct api_key and api_base for the given model string.
    model prefix determines the provider.
    """
    kwargs: dict = {}

    if model.startswith("openrouter/"):
        kwargs["api_key"] = config.api_key  # first key from rotation
        kwargs["api_base"] = config.base_url  # https://openrouter.ai/api/v1

    elif model.startswith("groq/"):
        kwargs["api_key"] = config.groq_api_key

    elif model.startswith("openai/"):
        kwargs["api_key"] = config.openai_api_key

    elif model.startswith("google/") or model.startswith("gemini/"):
        kwargs["api_key"] = config.google_api_key

    elif model.startswith("anthropic/"):
        kwargs["api_key"] = config.anthropic_api_key

    elif model.startswith("mistral/"):
        kwargs["api_key"] = config.mistral_api_key

    elif model.startswith("ollama/"):
        base = config.ollama_api_base or "http://localhost:11434"
        kwargs["api_base"] = base
        # Ollama does not need an API key
        kwargs["api_key"] = "ollama"

    return kwargs


def call_llm(
    messages: list[dict],
    config: Any,
    tools: list[dict] | None = None,
    tool_choice: str = "auto",
    model_override: str | None = None,
) -> Any:
    """
    Call the LLM using LiteLLM with automatic fallback.

    Priority order:
      1. config.model (primary)
      2. config.llm_fallback_models[0] (first fallback)
      3. config.llm_fallback_models[1] (second fallback)
      ... and so on

    Falls back on: RateLimitError, AuthenticationError, APIConnectionError.
    Rotates OpenRouter API keys on RateLimitError before trying next model.

    Returns: litellm ModelResponse object (OpenAI-compatible).
    Raises: RuntimeError if ALL models and keys are exhausted.
    """
    primary_model = model_override or config.model
    model_chain = [primary_model] + [m for m in config.llm_fallback_models if m != primary_model]

    last_error: Exception | None = None

    for model in model_chain:
        # Only rotate keys for OpenRouter models; other providers use
        # a single provider-specific key set by _build_api_kwargs.
        if model.startswith("openrouter/") and config.llm_api_keys:
            api_keys_to_try = config.llm_api_keys
        else:
            api_keys_to_try = [None]

        for i, api_key in enumerate(api_keys_to_try):
            try:
                kwargs = _build_api_kwargs(model, config)
                if api_key:
                    kwargs["api_key"] = api_key  # override with rotation key

                logger.debug(f"[LLM] Calling model={model}")

                call_kwargs: dict = dict(
                    model=model,
                    messages=messages,
                    timeout=config.timeout_seconds,
                    temperature=config.temperature,
                    **kwargs,
                )
                if config.max_tokens is not None:
                    call_kwargs["max_tokens"] = config.max_tokens

                if tools:
                    call_kwargs["tools"] = tools
                    call_kwargs["tool_choice"] = tool_choice

                response = completion(**call_kwargs)
                logger.debug(f"[LLM] Success: model={model}")
                return response

            except RateLimitError as e:
                msg = str(e).lower()
                is_quota = any(k in msg for k in ("quota", "billing", "insufficient_quota", "insufficient_quota_available", "out_of_quota"))
                level = logging.ERROR if is_quota else logging.WARNING

                is_last_key = (i == len(api_keys_to_try) - 1)
                retry_msg = "Trying next key." if not is_last_key else "Trying next model."
                logger.log(
                    level,
                    f"[LLM] {'Quota' if is_quota else 'RateLimit'} error on model={model}. {retry_msg}"
                )
                last_error = e
                continue

            except AuthenticationError as e:
                is_last_key = (i == len(api_keys_to_try) - 1)
                retry_msg = "Trying next key." if not is_last_key else "Trying next model."
                logger.error(f"[LLM] AuthenticationError on model={model}. {retry_msg}")
                last_error = e
                continue  # Try next key in case this one is just invalid/expired

            except (APIConnectionError, BadRequestError) as e:
                msg = str(e).lower()
                if "quota" in msg:
                    logger.error(f"[LLM] Quota exceeded on model={model} (BadRequest). Trying next model.")
                    last_error = e
                    break

                logger.error(f"[LLM] {type(e).__name__} on model={model}: {e}. Trying next model.")
                last_error = e
                break

            except Exception as e:
                logger.error(f"[LLM] Unexpected error on model={model}: {e}")
                last_error = e
                break

    raise RuntimeError(
        f"All LLM models exhausted. Last error: {last_error}\n"
        f"Models tried: {model_chain}\n"
        f"Check .env: LLM_MODEL, LLM_FALLBACK_MODEL, and API keys."
    )
