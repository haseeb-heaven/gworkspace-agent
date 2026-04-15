"""Browser-based GUI using Gradio."""
from __future__ import annotations

import logging
import os
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

        from .langgraph_workflow import run_workflow
        output = run_workflow(text, config=AppConfig.from_env(), system=self.agent_system, executor=self.executor, logger=self.logger)
        return output, "Plan tracking handled by LangGraph workflow."


def create_interface() -> gr.Blocks:
    config = AppConfig.from_env()
    logger = setup_logging(config)

    # In Cloud Run / containerised environments setup_complete may be False
    # because there is no interactive wizard.  We log a warning but continue
    # so the UI can still start up.
    if not config.setup_complete:
        logger.warning(
            "setup_complete is False (no .env or gws binary found via wizard). "
            "Continuing anyway – environment variables should supply all config."
        )

    runner = GWSRunner(config.gws_binary_path, logger=logger, config=config)
    if not runner.validate_binary():
        logger.warning(
            f"gws binary not found at {config.gws_binary_path}. "
            "GWS commands will fail, but the UI will still start."
        )

    planner = CommandPlanner()
    assistant = GradioAssistant(
        planner=planner,
        agent_system=WorkspaceAgentSystem(config=config, logger=logger),
        executor=PlanExecutor(planner=planner, runner=runner, logger=logger, config=config),
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


def main(host: str = "0.0.0.0", port: int = int(os.environ.get("PORT", 8080)), share: bool = False) -> None:
    interface = create_interface()
    interface.launch(server_name=host, server_port=port, share=share)
