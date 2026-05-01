"""Unit tests for gui_app.py — mocks customtkinter to allow instantiation in CI."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

# Mock customtkinter and tkinter before importing AssistantGUI
mock_ctk = MagicMock()
mock_tk = MagicMock()

class MockCTk:
    def __init__(self, *args, **kwargs): pass
    def title(self, *args, **kwargs): pass
    def geometry(self, *args, **kwargs): pass
    def grid_columnconfigure(self, *args, **kwargs): pass
    def grid_rowconfigure(self, *args, **kwargs): pass
    def bind(self, *args, **kwargs): pass
    def winfo_children(self): return []
    def mainloop(self): pass

mock_ctk.CTk = MockCTk
mock_ctk.set_appearance_mode = MagicMock()
mock_ctk.set_default_color_theme = MagicMock()

# Permanently patch sys.modules for this test session to avoid TclError
sys.modules["customtkinter"] = mock_ctk
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.messagebox"] = MagicMock()

def test_gui_instantiation():
    with patch("gws_assistant.gui_app.AppConfig.from_env") as mock_config_loader:
        mock_config = MagicMock()
        mock_config.gws_binary_path = "gws"
        mock_config.verbose = False
        mock_config.log_level = "INFO"
        mock_config.log_file_path = "test.log"
        mock_config_loader.return_value = mock_config
        
        with patch("gws_assistant.gui_app.setup_logging"):
            with patch("gws_assistant.gui_app.IntentParser"):
                with patch("gws_assistant.gui_app.CommandPlanner"):
                    with patch("gws_assistant.gui_app.GWSRunner"):
                        from gws_assistant.gui_app import AssistantGUI
                        gui = AssistantGUI()
                        assert gui is not None

def test_gui_append_output():
    with patch("gws_assistant.gui_app.AppConfig.from_env") as mock_conf:
        mock_conf.return_value.log_level = "INFO"
        mock_conf.return_value.log_file_path = "test.log"
        with patch("gws_assistant.gui_app.setup_logging"):
            with patch("gws_assistant.gui_app.IntentParser"):
                with patch("gws_assistant.gui_app.CommandPlanner"):
                    with patch("gws_assistant.gui_app.GWSRunner"):
                        from gws_assistant.gui_app import AssistantGUI
                        gui = AssistantGUI()
                        gui.output_box = MagicMock()
                        gui._append_output("test message")
                        gui.output_box.insert.assert_called_with("end", "test message\n")

def test_gui_refresh_parameter_fields():
    with patch("gws_assistant.gui_app.AppConfig.from_env") as mock_conf:
        mock_conf.return_value.log_level = "INFO"
        mock_conf.return_value.log_file_path = "test.log"
        with patch("gws_assistant.gui_app.setup_logging"):
            from gws_assistant.gui_app import AssistantGUI
            gui = AssistantGUI()
            gui.params_frame = MagicMock()
            gui.current_parameters = {"a": "b"}
            gui.service_var = MagicMock()
            gui.action_var = MagicMock()
            gui.engine = MagicMock()
            gui._refresh_parameter_fields()
            assert gui.current_parameters == {}
            # Check if it tried to destroy children
            assert gui.params_frame.winfo_children.called
