"""Unit tests for gui_app.py — mocks customtkinter to allow instantiation in CI."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

# Mock customtkinter and tkinter before importing AssistantGUI
mock_ctk = MagicMock()
mock_tk = MagicMock()

with patch.dict(sys.modules, {"customtkinter": mock_ctk, "tkinter": mock_tk, "tkinter.messagebox": MagicMock()}):
    # We need to ensure AssistantGUI can inherit from a mock
    mock_ctk.CTk = MagicMock
    from gws_assistant.gui_app import AssistantGUI

def test_gui_instantiation():
    with patch("gws_assistant.gui_app.AppConfig.from_env") as mock_config_loader:
        mock_config = MagicMock()
        mock_config.gws_binary_path = "gws"
        mock_config.verbose = False
        mock_config_loader.return_value = mock_config
        
        with patch("gws_assistant.gui_app.setup_logging"):
            with patch("gws_assistant.gui_app.IntentParser"):
                with patch("gws_assistant.gui_app.CommandPlanner"):
                    with patch("gws_assistant.gui_app.GWSRunner"):
                        # This should at least run the constructor logic
                        gui = AssistantGUI()
                        assert gui is not None

def test_gui_append_output():
    with patch("gws_assistant.gui_app.AppConfig.from_env"):
        with patch("gws_assistant.gui_app.setup_logging"):
            with patch("gws_assistant.gui_app.IntentParser"):
                with patch("gws_assistant.gui_app.CommandPlanner"):
                    with patch("gws_assistant.gui_app.GWSRunner"):
                        gui = AssistantGUI()
                        gui.output_box = MagicMock()
                        gui._append_output("test message")
                        gui.output_box.insert.assert_called_with("end", "test message\n")

def test_gui_clear_params():
    with patch("gws_assistant.gui_app.AppConfig.from_env"):
        with patch("gws_assistant.gui_app.setup_logging"):
            gui = AssistantGUI()
            gui.params_frame = MagicMock()
            gui.current_parameters = {"a": "b"}
            gui._clear_params_ui()
            assert gui.current_parameters == {}
            # Check if it tried to destroy children
            assert gui.params_frame.winfo_children.called
