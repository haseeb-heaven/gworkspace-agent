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
from .intent_parser import IntentParser
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
        value = Prompt.ask(spec.prompt, default=default)
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


def _collect_task_parameters(
    engine: ConversationEngine,
    task: PlannedTask,
) -> PlannedTask:
    collected = dict(task.parameters)
    for spec in engine.parameter_specs(task.service, task.action):
        value = collected.get(spec.name)
        if value is not None and str(value).strip():
            continue
        if not spec.required:
            continue
        collected[spec.name] = _ask_non_empty(spec.prompt, default=spec.example)
    return PlannedTask(
        id=task.id,
        service=task.service,
        action=task.action,
        parameters=collected,
        reason=task.reason,
    )


def _save_output(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text.rstrip() + "\n\n")


def _run_application(save_output: Path | None = None, task: str | None = None) -> None:
    """Runs the terminal assistant (interactive or single-task)."""
    config = AppConfig.from_env()
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

    parser = IntentParser(config=config, logger=logger)
    planner = CommandPlanner()
    engine = ConversationEngine(parser=parser, planner=planner, logger=logger)
    agent_system = WorkspaceAgentSystem(config=config, logger=logger)
    runner = GWSRunner(config.gws_binary_path, logger=logger)
    executor = PlanExecutor(planner=planner, runner=runner, logger=logger)
    formatter = HumanReadableFormatter()

    if not runner.validate_binary():
        console.print(
            Panel.fit(
                f"[red]gws binary not found at:[/red]\n{config.gws_binary_path}\n"
                "Run python cli.py --setup to configure it.",
                title="Setup Error",
            )
        )
        raise typer.Exit(code=1)
    if not config.api_key:
        console.print(
            Panel.fit(
                "No LLM API key is configured. CrewAI planning will fall back to local heuristics.",
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

            plan = agent_system.plan(user_text)
            logger.info(
                "Agent plan source=%s tasks=%s summary=%s",
                plan.source,
                [f"{task.service}.{task.action}" for task in plan.tasks],
                plan.summary,
            )
            if plan.no_service_detected or not plan.tasks:
                console.print(f"[yellow]{NO_SERVICE_MESSAGE}[/yellow]")
                if task:
                    break
                continue

            plan.tasks = [_collect_task_parameters(engine, task) for task in plan.tasks]
            report = executor.execute(plan)
            output = formatter.format_report(report)
            if save_output:
                _save_output(save_output, output)
            console.print(Panel(output, title="Success" if report.success else "Error", border_style="green" if report.success else "red"))

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
    setup: bool = typer.Option(False, "--setup", help="Run setup mode and save configuration."),
    save_output: Path | None = typer.Option(None, "--save-output", help="Append readable output to a file."),
    task: str | None = typer.Option(None, "--task", help="Execute a single task and exit."),
) -> None:
    """Default command: run app. Use --setup to configure it."""
    if setup:
        run_setup_wizard()
        return
    _run_application(save_output=save_output, task=task)


def main() -> None:
    """Entry point for console scripts."""
    app()


if __name__ == "__main__":
    main()
