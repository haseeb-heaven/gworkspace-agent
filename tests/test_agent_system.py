from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from gws_assistant.agent_system import (
    NO_SERVICE_MESSAGE,
    WorkspaceAgentSystem,
    _detect_services_in_order,
    _has_explicit_web_search_intent,
    _is_drive_to_email_request,
    _is_gmail_to_sheets_request,
    _web_search_query_from_text,
)
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


# ---------------------------------------------------------------------------
# Web-search routing — regression tests for the
# ``Search the web ... save to Sheet/Doc ... send email`` family of bugs.
# ---------------------------------------------------------------------------


class TestExplicitWebSearchIntent:
    """Routing helpers must distinguish web search from Workspace search."""

    @pytest.mark.parametrize(
        "text",
        [
            "Search the web for the top 3 Python frameworks",
            "search web for changelogs of C++ 17",
            "Please look up online: latest LLM benchmarks",
            "Find online how to deploy LangGraph on Cloud Run",
            "Search online for CES 2026 highlights",
            "Browse the web for OpenAI changelog",
            "Search the internet for Vertex AI quotas",
        ],
    )
    def test_web_search_intent_is_detected(self, text):
        assert _has_explicit_web_search_intent(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "Search Drive for all .qvm files",
            "Search Gmail for invoices",
            "search my drive folder for backups",
            "Find my tickets in Gmail",
            "Search for the spreadsheet named Q1 numbers",
        ],
    )
    def test_workspace_search_does_not_trigger_web_intent(self, text):
        assert _has_explicit_web_search_intent(text) is False


class TestServiceDetectionWithWebSearch:
    """``_detect_services_in_order`` must keep ``search`` for web-search prompts."""

    def test_search_is_kept_when_user_says_search_the_web(self):
        text = (
            "Search the web for the top 3 Python frameworks in 2026, "
            "save to a new Google Sheet named 'Top Python Frameworks'"
        )
        services = _detect_services_in_order(text)
        assert "search" in services
        assert "sheets" in services

    def test_search_is_dropped_when_user_says_search_drive(self):
        text = "Search Google drive for 'Passport size photo' and send email"
        services = _detect_services_in_order(text)
        # The user's "search" verb modifies "drive", not the web.
        assert "search" not in services
        assert "drive" in services
        assert "gmail" in services

    def test_drive_alias_is_dropped_when_only_matched_via_document(self):
        """``"document"`` matches both ``drive`` and ``docs`` aliases.

        When the user explicitly asks for a *web search* and only mentions
        "document"/"file" (not "drive"), we should keep ``docs`` and drop
        ``drive`` so the planner doesn't try to look up an existing Drive
        artefact for the Doc the user wants to *create*.
        """
        text = (
            "Search the web for changelogs of C++ 17 and save that "
            "information to a document called 'cpp_17_changelogs' and "
            "send that document via email to user@example.com"
        )
        services = _detect_services_in_order(text)
        assert "search" in services
        assert "docs" in services
        assert "drive" not in services
        assert "gmail" in services


class TestGmailToSheetsHeuristicGuard:
    """``_is_gmail_to_sheets_request`` must not capture web-search prompts."""

    def test_web_search_with_save_and_email_is_rejected(self):
        text = (
            "Search the web for the top 3 Software Engineering AI Agents, "
            "extract name and pricing, save to a new Google Sheet named "
            "'AI Agents Pricing', then send detailed email to user@example.com"
        ).lower()
        assert _is_gmail_to_sheets_request(text) is False

    def test_real_gmail_to_sheets_prompt_still_matches(self):
        text = (
            "Extract every Gmail ticket from last week and save them to a "
            "spreadsheet, then email me the link"
        ).lower()
        assert _is_gmail_to_sheets_request(text) is True


class TestDriveToEmailHeuristicGuard:
    """``_is_drive_to_email_request`` must not capture web-search prompts."""

    def test_web_search_to_doc_to_email_is_rejected(self):
        text = (
            "Search the web for changelogs of C++ 17 and save that "
            "information to a document and send email to user@example.com"
        )
        assert _is_drive_to_email_request(text) is False

    def test_genuine_drive_to_email_prompt_still_matches(self):
        text = "Find my passport photo in Drive and email it to user@example.com"
        assert _is_drive_to_email_request(text) is True


