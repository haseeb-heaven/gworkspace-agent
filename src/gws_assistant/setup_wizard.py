"""Explicit setup mode for gws and model configuration."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from dotenv import dotenv_values
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from .config import OPENAI_DEFAULT_MODEL, OPENROUTER_DEFAULT_BASE_URL, OPENROUTER_DEFAULT_MODEL

console = Console()


def discover_gws_binary() -> Path | None:
    """Find a local, npm/global, or PATH-provided gws executable."""
    candidates = [
        Path.cwd() / "gws.exe",
        Path.cwd() / "gws",
    ]
    for executable in ("gws", "gws.exe", "google-workspace-cli"):
        discovered = shutil.which(executable)
        if discovered:
            candidates.append(Path(discovered))

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return None


def run_setup_wizard(env_file_path: Path | None = None) -> Path:
    """Collect setup values and write the .env file."""
    env_file = (env_file_path or Path(".env")).expanduser().resolve()
    existing = {key: value or "" for key, value in dotenv_values(env_file).items()} if env_file.exists() else {}
    detected_binary = discover_gws_binary()

    console.print(Panel.fit("Setup runs only because --setup was provided.", title="Google Workspace Setup"))
    if detected_binary:
        console.print(f"[green]Detected gws CLI:[/green] {detected_binary}")
    else:
        console.print("[yellow]No gws CLI binary was detected automatically.[/yellow]")

    default_binary = existing.get("GWS_BINARY_PATH") or str(detected_binary or Path.cwd() / "gws.exe")
    gws_binary_path = Prompt.ask("Path to gws CLI binary", default=default_binary)
    if not gws_binary_path:
        raise RuntimeError("Setup cancelled before gws binary path was saved.")

    provider = Prompt.ask(
        "Which LLM provider should the LangChain planner use?",
        choices=["openrouter", "openai"],
        default=existing.get("LLM_PROVIDER") or "openrouter",
    )
    if not provider:
        raise RuntimeError("Setup cancelled before provider was saved.")

    openai_key = _ask_secret("OpenAI API key (leave blank to keep existing)", existing.get("OPENAI_API_KEY", ""))
    openrouter_key = _ask_secret(
        "OpenRouter API key (leave blank to keep existing)",
        existing.get("OPENROUTER_API_KEY", ""),
    )

    openai_model = _ask_text("OpenAI model", existing.get("OPENAI_MODEL") or OPENAI_DEFAULT_MODEL)
    openai_base_url = _ask_text("OpenAI base URL (optional)", existing.get("OPENAI_BASE_URL", ""), required=False)
    openrouter_model = _ask_text("OpenRouter model", existing.get("OPENROUTER_MODEL") or OPENROUTER_DEFAULT_MODEL)
    openrouter_base_url = _ask_text(
        "OpenRouter base URL",
        existing.get("OPENROUTER_BASE_URL") or OPENROUTER_DEFAULT_BASE_URL,
    )
    tavily_api_key = _ask_secret("Tavily API key for enhanced web search (optional)", existing.get("TAVILY_API_KEY", ""))
    default_recipient = _ask_text(
        "Default recipient email (optional)",
        existing.get("DEFAULT_RECIPIENT_EMAIL", ""),
        required=False,
    )
    code_execution_backend = _ask_text(
        "Code execution backend",
        existing.get("CODE_EXECUTION_BACKEND") or "restricted_subprocess",
    )
    code_execution_enabled = _ask_text(
        "Enable code execution",
        existing.get("CODE_EXECUTION_ENABLED") or "true",
    )
    e2b_api_key = _ask_secret("E2B API key (only needed for backend=e2b)", existing.get("E2B_API_KEY", ""))
    log_level = _ask_text("Log level", existing.get("APP_LOG_LEVEL") or "INFO")
    log_dir = _ask_text("Log directory", existing.get("APP_LOG_DIR") or "logs")
    timeout_seconds = _ask_text("LLM timeout seconds", existing.get("LLM_TIMEOUT_SECONDS") or "30")
    max_retries = _ask_text("Max retries", existing.get("MAX_RETRIES") or "3")

    values = {
        "LLM_PROVIDER": provider,
        "OPENAI_API_KEY": openai_key,
        "OPENAI_MODEL": openai_model,
        "OPENAI_BASE_URL": openai_base_url,
        "OPENROUTER_API_KEY": openrouter_key,
        "OPENROUTER_MODEL": openrouter_model,
        "OPENROUTER_BASE_URL": openrouter_base_url,
        "TAVILY_API_KEY": tavily_api_key,
        "DEFAULT_RECIPIENT_EMAIL": default_recipient,
        "LANGCHAIN_ENABLED": existing.get("LANGCHAIN_ENABLED") or "true",
        "CODE_EXECUTION_ENABLED": code_execution_enabled,
        "CODE_EXECUTION_BACKEND": code_execution_backend,
        "CODE_EXECUTION_TIMEOUT_SECONDS": existing.get("CODE_EXECUTION_TIMEOUT_SECONDS") or "10",
        "CODE_EXECUTION_MEMORY_MB": existing.get("CODE_EXECUTION_MEMORY_MB") or "64",
        "CODE_EXECUTION_MAX_OUTPUT": existing.get("CODE_EXECUTION_MAX_OUTPUT") or "8192",
        "CODE_EXECUTION_DOCKER_IMAGE": existing.get("CODE_EXECUTION_DOCKER_IMAGE") or "gws-sandbox:latest",
        "CODE_EXECUTION_DOCKER_BINARY": existing.get("CODE_EXECUTION_DOCKER_BINARY") or "docker",
        "E2B_API_KEY": e2b_api_key,
        "GWS_BINARY_PATH": str(Path(gws_binary_path).expanduser().resolve()),
        "APP_LOG_LEVEL": log_level.upper(),
        "APP_VERBOSE": existing.get("APP_VERBOSE") or "true",
        "APP_LOG_DIR": log_dir,
        "LLM_TIMEOUT_SECONDS": timeout_seconds,
        "MAX_RETRIES": max_retries,
    }

    env_file.write_text(_render_env(values), encoding="utf-8")
    console.print(Panel.fit(f"Setup saved to {env_file}", title="Setup Complete", border_style="green"))
    return env_file


def _ask_text(prompt: str, default: str, required: bool = True) -> str:
    while True:
        value = Prompt.ask(prompt, default=default)
        if value is None:
            raise RuntimeError(f"Setup cancelled while asking: {prompt}")
        cleaned = value.strip()
        if cleaned or not required:
            return cleaned
        console.print("[yellow]This value cannot be empty.[/yellow]")


def _ask_secret(prompt: str, existing: str) -> str:
    value = Prompt.ask(prompt, password=True)
    if not value and existing:
        return existing.strip()
    if value is None:
        raise RuntimeError(f"Setup cancelled while asking: {prompt}")
    return value.strip()


def _render_env(values: dict[str, str]) -> str:
    lines = [
        "# Generated by python gws_cli.py --setup",
        "# Set to openai or openrouter. If empty, OPENROUTER_API_KEY takes priority.",
        f"LLM_PROVIDER={_quote(values['LLM_PROVIDER'])}",
        "",
        "# OpenAI settings",
        f"OPENAI_API_KEY={_quote(values['OPENAI_API_KEY'])}",
        f"OPENAI_MODEL={_quote(values['OPENAI_MODEL'])}",
        f"OPENAI_BASE_URL={_quote(values['OPENAI_BASE_URL'])}",
        "",
        "# OpenRouter settings",
        f"OPENROUTER_API_KEY={_quote(values['OPENROUTER_API_KEY'])}",
        f"OPENROUTER_MODEL={_quote(values['OPENROUTER_MODEL'])}",
        f"OPENROUTER_BASE_URL={_quote(values['OPENROUTER_BASE_URL'])}",
        "",
        "# Web search settings",
        f"TAVILY_API_KEY={_quote(values['TAVILY_API_KEY'])}",
        "",
        "# Workflow settings",
        f"LANGCHAIN_ENABLED={_quote(values['LANGCHAIN_ENABLED'])}",
        f"CODE_EXECUTION_ENABLED={_quote(values['CODE_EXECUTION_ENABLED'])}",
        f"CODE_EXECUTION_BACKEND={_quote(values['CODE_EXECUTION_BACKEND'])}",
        f"CODE_EXECUTION_TIMEOUT_SECONDS={_quote(values['CODE_EXECUTION_TIMEOUT_SECONDS'])}",
        f"CODE_EXECUTION_MEMORY_MB={_quote(values['CODE_EXECUTION_MEMORY_MB'])}",
        f"CODE_EXECUTION_MAX_OUTPUT={_quote(values['CODE_EXECUTION_MAX_OUTPUT'])}",
        f"CODE_EXECUTION_DOCKER_IMAGE={_quote(values['CODE_EXECUTION_DOCKER_IMAGE'])}",
        f"CODE_EXECUTION_DOCKER_BINARY={_quote(values['CODE_EXECUTION_DOCKER_BINARY'])}",
        f"E2B_API_KEY={_quote(values['E2B_API_KEY'])}",
        f"DEFAULT_RECIPIENT_EMAIL={_quote(values['DEFAULT_RECIPIENT_EMAIL'])}",
        f"MAX_RETRIES={_quote(values['MAX_RETRIES'])}",
        "",
        "# Assistant settings",
        f"GWS_BINARY_PATH={_quote(values['GWS_BINARY_PATH'])}",
        f"APP_LOG_LEVEL={_quote(values['APP_LOG_LEVEL'])}",
        f"APP_VERBOSE={_quote(values['APP_VERBOSE'])}",
        f"APP_LOG_DIR={_quote(values['APP_LOG_DIR'])}",
        f"LLM_TIMEOUT_SECONDS={_quote(values['LLM_TIMEOUT_SECONDS'])}",
        "",
    ]
    return os.linesep.join(lines)


def _quote(value: str) -> str:
    if not value:
        return ""
    escaped = value.replace("'", "\\'")
    return f"'{escaped}'"
