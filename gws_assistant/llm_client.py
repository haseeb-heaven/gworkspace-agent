"""
LiteLLM-based LLM client for gws-assistant.
Single entry point for all LLM calls. Handles:
  - Tool-capable model enforcement
  - API key injection per provider
  - Automatic fallback between models on RateLimitError / AuthenticationError
  - API key rotation for OpenRouter (OPENROUTER_API_KEY1/2/3)
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
        if not kwargs["api_key"]:
            raise ValueError(f"Model '{model}' requires GROQ_API_KEY in .env")

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
        api_keys_to_try = (
            config.openrouter_api_keys if model.startswith("openrouter/") and config.openrouter_api_keys else [None]
        )

        for api_key in api_keys_to_try:
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
                logger.warning(
                    f"[LLM] RateLimitError on model={model} "
                    f"key=...{str(api_key)[-6:] if api_key else 'N/A'}. "
                    f"Trying next key/model."
                )
                last_error = e
                continue

            except AuthenticationError as e:
                logger.error(f"[LLM] AuthenticationError on model={model}. Check your API key. Trying next model.")
                last_error = e
                break  # wrong key — skip remaining keys for this model

            except APIConnectionError as e:
                logger.error(f"[LLM] APIConnectionError on model={model}. Cannot reach provider. Trying next model.")
                last_error = e
                break

            except BadRequestError as e:
                logger.error(
                    f"[LLM] BadRequestError on model={model}: {e}. "
                    f"Model may not support tool-calling. Trying next model."
                )
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