class TestWebSearchQueryExtraction:
    @pytest.mark.parametrize(
        "text, expected_substr",
        [
            (
                "Search the web for the top 3 Python frameworks in 2026, "
                "extract name, save to a new Google Sheet",
                "the top 3 Python frameworks",
            ),
            (
                "Search web for changelogs of C++ 17 and save that information",
                "changelogs of C++ 17",
            ),
            (
                "Search the web for 'Quantum Computing applications'",
                "Quantum Computing applications",
            ),
        ],
    )
    def test_query_focuses_on_topic_not_artifact_name(self, text, expected_substr):
        query = _web_search_query_from_text(text)
        assert expected_substr.lower() in query.lower()
        # Must NOT bleed downstream-step keywords into the search query.
        assert "send" not in query.lower()
        assert "google sheet" not in query.lower()


class TestWebSearchPlanRouting:
    """End-to-end heuristic routing for web-search-driven workflows."""

    def test_web_search_to_sheets_with_code_and_email(self, tmp_path):
        agent = WorkspaceAgentSystem(
            config=_config(tmp_path), logger=logging.getLogger("test")
        )
        plan = agent.plan(
            "Search the web for the top 3 Software Engineering AI Agents, "
            "extract name and pricing, use code executor to sort them from "
            "cheapest to most expensive, save to a new Google Sheet named "
            "'AI Agents Pricing', then send detailed email to user@example.com"
        )

        services = [t.service for t in plan.tasks]
        actions = [t.action for t in plan.tasks]

        assert plan.no_service_detected is False
        # First step MUST be a web search — never gmail.list_messages or
        # drive.list_files.
        assert plan.tasks[0].service == "search"
        assert plan.tasks[0].action == "web_search"
        assert "code" in services
        assert "sheets" in services
        # Email must come last and must not be the body source.
        assert "send_message" in actions
        assert services.index("search") < services.index("sheets")

    def test_web_search_to_sheets_only_no_email(self, tmp_path):
        agent = WorkspaceAgentSystem(
            config=_config(tmp_path), logger=logging.getLogger("test")
        )
        plan = agent.plan(
            "Search the web for the top 3 Python frameworks in 2026, "
            "extract name, description, GitHub stars, and key features, "
            "save to a new Google Sheet named 'Top Python Frameworks' with "
            "proper column headers"
        )

        actions = [t.action for t in plan.tasks]
        assert plan.tasks[0].service == "search"
        assert plan.tasks[0].action == "web_search"
        assert "create_spreadsheet" in actions
        assert "append_values" in actions
        # No email step should be added when the user didn't ask for one.
        assert "send_message" not in actions
        # Critically: gmail.list_messages must NOT appear — the previous
        # heuristic incorrectly inserted it which polluted the spreadsheet
        # with random Gmail messages.
        assert "list_messages" not in actions

    def test_web_search_to_doc_to_email(self, tmp_path):
        agent = WorkspaceAgentSystem(
            config=_config(tmp_path), logger=logging.getLogger("test")
        )
        plan = agent.plan(
            "Search web for changelogs of C++ 17 and save that information "
            "to a document called 'cpp_17_changelogs' and send that "
            "document information to email user@example.com"
        )

        services = [t.service for t in plan.tasks]
        actions = [t.action for t in plan.tasks]

        # Must NOT be drive.list_files + drive.export_file: the doc doesn't
        # exist yet, the planner must CREATE it after a web search.
        assert "drive" not in services
        assert plan.tasks[0].service == "search"
        assert plan.tasks[0].action == "web_search"
        assert "docs" in services
        assert "create_document" in actions
        assert "send_message" in actions

    def test_drive_search_for_named_file_is_unchanged(self, tmp_path):
        """Genuine Drive lookups must still route through drive.list_files."""
        agent = WorkspaceAgentSystem(
            config=_config(tmp_path), logger=logging.getLogger("test")
        )
        plan = agent.plan(
            "Search Google drive for 'Passport size photo' and send email "
            "to user@example.com"
        )
        services = [t.service for t in plan.tasks]
        actions = [t.action for t in plan.tasks]
        assert "search" not in services
        assert "drive" in services
        assert "list_files" in actions
        assert "send_message" in actions
