"""Terminal UI CLI app."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from .agent_system import NO_SERVICE_MESSAGE, WorkspaceAgentSystem
from .config import AppConfig
from .conversation import ConversationEngine
from .execution import PlanExecutor
from .exceptions import ValidationError
from .gws_runner import GWSRunner
from .logging_utils import setup_logging
from .models import PlannedTask
from .output_formatter import HumanReadableFormatter
from .planner import CommandPlanner
from .setup_wizard import run_setup_wizard

app = typer.Typer(invoke_without_command=True, no_args_is_help=False, help="Google Workspace Assistant CLI")
console = Console()


def _ask_non_empty(prompt: str, default: str | None = None) -> str:
    while True:
        if default:
            answer = Prompt.ask(prompt, default=default)
        else:
            answer = Prompt.ask(prompt)
        if answer is None:
            continue
        cleaned = answer.strip()
        if cleaned:
            return cleaned
        console.print("[yellow]This value cannot be empty.[/yellow]")


def _pick_service(engine: ConversationEngine) -> str:
    services = engine.planner.list_services()
    choice = Prompt.ask("Which Google service do you want to use?", choices=services)
    if not choice:
        raise ValidationError("Service selection was cancelled.")
    return choice


def _pick_action(engine: ConversationEngine, service: str) -> str:
    actions = engine.action_choices(service)
    choice = Prompt.ask("Which action should I run?", choices=actions)
    if not choice:
        raise ValidationError("Action selection was cancelled.")
    return choice


def _save_output(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text.rstrip() + "\n\n")


from .langgraph_workflow import run_workflow

def _run_application(save_output: Path | None = None, task: str | None = None, no_langchain: bool = False) -> None:
    """Runs the terminal assistant (interactive or single-task)."""
    config = AppConfig.from_env()
    if no_langchain:
         config.api_key = None
         config.langchain_enabled = False

    logger = setup_logging(config)
    logger.info("Starting CLI application.")

    if not config.setup_complete:
        console.print(
            Panel.fit(
                f"[red]Setup is missing or incomplete.[/red]\n"
                f"Expected config file: {config.env_file_path}\n"
                f"Expected gws binary: {config.gws_binary_path}\n\n"
                "Run setup explicitly with:\npython cli.py --setup",
                title="Setup Required",
            )
        )
        raise typer.Exit(code=1)

    planner = CommandPlanner()
    engine = ConversationEngine(planner=planner, logger=logger)
    agent_system = WorkspaceAgentSystem(config=config, logger=logger)
    runner = GWSRunner(config.gws_binary_path, logger=logger)
    executor = PlanExecutor(planner=planner, runner=runner, logger=logger)

    if not runner.validate_binary():
        console.print(
            Panel.fit(
                f"[red]gws binary not found at:[/red]\n{config.gws_binary_path}\n"
                "Run python cli.py --setup to configure it.",
                title="Setup Error",
            )
        )
        raise typer.Exit(code=1)
    if not config.api_key and config.langchain_enabled:
        console.print(
            Panel.fit(
                "No LLM API key is configured. Planning will fall back to local heuristics.",
                title="Model Warning",
                border_style="yellow",
            )
        )

    console.print(Panel.fit("Google Workspace Agent.", title="Welcome"))

    while True:
        try:
            if task:
                user_text = task
            else:
                user_text = _ask_non_empty(">: ")

            if user_text.lower() in {"exit", "quit", "q"}:
                console.print("[green]Goodbye.[/green]")
                break

            output = run_workflow(user_text, config, agent_system, executor, logger)

            if save_output:
                _save_output(save_output, output)
            console.print(Panel(output, title="Result", border_style="green"))

            if task:
                break

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user. Exiting.[/yellow]")
            break
        except ValidationError as exc:
            logger.warning("Validation error: %s", exc)
            console.print(f"[red]{exc}[/red]")
        except Exception as exc:
            logger.exception("Unexpected CLI error: %s", exc)
            console.print(f"[red]Unexpected error: {exc}[/red]")


@app.callback(invoke_without_command=True)
def run(
    ctx: typer.Context,
    setup: bool = typer.Option(False, "--setup", help="Run setup mode and save configuration."),
    save_output: Path | None = typer.Option(None, "--save-output", help="Append readable output to a file."),
    task: str | None = typer.Option(None, "--task", help="Execute a single task and exit."),
    no_langchain: bool = typer.Option(False, "--no-langchain", help="Disable LangChain and force heuristic mode."),
) -> None:
    """Default command: run app. Use --setup to configure it."""
    # Typer sets resilient_parsing=True during --help and shell-completion
    # resolution. Returning early prevents _run_application() from being
    # invoked (which would block on stdin / validate binaries / etc.).
    if ctx.resilient_parsing:
        return
    if setup:
        run_setup_wizard()
        return
    _run_application(save_output=save_output, task=task, no_langchain=no_langchain)


def main() -> None:
    """Entry point for console scripts."""
    app()


if __name__ == "__main__":
    main()
