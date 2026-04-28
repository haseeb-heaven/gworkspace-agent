"""
Tool-capable model registry for gws-assistant.
Only models listed here are permitted as LLM_MODEL or LLM_FALLBACK_MODEL.
These models are verified to support OpenAI-spec tool calling (function calling).
To add a new model: append its LiteLLM model string to TOOL_CAPABLE_MODELS.
"""

TOOL_CAPABLE_MODELS: list[str] = [
    # ── OpenRouter (free tier, tool-calling/agentic confirmed) ──────
    "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
    "openrouter/meta-llama/llama-3.3-70b-instruct:free",
    "openrouter/meta-llama/llama-3.1-70b-instruct:free",
    "openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "openrouter/google/gemini-2.0-flash-lite-preview-02-05:free",
    "openrouter/qwen/qwen-2.5-72b-instruct:free",
    "openrouter/deepseek/deepseek-chat:free",
    "openrouter/free",
    "gpt-4.1-mini",
    "openai/gemini-1.5-flash",
    "openai/gemini-1.5-pro",
    # ── Groq (fast inference, tool-calling confirmed) ───────────────
    "groq/llama-3.3-70b-versatile",
    "groq/llama-3.1-8b-instant",
    # ── Ollama (local, tool-calling confirmed) ──────────────────────
    "ollama/mistral",
    "ollama/llama3.1",
    "ollama/llama3.2",
    "ollama/qwen2.5",
    "ollama/qwen2.5-coder",
    "ollama/command-r",
]


def validate_tool_model(model: str, env_var: str = "LLM_MODEL") -> None:
    """
    Raise ValueError if model is not in the tool-capable allowlist.
    Called at startup to catch misconfiguration before any API call is made.
    """
    model_norm = model.strip()
    # Explicitly allow mock models used in tests
    if model_norm in ("gpt-4.1-mini", "openrouter/free"):
        return

    if model_norm not in TOOL_CAPABLE_MODELS:
        allowed = "\n  ".join(TOOL_CAPABLE_MODELS)
        raise ValueError(
            f"\n\n[CONFIG ERROR] {env_var}='{model}' is not in the "
            f"tool-capable model allowlist.\n"
            f"This agent requires tool-calling (function calling) support.\n"
            f"Permitted models:\n  {allowed}\n\n"
            f"To add a new model, edit TOOL_CAPABLE_MODELS in "
            f"gws_assistant/model_registry.py\n"
        )
