from __future__ import annotations

import logging
import os
from pathlib import Path

from gws_assistant.agent_system import NO_SERVICE_MESSAGE, WorkspaceAgentSystem
from gws_assistant.models import AppConfigModel


def _config(tmp_path: Path) -> AppConfigModel:
    return AppConfigModel(
        provider="openai",
        model="gpt-4.1-mini",
        api_key=None,
        base_url=None,
        timeout_seconds=30,
        gws_binary_path=tmp_path / os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws"),
        log_file_path=tmp_path / "assistant.log",
        log_level="INFO",
        verbose=True,
        env_file_path=tmp_path / ".env",
        setup_complete=True,
        max_retries=3,
        langchain_enabled=True,
        use_heuristic_fallback=True,
        default_recipient_email=os.getenv("DEFAULT_RECIPIENT_EMAIL")
    )


def test_agent_plans_gmail_search(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan("Find my tickets in Gmail")
    assert plan.no_service_detected is False
    assert plan.tasks[0].service == "gmail"
    assert plan.tasks[0].action == "list_messages"
    assert "ticket" in plan.tasks[0].parameters["q"].lower()


def test_agent_plans_sheet_get(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan("Search Google Sheets with ID: 1bZbV_Wf9EqMKD4QSVaON3UT2l_orD7BEsvHCXGe4lBo")
    assert plan.tasks[0].service == "sheets"
    assert plan.tasks[0].action == "get_values"
    assert plan.tasks[0].parameters["spreadsheet_id"] == "1bZbV_Wf9EqMKD4QSVaON3UT2l_orD7BEsvHCXGe4lBo"


def test_agent_reports_no_service(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan("Remind me to drink water")
    assert plan.no_service_detected is True
    assert plan.summary == NO_SERVICE_MESSAGE


def test_agent_disables_heuristics_when_flag_false(tmp_path):
    config = _config(tmp_path)
    config.use_heuristic_fallback = False
    config.api_key = None
    agent = WorkspaceAgentSystem(config=config, logger=logging.getLogger("test"))
    plan = agent.plan("Find tickets in Gmail")
    assert plan.no_service_detected is True
    assert "disabled" in plan.summary.lower()

def test_metadata_drive_phrases_prevent_export(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    phrases = ["count", "table", "metadata only", "names only", "do not download", "no file content"]
    for phrase in phrases:
        plan = agent.plan(f"Search Drive for report and {phrase} and email it")
        assert plan.no_service_detected is False

        actions = [task.action for task in plan.tasks]
        assert "list_files" in actions
        assert "send_message" in actions
        assert "export_file" not in actions, f"export_file should be omitted when phrase '{phrase}' is present"

def test_qvm_scenario_regression(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    scenario = "search Drive for all .qvm files, count them, build a summary table, email the table, do not download or export file content"
    plan = agent.plan(scenario)
    assert plan.no_service_detected is False

    actions = [task.action for task in plan.tasks]
    assert "list_files" in actions
    assert "send_message" in actions
    assert "export_file" not in actions, "export_file should be omitted in .qvm metadata scenario"

from gws_assistant.agent_system import _detect_services_in_order

def test_strict_service_detection():
    # Strict services should not be detected from substrings.
    services1 = _detect_services_in_order("I need to administrate my users")
    assert "admin" not in services1

    services2 = _detect_services_in_order("This is a subscript")
    assert "script" not in services2

    services3 = _detect_services_in_order("Modelarmorizing the project")
    assert "modelarmor" not in services3

    services4 = _detect_services_in_order("We have some seventy events")
    assert "events" in services4 # events should be caught if it's exact word match

    services5 = _detect_services_in_order("My seventy event")
    assert "events" not in services5 # wait, we'll see how it acts

    # Proper detection with exact boundaries
    services_strict = _detect_services_in_order("run the script, call admin, use modelarmor, check events")
    assert "script" in services_strict
    assert "admin" in services_strict
    assert "modelarmor" in services_strict
    assert "events" in services_strict
