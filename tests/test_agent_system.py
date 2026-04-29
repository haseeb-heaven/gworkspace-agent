from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from gws_assistant.agent_system import NO_SERVICE_MESSAGE, WorkspaceAgentSystem, _detect_services_in_order
from gws_assistant.models import AppConfigModel


def _config(tmp_path: Path) -> AppConfigModel:
    return AppConfigModel(
        provider="openai",
        model="gpt-4.1-mini",
        api_key=None,
        llm_fallback_models=[],
        base_url=None,
        timeout_seconds=30,
        gws_binary_path=tmp_path / os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws"),
        log_file_path=tmp_path / "assistant.log",
        log_level="INFO",
        file_log_level="DEBUG",
        verbose=True,
        env_file_path=tmp_path / ".env",
        setup_complete=True,
        max_retries=3,
        langchain_enabled=True,
        use_heuristic_fallback=True,
        default_recipient_email=os.getenv("DEFAULT_RECIPIENT_EMAIL"),
    )


@pytest.mark.gmail
def test_agent_plans_gmail_search(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan("Find my tickets in Gmail")
    assert plan.no_service_detected is False
    assert plan.tasks[0].service == "gmail"
    assert plan.tasks[0].action == "list_messages"
    assert "ticket" in plan.tasks[0].parameters["q"].lower()


@pytest.mark.sheets
def test_agent_plans_sheet_get(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan("Search Google Sheets with ID: 1bZbV_Wf9EqMKD4QSVaON3UT2l_orD7BEsvHCXGe4lBo")
    assert plan.tasks[0].service == "sheets"
    assert plan.tasks[0].action == "get_values"
    assert plan.tasks[0].parameters["spreadsheet_id"] == "1bZbV_Wf9EqMKD4QSVaON3UT2l_orD7BEsvHCXGe4lBo"


@pytest.mark.gmail
def test_agent_reports_no_service(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan("Remind me to drink water")
    assert plan.no_service_detected is True
    assert plan.summary == NO_SERVICE_MESSAGE


@pytest.mark.gmail
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
        assert actions.index("list_files") < actions.index("send_message")
        assert "export_file" not in actions, f"export_file should be omitted when phrase '{phrase}' is present"


def test_qvm_scenario_regression(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    scenario = "search Drive for all .qvm files, count them, build a summary table, email the table, do not download or export file content"
    plan = agent.plan(scenario)
    assert plan.no_service_detected is False

    actions = [task.action for task in plan.tasks]
    assert "list_files" in actions
    assert "send_message" in actions
    assert actions.index("list_files") < actions.index("send_message")
    assert "export_file" not in actions, "export_file should be omitted in .qvm metadata scenario"

    list_task = next(t for t in plan.tasks if t.action == "list_files")
    assert ".qvm" in list_task.parameters.get("q", "")


def test_strict_service_detection():
    # Strict services should not be detected from substrings.
    services1 = _detect_services_in_order("I need to administrate my users")
    assert "admin" not in services1

    services2 = _detect_services_in_order("This is a subscript")
    assert "script" not in services2

    services3 = _detect_services_in_order("Modelarmorizing the project")
    assert "modelarmor" not in services3

    services4 = _detect_services_in_order("We have some seventy events")
    # "events" should be matched because it's an exact word boundary match
    assert "events" in services4

    services5 = _detect_services_in_order("My seventy event")
    # "events" should not be matched because the input contains the singular "event" which does not match the /\bevents\b/ pattern
    assert "events" not in services5

    # Proper detection with exact boundaries
    services_strict = _detect_services_in_order("run the script, call admin, use modelarmor, check events")
    assert "script" in services_strict
    assert "admin" in services_strict
    assert "modelarmor" in services_strict
    assert "events" in services_strict


@pytest.mark.drive
def test_agent_plans_metadata_only_count_by_extension(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan("Search Drive, count files by extension and email the result")

    assert plan.no_service_detected is False
    actions = [task.action for task in plan.tasks]
    assert "list_files" in actions
    assert "export_file" not in actions
    assert "send_message" in actions


@pytest.mark.drive
def test_agent_plans_metadata_only_list_names_table(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan("Search my drive files, list names only and build a table and send email")

    assert plan.no_service_detected is False
    actions = [task.action for task in plan.tasks]
    assert "list_files" in actions
    assert "export_file" not in actions
    assert "send_message" in actions


@pytest.mark.drive
def test_agent_plans_metadata_only_no_download(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan("Search Drive, do not download, then summarize and email")

    assert plan.no_service_detected is False
    actions = [task.action for task in plan.tasks]
    assert "list_files" in actions
    assert "export_file" not in actions
    assert "send_message" in actions


@pytest.mark.drive
def test_agent_plans_metadata_only_summary_no_content(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan("search Drive and send only the summary, not file content to email")

    assert plan.no_service_detected is False
    actions = [task.action for task in plan.tasks]
    assert "list_files" in actions
    assert "export_file" not in actions
    assert "send_message" in actions


@pytest.mark.drive
def test_agent_plans_content_extraction_when_requested(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan("get the document and email the content")

    assert plan.no_service_detected is False
    actions = [task.action for task in plan.tasks]
    assert "list_files" in actions
    assert "export_file" in actions
    assert "send_message" in actions


@pytest.mark.drive
def test_agent_plans_ambiguous_prompt_forbidding_download(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan("check drive but do not download anything and send me an email")

    assert plan.no_service_detected is False
    actions = [task.action for task in plan.tasks]
    assert "list_files" in actions
    assert "export_file" not in actions
    assert "send_message" in actions
