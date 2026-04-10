"""Professional GUI app using CustomTkinter."""

from __future__ import annotations

import logging
import tkinter.messagebox as messagebox
from typing import Any

import customtkinter as ctk

from .config import AppConfig
from .conversation import ConversationEngine
from .exceptions import ValidationError
from .gws_runner import GWSRunner
from .intent_parser import IntentParser
from .logging_utils import setup_logging
from .planner import CommandPlanner


class AssistantGUI(ctk.CTk):
    """Desktop GUI for Google Workspace assistant."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Google Workspace Assistant")
        self.geometry("980x700")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.config_model = AppConfig.from_env()
        self.logger = setup_logging(self.config_model)
        self.parser = IntentParser(config=self.config_model, logger=self.logger)
        self.planner = CommandPlanner()
        self.engine = ConversationEngine(parser=self.parser, planner=self.planner, logger=self.logger)
        self.runner = GWSRunner(self.config_model.gws_binary_path, logger=self.logger)

        self.current_parameters: dict[str, ctk.CTkEntry] = {}

        self._build_layout()
        self._bind_events()
        self._check_binary()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        title = ctk.CTkLabel(self, text="Google Workspace Assistant", font=("Segoe UI", 26, "bold"))
        title.grid(row=0, column=0, sticky="w", padx=20, pady=(16, 8))

        self.input_box = ctk.CTkTextbox(self, height=100)
        self.input_box.grid(row=1, column=0, sticky="ew", padx=20, pady=8)
        self.input_box.insert("1.0", "Example: show my latest Google Drive files")

        controls = ctk.CTkFrame(self)
        controls.grid(row=2, column=0, sticky="ew", padx=20, pady=8)
        controls.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.analyze_button = ctk.CTkButton(controls, text="Analyze Request", command=self._analyze_request)
        self.analyze_button.grid(row=0, column=0, padx=8, pady=8, sticky="ew")

        self.service_var = ctk.StringVar(value="drive")
        self.service_menu = ctk.CTkOptionMenu(
            controls,
            variable=self.service_var,
            values=self.planner.list_services(),
            command=self._on_service_changed,
        )
        self.service_menu.grid(row=0, column=1, padx=8, pady=8, sticky="ew")

        self.action_var = ctk.StringVar(value="")
        self.action_menu = ctk.CTkOptionMenu(
            controls,
            variable=self.action_var,
            values=[""],
            command=self._on_action_changed,
        )
        self.action_menu.grid(row=0, column=2, padx=8, pady=8, sticky="ew")

        self.execute_button = ctk.CTkButton(controls, text="Execute", command=self._execute)
        self.execute_button.grid(row=0, column=3, padx=8, pady=8, sticky="ew")

        self.params_frame = ctk.CTkScrollableFrame(self, height=170)
        self.params_frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=8)

        self.output_box = ctk.CTkTextbox(self, height=300)
        self.output_box.grid(row=4, column=0, sticky="nsew", padx=20, pady=(8, 16))

        self._refresh_actions_for_service(self.service_var.get())

    def _bind_events(self) -> None:
        self.bind("<Control-Return>", lambda _: self._execute())

    def _check_binary(self) -> None:
        if not self.runner.validate_binary():
            messagebox.showerror(
                "Setup Error",
                f"gws binary not found at:\n{self.config_model.gws_binary_path}\nSet GWS_BINARY_PATH in .env.",
            )

    def _append_output(self, text: str) -> None:
        self.output_box.insert("end", f"{text}\n")
        self.output_box.see("end")

    def _on_service_changed(self, _: str) -> None:
        self._refresh_actions_for_service(self.service_var.get())

    def _on_action_changed(self, _: str) -> None:
        self._refresh_parameter_fields()

    def _refresh_actions_for_service(self, service: str) -> None:
        try:
            actions = [a.key for a in self.planner.list_actions(service)]
            if not actions:
                actions = [""]
            self.action_menu.configure(values=actions)
            self.action_var.set(actions[0])
            self._refresh_parameter_fields()
        except Exception as exc:
            self.logger.exception("Failed to refresh actions: %s", exc)
            self._append_output(f"Error loading actions: {exc}")

    def _refresh_parameter_fields(self, defaults: dict[str, Any] | None = None) -> None:
        for widget in self.params_frame.winfo_children():
            widget.destroy()
        self.current_parameters.clear()

        defaults = defaults or {}
        service = self.service_var.get()
        action = self.action_var.get()
        try:
            specs = self.engine.parameter_specs(service, action)
        except Exception:
            return
        for index, spec in enumerate(specs):
            label = ctk.CTkLabel(self.params_frame, text=f"{spec.name} ({'required' if spec.required else 'optional'})")
            label.grid(row=index, column=0, sticky="w", padx=8, pady=(6, 2))
            entry = ctk.CTkEntry(self.params_frame)
            entry.grid(row=index, column=1, sticky="ew", padx=8, pady=(6, 2))
            self.params_frame.grid_columnconfigure(1, weight=1)
            entry_value = str(defaults.get(spec.name) or spec.example)
            entry.insert(0, entry_value)
            self.current_parameters[spec.name] = entry

    def _analyze_request(self) -> None:
        try:
            user_text = self.input_box.get("1.0", "end").strip()
            intent = self.engine.parse_user_request(user_text)
            service = intent.service
            if self.engine.needs_service_clarification(intent):
                supported = ", ".join(self.planner.list_services())
                self._append_output(f"Service not detected. Please choose one: {supported}")
                service = self.service_var.get()
            if service:
                self.service_var.set(service)
            self._refresh_actions_for_service(self.service_var.get())
            if intent.action:
                available_actions = [a.key for a in self.planner.list_actions(self.service_var.get())]
                if intent.action in available_actions:
                    self.action_var.set(intent.action)
            self._refresh_parameter_fields(defaults=intent.parameters)
            self._append_output(
                f"Detected service={self.service_var.get()} action={self.action_var.get() or 'not-detected'}"
            )
        except Exception as exc:
            self.logger.exception("Analyze error: %s", exc)
            self._append_output(f"Analyze error: {exc}")

    def _execute(self) -> None:
        try:
            service = self.service_var.get()
            action = self.action_var.get()
            self.engine.validate_selection(service, action)
            params = {name: entry.get().strip() for name, entry in self.current_parameters.items()}
            args = self.engine.build_command(service, action, params)
            result = self.runner.run(args)
            output = self.engine.format_result(result)
            self._append_output(f"$ {' '.join(result.command)}")
            self._append_output(output)
            self._append_output("-" * 80)
        except ValidationError as exc:
            self._append_output(f"Validation error: {exc}")
            self.logger.warning("Validation error in GUI: %s", exc)
        except Exception as exc:
            self._append_output(f"Execution error: {exc}")
            self.logger.exception("GUI execution error: %s", exc)


def main() -> None:
    """Entry point for GUI execution."""
    app = AssistantGUI()
    app.mainloop()
