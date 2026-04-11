"""Browser-based GUI using Gradio."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import gradio as gr

from .agent_system import NO_SERVICE_MESSAGE, WorkspaceAgentSystem
from .config import AppConfig
from .execution import PlanExecutor
from .gws_runner import GWSRunner
from .logging_utils import setup_logging
from .output_formatter import HumanReadableFormatter
from .planner import CommandPlanner
from .service_catalog import SERVICES


@dataclass(slots=True)
class GradioAssistant:
    planner: CommandPlanner
    agent_system: WorkspaceAgentSystem
    executor: PlanExecutor
    formatter: HumanReadableFormatter
    logger: logging.Logger

    def run_request(self, user_text: str) -> tuple[str, str]:
        text = (user_text or "").strip()
        if not text:
            return "Enter a request to continue.", ""

        plan = self.agent_system.plan(text)
        self.logger.info(
            "Gradio request planned source=%s tasks=%s",
            plan.source,
            [f"{task.service}.{task.action}" for task in plan.tasks],
        )
        if plan.no_service_detected or not plan.tasks:
            return NO_SERVICE_MESSAGE, ""

        missing = self._missing_required_parameters(plan.tasks)
        if missing:
            return (
                "I need more details before running this request:\n" + "\n".join(f"- {item}" for item in missing),
                _render_plan(plan),
            )

        report = self.executor.execute(plan)
        output = self.formatter.format_report(report)
        return output, _render_plan(plan)

    def _missing_required_parameters(self, tasks: list[Any]) -> list[str]:
        missing: list[str] = []
        for task in tasks:
            service_spec = SERVICES.get(task.service)
            action_spec = service_spec.actions.get(task.action) if service_spec else None
            if not action_spec:
                continue
            for parameter in action_spec.parameters:
                value = task.parameters.get(parameter.name)
                if parameter.required and not _is_value_supplied(value):
                    missing.append(f"{task.service}.{task.action}: {parameter.name}")
        return missing


def create_interface() -> gr.Blocks:
    config = AppConfig.from_env()
    logger = setup_logging(config)
    if not config.setup_complete:
        raise RuntimeError(
            "Setup is missing. Run python cli.py --setup first so .env and GWS_BINARY_PATH are configured."
        )
    runner = GWSRunner(config.gws_binary_path, logger=logger)
    if not runner.validate_binary():
        raise RuntimeError(f"gws binary not found at {config.gws_binary_path}. Run python cli.py --setup.")
    planner = CommandPlanner()

    assistant = GradioAssistant(
        planner=planner,
        agent_system=WorkspaceAgentSystem(config=config, logger=logger),
        executor=PlanExecutor(planner=planner, runner=runner, logger=logger),
        formatter=HumanReadableFormatter(),
        logger=logger,
    )

    with gr.Blocks(title="Google Workspace Assistant") as demo:
        gr.Markdown("# Google Workspace Assistant")
        gr.Markdown("Describe your Google Workspace task in natural language.")
        with gr.Row():
            request = gr.Textbox(
                label="Request",
                lines=4,
                placeholder="Example: List all emails from assistant@glider.ai and show details",
            )
        with gr.Row():
            run_button = gr.Button("Run")
            clear_button = gr.Button("Clear")
        output = gr.Textbox(label="Result", lines=18)
        plan_preview = gr.Textbox(label="Planned Tasks", lines=8)

        run_button.click(fn=assistant.run_request, inputs=[request], outputs=[output, plan_preview])
        request.submit(fn=assistant.run_request, inputs=[request], outputs=[output, plan_preview])
        clear_button.click(fn=lambda: ("", "", ""), outputs=[request, output, plan_preview])
    return demo


def main(host: str = "127.0.0.1", port: int = 7860, share: bool = False) -> None:
    interface = create_interface()
    interface.launch(server_name=host, server_port=port, share=share)


def _is_value_supplied(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        if not value.strip():
            return False
        if value.strip().startswith("$"):
            return True
        return True
    return True


def _render_plan(plan: Any) -> str:
    rows = [f"Source: {plan.source}", f"Summary: {plan.summary or 'n/a'}", ""]
    for index, task in enumerate(plan.tasks, start=1):
        rows.append(f"{index}. {task.service}.{task.action}")
        if task.parameters:
            rows.append(f"   params: {task.parameters}")
        if task.reason:
            rows.append(f"   reason: {task.reason}")
    return "\n".join(rows).strip()
