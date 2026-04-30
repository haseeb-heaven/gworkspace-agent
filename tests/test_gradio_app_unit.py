"""Unit tests for gradio_app.py — mocks gradio to allow testing in CI."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

# Mock gradio before importing
mock_gr = MagicMock()
mock_gr.Blocks.return_value.__enter__.return_value = MagicMock()

with patch.dict(sys.modules, {"gradio": mock_gr}):
    # Pre-patch setup_logging before importing
    with patch("gws_assistant.gradio_app.setup_logging"):
        from gws_assistant import gradio_app
        from gws_assistant.gradio_app import GradioAssistant, create_interface


def test_gradio_assistant_run_request():
    planner = MagicMock()
    system = MagicMock()
    executor = MagicMock()
    formatter = MagicMock()
    logger = MagicMock()
    
    assistant = GradioAssistant(
        planner=planner,
        agent_system=system,
        executor=executor,
        formatter=formatter,
        logger=logger
    )
    
    with patch("gws_assistant.gradio_app.AppConfig.from_env") as mock_conf:
        mock_conf.return_value.log_level = "INFO"
        mock_conf.return_value.log_file_path = "test.log"
        with patch("gws_assistant.langgraph_workflow.run_workflow") as mock_run:
            mock_run.return_value = "success output"
            out, plan = assistant.run_request("test")
            assert out == "success output"
            assert "LangGraph" in plan

def test_gradio_assistant_empty_request():
    assistant = GradioAssistant(
        planner=MagicMock(),
        agent_system=MagicMock(),
        executor=MagicMock(),
        formatter=MagicMock(),
        logger=MagicMock()
    )
    out, plan = assistant.run_request("")
    assert "Enter a request" in out

def test_create_interface():
    with patch("gws_assistant.gradio_app.AppConfig.from_env") as mock_conf:
        mock_conf.return_value.log_level = "INFO"
        mock_conf.return_value.log_file_path = "test.log"
        with patch("gws_assistant.gradio_app.setup_logging"):
            with patch("gws_assistant.gradio_app.GWSRunner"):
                with patch("gws_assistant.gradio_app.WorkspaceAgentSystem"):
                    with patch("gws_assistant.gradio_app.PlanExecutor"):
                        demo = create_interface()
                        assert demo is not None
                        # Check if gradio functions were called
                        assert mock_gr.Blocks.called
                        assert mock_gr.Textbox.called
                        assert mock_gr.Button.called
