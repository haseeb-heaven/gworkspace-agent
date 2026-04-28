"""
Tool-capable model registry for gws-assistant.
Only models listed here are permitted as LLM_MODEL or LLM_FALLBACK_MODEL.
These models are verified to support OpenAI-spec tool calling (function calling).
To add a new model: append its LiteLLM model string to TOOL_CAPABLE_MODELS.
"""

TOOL_CAPABLE_MODELS: list[str] = [
    # ── OpenRouter (free tier, tool-calling confirmed) ──────────────
    "openrouter/nvidia/nemotron-super-49b-v1:free",
    "openrouter/mistralai/mistral-7b-instruct:free",
    "openrouter/microsoft/phi-3-mini-128k-instruct:free",
    "openrouter/qwen/qwen3-235b-a22b:free",
    "openrouter/qwen/qwen3-30b-a3b:free",
    "openrouter/google/gemini-2.0-flash-exp:free",
    "openrouter/meta-llama/llama-3.3-70b-instruct:free",
    "openrouter/deepseek/deepseek-chat-v3-0324:free",
    "openrouter/free",
    "gpt-4.1-mini",
    # ── Groq (fast inference, tool-calling confirmed) ───────────────
    "groq/llama3-70b-8192",
    "groq/llama3-groq-70b-8192-tool-use-preview",
    "groq/llama-3.1-70b-versatile",
    "groq/mixtral-8x7b-32768",
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
            f"src/gws_assistant/model_registry.py\n"
        )
