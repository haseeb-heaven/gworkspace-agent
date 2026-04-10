"""Terminal UI CLI app."""

from __future__ import annotations

import logging
from typing import Any

import questionary
import typer
from rich.console import Console
from rich.panel import Panel

from .config import AppConfig
from .conversation import ConversationEngine
from .exceptions import ValidationError
from .gws_runner import GWSRunner
from .intent_parser import IntentParser
from .logging_utils import setup_logging
from .planner import CommandPlanner

app = typer.Typer(no_args_is_help=False, help="Google Workspace Assistant CLI")
console = Console()


def _ask_non_empty(prompt: str, default: str | None = None) -> str:
    while True:
        answer = questionary.text(prompt, default=default or "").ask()
        if answer is None:
            continue
        cleaned = answer.strip()
        if cleaned:
            return cleaned
        console.print("[yellow]This value cannot be empty.[/yellow]")


def _pick_service(engine: ConversationEngine) -> str:
    services = engine.planner.list_services()
    choice = questionary.select("Which Google service do you want to use?", choices=services).ask()
    if not choice:
        raise ValidationError("Service selection was cancelled.")
    return choice


def _pick_action(engine: ConversationEngine, service: str) -> str:
    actions = engine.action_choices(service)
    choice = questionary.select("Which action should I run?", choices=actions).ask()
    if not choice:
        raise ValidationError("Action selection was cancelled.")
    return choice


def _collect_parameters(
    engine: ConversationEngine,
    service: str,
    action: str,
    existing: dict[str, Any],
) -> dict[str, Any]:
    collected = dict(existing)
    specs = engine.parameter_specs(service, action)
    for spec in specs:
        default = str(existing.get(spec.name) or "").strip() or spec.example
        value = questionary.text(spec.prompt, default=default).ask()
        if value is None:
            if spec.required:
                raise ValidationError(f"Required parameter missing: {spec.name}")
            continue
        if spec.required and not value.strip():
            raise ValidationError(f"Required parameter missing: {spec.name}")
        cleaned = value.strip()
        if cleaned:
            collected[spec.name] = cleaned
    return collected


@app.command()
def run() -> None:
    """Runs the interactive terminal assistant."""
    config = AppConfig.from_env()
    logger = setup_logging(config)
    logger.info("Starting CLI application.")

    parser = IntentParser(config=config, logger=logger)
    planner = CommandPlanner()
    engine = ConversationEngine(parser=parser, planner=planner, logger=logger)
    runner = GWSRunner(config.gws_binary_path, logger=logger)

    if not runner.validate_binary():
        console.print(
            Panel.fit(
                f"[red]gws binary not found at:[/red]\n{config.gws_binary_path}\n"
                "Set GWS_BINARY_PATH in your .env file.",
                title="Setup Error",
            )
        )
        raise typer.Exit(code=1)

    console.print(Panel.fit("Google Workspace Assistant CLI is ready.", title="Welcome"))

    while True:
        try:
            user_text = _ask_non_empty("What do you want to do?")
            if user_text.lower() in {"exit", "quit", "q"}:
                console.print("[green]Goodbye.[/green]")
                break

            intent = engine.parse_user_request(user_text)
            service = intent.service
            if engine.needs_service_clarification(intent):
                console.print(f"[yellow]{engine.service_clarification_message()}[/yellow]")
                service = _pick_service(engine)

            action = intent.action
            try:
                if not service:
                    raise ValidationError("Service could not be determined.")
                engine.validate_selection(service, action)
            except ValidationError:
                action = _pick_action(engine, service)

            if not service or not action:
                raise ValidationError("Both service and action are required.")

            params = _collect_parameters(engine, service, action, intent.parameters)
            args = engine.build_command(service, action, params)
            result = runner.run(args)

            if result.success:
                console.print(Panel(engine.format_result(result), title="Success", border_style="green"))
            else:
                console.print(Panel(engine.format_result(result), title="Error", border_style="red"))

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user. Exiting.[/yellow]")
            break
        except ValidationError as exc:
            logger.warning("Validation error: %s", exc)
            console.print(f"[red]{exc}[/red]")
        except Exception as exc:
            logger.exception("Unexpected CLI error: %s", exc)
            console.print(f"[red]Unexpected error: {exc}[/red]")


def main() -> None:
    """Entry point for console scripts."""
    app()

