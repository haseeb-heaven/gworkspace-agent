"""
Tool-capable model registry for gws-assistant.
Only models listed here are permitted as LLM_MODEL or LLM_FALLBACK_MODEL.
These models are verified to support OpenAI-spec tool calling (function calling).
To add a new model: append its LiteLLM model string to TOOL_CAPABLE_MODELS.
"""

TOOL_CAPABLE_MODELS: list[str] = [
    # ── OpenAI (agentic tool-calling confirmed) ────────────────────
    "gpt-4.1-mini",
    "openai/gpt-4.1",
    "openai/gpt-4o",
    "openai/gpt-5-mini",
    "openai/gpt-5.2",
    "openai/gpt-5.4",
    "openai/o1-preview",
    "openai/o3-mini",
    # ── Anthropic Claude (top agentic benchmarks) ───────────────────
    "anthropic/claude-3-7-sonnet-20250219",
    "anthropic/claude-4-opus-202604",
    "anthropic/claude-3-5-sonnet-20241022",
    # ── xAI Grok (agentic, tool-calling, reasoning) ─────────────────
    "xai/grok-4-1-fast-reasoning",
    "xai/grok-4-1-fast-non-reasoning",
    "xai/grok-4",
    "xai/grok-4-20",
    # ── OpenRouter (tool-calling) ──────────────────────────────────
    "openrouter/free",
    # ── Google Gemini (tool support) ────────────────────────────────
    "google/gemini-2.0-flash",
    "google/gemini-2.0-pro-exp-02-05",
    "google/gemini-1.5-flash",
    "google/gemini-1.5-pro",
    "gemini/gemini-flash-latest",
    "gemini/gemini-flash-lite-latest",
    "gemini/gemini-pro-latest",
    "gemini/gemini-2.5-flash",
    "gemini/gemini-2.5-pro",
    "gemini/gemini-2.0-flash",
    "gemini/gemini-2.0-flash-exp",
    "gemini/gemini-2.0-pro-exp-02-05",
    "gemini/gemini-1.5-flash",
    "gemini/gemini-1.5-pro",
    # ── Meta Llama (via LiteLLM providers) ──────────────────────────
    "meta-llama/llama-3.3-70b-instruct",
    "meta-llama/llama-4-70b-instruct",
    # ── Mistral AI (strong tool use) ────────────────────────────────
    "mistral-large-3",
    "mistral/mistral-nemo",
    # ── Cohere (RAG + tool optimized) ──────────────────────────────
    "cohere/command-r-plus",
    "cohere/command-a-03-2026",
    # ── DeepSeek (reasoning + tools) ───────────────────────────────
    "deepseek/deepseek-r1",
    "deepseek/deepseek-chat",
    # ── OpenRouter (free tier, tool-calling/agentic confirmed) ──────
    "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
    "openrouter/meta-llama/llama-3.3-70b-instruct:free",
    "openrouter/meta-llama/llama-3.1-70b-instruct:free",
    "openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "openrouter/google/gemini-2.0-flash-lite-preview-02-05:free",
    "openrouter/qwen/qwen-2.5-72b-instruct:free",
    "openrouter/qwen/qwen3-next-80b-a3b-instruct:free",
    "openrouter/deepseek/deepseek-chat:free",
    "openrouter/nvidia/nemotron-super-49b-v1:free",
    "openrouter/nvidia/llama-3.3-nemotron-super-49b-v1:free",
    "openrouter/groq/llama-3.3-70b-versatile",
    "openrouter/groq/llama-3.1-70b-versatile",
    "openrouter/groq/llama-3.1-8b-instant",
    "openrouter/groq/llama-3.1-8b-instant:free",
    # ── Groq (fast inference, tool-calling confirmed) ───────────────
    "groq/llama-3.3-70b-versatile",
    "groq/llama-3.1-8b-instant",
    # ── Cerebras (fast inference, tool-calling confirmed) ───────────
    "cerebras/llama3.1-70b",
    "cerebras/llama3.1-8b",
    "cerebras/llama-3.3-70b",

    # ── Ollama (local, tool-calling confirmed) ──────────────────────
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
