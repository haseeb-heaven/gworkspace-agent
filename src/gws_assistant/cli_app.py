"""Terminal UI CLI app."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from .exceptions import ValidationError
from .logging_utils import setup_logging
from .setup_wizard import run_setup_wizard

app = typer.Typer(invoke_without_command=True, no_args_is_help=False, help="Google Workspace Assistant CLI")
# Specifically force UTF-8 for Windows environments to avoid 'charmap' encoding errors.
console = Console(force_terminal=True, legacy_windows=False)


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


def _pick_service(engine: Any) -> str:
    services = engine.planner.list_services()
    choice = Prompt.ask("Which Google service do you want to use?", choices=services)
    if not choice:
        raise ValidationError("Service selection was cancelled.")
    return choice


def _pick_action(engine: Any, service: str) -> str:
    actions = engine.action_choices(service)
    choice = Prompt.ask("Which action should I run?", choices=actions)
    if not choice:
        raise ValidationError("Action selection was cancelled.")
    return choice


def _save_output(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text.rstrip() + "\n\n")


def _run_application(
    save_output: Path | None = None,
    task: str | None = None,
    no_langchain: bool = False,
    sandbox: bool | None = None,
    read_only: bool | None = None,
    dry_run: bool = False,
    no_confirm: bool = False,
    force_dangerous: bool = False,
    is_telegram: bool = False,
) -> None:
    """Runs the terminal assistant (interactive or single-task)."""
    # Heavy imports are deferred here so that importing cli_app at the
    # module level (e.g. for --help) does not trigger the full
    # langchain / transformers / numpy chain.
    from .agent_system import NO_SERVICE_MESSAGE, WorkspaceAgentSystem  # noqa: F401
    from .config import AppConfig
    from .execution import PlanExecutor
    from .gws_runner import GWSRunner
    from .langgraph_workflow import run_workflow
    from .models import PlannedTask  # noqa: F401
    from .output_formatter import HumanReadableFormatter  # noqa: F401
    from .planner import CommandPlanner

    config = AppConfig.from_env()
    if no_langchain:
        config.api_key = None
        config.langchain_enabled = False

    # Runtime overrides
    if sandbox is not None:
        config.sandbox_enabled = sandbox
    if read_only is not None:
        config.read_only_mode = read_only
    if dry_run:
        config.dry_run = dry_run
    if no_confirm:
        config.no_confirm = no_confirm
    if force_dangerous:
        config.force_dangerous = force_dangerous
    if is_telegram:
        config.is_telegram = is_telegram

    logger = setup_logging(config)
    logger.info("Starting CLI application.")

    if not config.setup_complete:
        console.print(
            Panel.fit(
                f"[red]Setup is missing or incomplete.[/red]\n"
                f"Expected config file: {config.env_file_path}\n"
                f"Expected gws binary: {config.gws_binary_path}\n\n"
                "Run setup explicitly with:\npython gws_cli.py --setup",
                title="Setup Required",
            )
        )
        raise typer.Exit(code=1)

    planner = CommandPlanner()
    agent_system = WorkspaceAgentSystem(config=config, logger=logger)
    runner = GWSRunner(config.gws_binary_path, logger=logger, config=config)
    executor = PlanExecutor(planner=planner, runner=runner, logger=logger, config=config)

    if not runner.validate_binary():
        console.print(
            Panel.fit(
                f"[red]gws binary not found at:[/red]\n{config.gws_binary_path}\n"
                "Run python gws_cli.py --setup to configure it.",
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
    send_telegram: str | None = typer.Option(None, "--send-telegram", help="Send a message to Telegram and exit."),
    sandbox: bool | None = typer.Option(
        None,
        "--sandbox/--no-sandbox",
        help="Enable or disable sandbox mode (intercepts writes/deletes). Default: env or true.",
    ),
    read_only: bool | None = typer.Option(
        None, "--read-only/--read-write", help="Force read-only mode (blocks all writes/deletes). Default: env or true."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Log destructive actions without executing them."),
    no_confirm: bool = typer.Option(False, "--no-confirm", help="Skip confirmation prompts for destructive actions."),
    force_dangerous: bool = typer.Option(False, "--force-dangerous", help="Allow plans with multiple destructive actions."),
    is_telegram: bool = typer.Option(False, "--is-telegram", hidden=True, help="Internal flag: denotes running from Telegram."),
) -> None:
    """Default command: run app. Use --setup to configure it."""
    # resilient_parsing is True during --help rendering and shell-completion;
    # returning early prevents any I/O, binary validation, or blocking stdin.
    if ctx.resilient_parsing:
        return
    if setup:
        run_setup_wizard()
        return
    if send_telegram:
        from .tools.telegram import send_telegram as st

        st(send_telegram)
        return

    from gws_assistant.exceptions import SafetyConfirmationRequired
    import json
    import sys

    try:
        _run_application(
            save_output=save_output,
            task=task,
            no_langchain=no_langchain,
            sandbox=sandbox,
            read_only=read_only,
            dry_run=dry_run,
            no_confirm=no_confirm,
            force_dangerous=force_dangerous,
            is_telegram=is_telegram,
        )
    except SafetyConfirmationRequired as e:
        print(
            json.dumps(
                {"status": "confirmation_required", "action": e.action_name, "details": e.details}
            )
        )
        sys.exit(2)


def main() -> None:
    """Entry point for console scripts."""
    if sys.platform == "win32":
        import io

        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    app()


if __name__ == "__main__":
    main()
