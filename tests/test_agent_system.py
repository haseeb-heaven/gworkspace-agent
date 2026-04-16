from __future__ import annotations

import logging
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
        gws_binary_path=tmp_path / "gws.exe",
        log_file_path=tmp_path / "assistant.log",
        log_level="INFO",
        verbose=True,
        env_file_path=tmp_path / ".env",
        setup_complete=True,
        max_retries=3,
        langchain_enabled=True,
        use_heuristic_fallback=True,
    )


def test_agent_plans_gmail_to_sheets(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan("Find my tickets in Gmail and save to Sheets")
    assert plan.no_service_detected is False
    assert [(task.service, task.action) for task in plan.tasks] == [
        ("gmail", "list_messages"),
        ("sheets", "create_spreadsheet"),
        ("sheets", "append_values"),
    ]
    assert plan.tasks[0].parameters["q"] == "ticket OR tickets"


def test_agent_trims_save_instruction_from_gmail_query(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan("Search my email about Jobs offers from last week and save company names into Google sheets")
    assert plan.tasks[0].parameters["q"] == "jobs offers from last week"


def test_agent_adds_get_message_for_company_extraction(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan("Search my email about jobs offers and save company names into Google sheets")
    assert ("gmail", "get_message") in [(task.service, task.action) for task in plan.tasks]


def test_agent_plans_sheet_to_email_flow(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan(
        "Search Google Sheets with ID: 1bZbV_Wf9EqMKD4QSVaON3UT2l_orD7BEsvHCXGe4lBo create email with this data to igiproz.hm@gmail.com and send it."
    )
    assert [(task.service, task.action) for task in plan.tasks] == [
        ("sheets", "get_values"),
        ("gmail", "send_message"),
    ]
    assert plan.tasks[0].parameters["spreadsheet_id"] == "1bZbV_Wf9EqMKD4QSVaON3UT2l_orD7BEsvHCXGe4lBo"
    assert plan.tasks[1].parameters["to_email"] == "igiproz.hm@gmail.com"


def test_agent_reports_no_service(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan("Remind me to drink water")
    assert plan.no_service_detected is True
    assert plan.summary == NO_SERVICE_MESSAGE


def test_agent_lists_email_with_detail_fetch(tmp_path):
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan("List all received emails from assistant@glider.ai")
    assert [(task.service, task.action) for task in plan.tasks] == [
        ("gmail", "list_messages"),
        ("gmail", "get_message"),
    ]


def test_agent_disables_heuristics_when_flag_false(tmp_path):
    config = _config(tmp_path)
    config.use_heuristic_fallback = False
    config.api_key = None
    agent = WorkspaceAgentSystem(config=config, logger=logging.getLogger("test"))
    plan = agent.plan("Find tickets in Gmail and save to Sheets")
    assert plan.no_service_detected is True
    assert "disabled" in plan.summary.lower()
