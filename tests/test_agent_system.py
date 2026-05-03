from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from gws_assistant.agent_system import (
    NO_SERVICE_MESSAGE,
    DriveFolderUploadStrategy,
    PlanningContext,
    WorkspaceAgentSystem,
    _detect_services_in_order,
    _has_explicit_web_search_intent,
    _is_drive_folder_move_request,
    _is_drive_folder_upload_request,
    _is_drive_to_email_request,
    _is_drive_to_sheets_to_email_request,
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
            f"send that document via email to {os.getenv('DEFAULT_RECIPIENT_EMAIL')}"
        )
        services = _detect_services_in_order(text)
        assert "search" in services
        assert "docs" in services
        assert "drive" not in services
        assert "gmail" in services


class TestGmailToSheetsHeuristicGuard:
    """``_is_gmail_to_sheets_request`` must not capture web-search or Drive/document search prompts."""

    def test_web_search_with_save_and_email_is_rejected(self):
        text = (
            "Search the web for the top 3 Software Engineering AI Agents, "
            "extract name and pricing, save to a new Google Sheet named "
            "'AI Agents Pricing', then send detailed email to test@example.com"
        ).lower()
        assert _is_gmail_to_sheets_request(text) is False

    def test_drive_document_search_is_rejected(self):
        text = "Search document '12th Class' and convert that to table format in Sheets"
        assert _is_gmail_to_sheets_request(text) is False

    def test_drive_file_search_is_rejected(self):
        text = "Search file 'report' and save to Sheets"
        assert _is_gmail_to_sheets_request(text) is False

    def test_real_gmail_to_sheets_prompt_still_matches(self):
        text = (
            "Extract every Gmail ticket from last week and save them to a "
            "spreadsheet, then email me the link"
        ).lower()
        assert _is_gmail_to_sheets_request(text) is True

    def test_genuine_gmail_to_sheets_still_matches(self):
        text = "Search my emails for invoices and save to Sheets"
        assert _is_gmail_to_sheets_request(text) is True


class TestDriveToEmailHeuristicGuard:
    """``_is_drive_to_email_request`` must not capture web-search prompts."""

    def test_web_search_to_doc_to_email_is_rejected(self):
        text = (
            "Search the web for changelogs of C++ 17 and save that "
            f"information to a document and send email to {os.getenv('DEFAULT_RECIPIENT_EMAIL')}"
        )
        assert _is_drive_to_email_request(text) is False

    def test_genuine_drive_to_email_prompt_still_matches(self):
        text = f"Find my passport photo in Drive and email it to {os.getenv('DEFAULT_RECIPIENT_EMAIL')}"
        assert _is_drive_to_email_request(text) is True

    def test_drive_image_attachment_skips_export(self, tmp_path):
        """Test that image attachment requests skip export_file and use Drive links."""
        agent = WorkspaceAgentSystem(
            config=_config(tmp_path), logger=logging.getLogger("test")
        )
        plan = agent.plan(
            "Find drive about file 'passport_size_studio_large' and attach that image to my email"
        )

        services = [t.service for t in plan.tasks]
        actions = [t.action for t in plan.tasks]

        # Should have drive.list_files and gmail.send_message
        assert "drive" in services
        assert "gmail" in services
        assert "list_files" in actions
        assert "send_message" in actions

        # Should NOT have export_file for images
        assert "export_file" not in actions

        # Email body should reference Drive links, not content
        gmail_task = next(t for t in plan.tasks if t.action == "send_message")
        assert "$drive_metadata_table" in gmail_task.parameters["body"]
        assert "$drive_file_links" in gmail_task.parameters["body"]


class TestDriveToSheetsToEmailHeuristic:
    """``_is_drive_to_sheets_to_email_request`` detects Drive → Sheets → Gmail workflows."""

    def test_drive_to_sheets_to_email_is_detected(self):
        text = "Search document '12th Class' and convert that to table format in Sheets and then send me haseebmir.hm@gmail.com"
        assert _is_drive_to_sheets_to_email_request(text) is True

    def test_drive_to_sheets_to_email_with_find(self):
        text = "Find document 'report' and save to Sheets then email me"
        assert _is_drive_to_sheets_to_email_request(text) is True

    def test_drive_to_sheets_to_email_rejects_web_search(self):
        text = "Search the web for Python frameworks and save to Sheets and email me"
        assert _is_drive_to_sheets_to_email_request(text) is False

    def test_drive_to_sheets_to_email_requires_drive_document(self):
        text = "Convert to table in Sheets and send email"
        assert _is_drive_to_sheets_to_email_request(text) is False

    def test_drive_metadata_pattern_rejects_sheet_requests(self):
        """Drive metadata pattern should not match when user explicitly mentions Sheets with conversion verbs."""
        from gws_assistant.agent_system import _is_drive_metadata_to_email_request
        text = "Search document '12th Class' and convert that to table format in Sheets and then send email"
        assert _is_drive_metadata_to_email_request(text) is False

    def test_drive_metadata_pattern_rejects_save_to_sheet(self):
        """Drive metadata pattern should not match when user says 'save to Sheets'."""
        from gws_assistant.agent_system import _is_drive_metadata_to_email_request
        text = "Search document 'report' and save to Sheets"
        assert _is_drive_metadata_to_email_request(text) is False

    def test_drive_metadata_only_rejects_sheet_requests(self):
        """Drive metadata-only pattern should not match when user explicitly mentions Sheets with conversion verbs."""
        from gws_assistant.agent_system import _is_metadata_only_request
        text = "Search document '12th Class' and convert that to table format in Sheets"
        assert _is_metadata_only_request(text) is False

    def test_drive_pattern_takes_priority_over_gmail_pattern(self, tmp_path):
        """When both Drive and Gmail could match, Drive pattern should win."""
        agent = WorkspaceAgentSystem(
            config=_config(tmp_path), logger=logging.getLogger("test")
        )
        # This request has both "document" (Drive) and "email" (Gmail) keywords
        # It should route to Drive → Sheets → Gmail, not Gmail → Sheets
        plan = agent.plan(
            "Search document '12th Class' and convert that to table format in Sheets and then show me total percentage and send that sheets link and append that to email"
        )
        assert plan.no_service_detected is False
        # First task should be Drive, not Gmail
        assert plan.tasks[0].service == "drive"
        assert plan.tasks[0].action == "list_files"
        # Should have 6 tasks: drive.list_files -> drive.export_file -> code.execute -> sheets.create_spreadsheet -> sheets.append_values -> gmail.send_message
        assert len(plan.tasks) == 6
        assert plan.tasks[1].service == "drive"
        assert plan.tasks[1].action == "export_file"


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

    def test_web_search_to_doc_to_email_with_call_that_syntax(self, tmp_path):
        """Test 'call that' syntax for doc title extraction."""
        agent = WorkspaceAgentSystem(
            config=_config(tmp_path), logger=logging.getLogger("test")
        )
        plan = agent.plan(
            "Search web for changelogs of C++ 17 and save that information "
            "to a document call that 'cpp_17_changelogs' and send that "
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

        # Verify query extraction is correct (should not include the save/email part)
        assert plan.tasks[0].parameters["query"] == "changelogs of C++ 17"

        # Verify doc title extraction is correct
        doc_task = next(t for t in plan.tasks if t.action == "create_document")
        assert doc_task.parameters["title"] == "cpp_17_changelogs"

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


# ---------------------------------------------------------------------------
# _is_drive_folder_move_request — modified to exclude upload/copy/save
# ---------------------------------------------------------------------------


class TestIsDriveFolderMoveRequest:
    """_is_drive_folder_move_request must return False for upload/copy/save verbs."""

    @pytest.mark.parametrize(
        "text",
        [
            "move files in drive to a folder",
            "organize my drive files into a folder",
            "move this file to a new folder",
        ],
    )
    def test_returns_true_for_move_and_organize(self, text):
        assert _is_drive_folder_move_request(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "upload a file to drive and create a folder",
            "copy the file to a drive folder",
            "save to drive folder",
        ],
    )
    def test_returns_false_when_upload_copy_save_present(self, text):
        assert _is_drive_folder_move_request(text) is False

    def test_returns_false_for_unrelated_text(self):
        assert _is_drive_folder_move_request("send an email") is False

    def test_word_boundaries_prevent_substring_matches(self):
        # "saved", "copyrighted", "unsaved" should not match "save" or "copy"
        assert _is_drive_folder_move_request("move my saved files to a drive folder") is True
        assert _is_drive_folder_move_request("organize my copyrighted files on drive") is True
        assert _is_drive_folder_move_request("move unsaved drafts to a drive folder") is True


# ---------------------------------------------------------------------------
# _is_drive_folder_upload_request — new function
# ---------------------------------------------------------------------------


class TestIsDriveFolderUploadRequest:
    """_is_drive_folder_upload_request detects upload-to-folder patterns."""

    @pytest.mark.parametrize(
        "text",
        [
            "create a drive folder and upload the file",
            "create folder in drive then copy the file there",
            "create a new drive folder and save the report",
            "upload 'report.pdf' to a new folder in drive, create the folder first",
            "create folder and copy file to drive",
        ],
    )
    def test_returns_true_for_upload_patterns(self, text):
        assert _is_drive_folder_upload_request(text) is True

    def test_returns_false_without_drive_or_folder(self):
        # Neither "drive" nor "folder"
        assert _is_drive_folder_upload_request("create and upload and save") is False

    def test_returns_false_without_upload_copy_or_save(self):
        # Has "drive" + "create" but no upload verb
        assert _is_drive_folder_upload_request("create a folder in drive") is False

    def test_returns_false_without_create_keyword(self):
        # Has "drive" + "upload" but no "create" - should not match (requires explicit folder creation)
        assert _is_drive_folder_upload_request("upload a file to drive") is False

    def test_returns_false_for_pure_move_request(self):
        # Move requests must not trigger upload
        assert _is_drive_folder_upload_request("move files in drive to a folder") is False

    def test_word_boundaries_prevent_substring_matches(self):
        # "saved", "copyrighted", "unsaved" should not match "save" or "copy"
        assert _is_drive_folder_upload_request("upload my saved files to drive") is True
        assert _is_drive_folder_upload_request("copy copyrighted content to folder") is True


# ---------------------------------------------------------------------------
# WorkspaceAgentSystem._drive_folder_upload_tasks — new method
# ---------------------------------------------------------------------------


class TestDriveFolderUploadTasks:
    """_drive_folder_upload_tasks must produce exactly 2 planned tasks."""

    def setup_method(self, tmp_path=None):
        # Use a temporary config without a real binary
        import tempfile
        self._tmp = tempfile.mkdtemp()
        self._config = AppConfigModel(
            provider="openai",
            model="gpt-4.1-mini",
            api_key=None,
            llm_fallback_models=[],
            base_url=None,
            timeout_seconds=30,
            gws_binary_path=os.path.join(self._tmp, "gws"),
            log_file_path=os.path.join(self._tmp, "assistant.log"),
            log_level="INFO",
            verbose=False,
            env_file_path=os.path.join(self._tmp, ".env"),
            setup_complete=True,
            max_retries=3,
            langchain_enabled=False,
            use_heuristic_fallback=True,
            default_recipient_email="test@example.com",
        )
        self._agent = WorkspaceAgentSystem(
            config=self._config, logger=logging.getLogger("test")
        )

    def test_returns_exactly_two_tasks(self):
        tasks = self._agent._drive_folder_upload_tasks(
            "create folder 'Backups' and upload 'notes.txt'", "create folder 'backups' and upload 'notes.txt'"
        )
        assert len(tasks) == 2

    def test_first_task_is_create_folder(self):
        tasks = self._agent._drive_folder_upload_tasks(
            "create folder 'Reports' and upload 'data.csv'", "create folder 'reports' and upload 'data.csv'"
        )
        assert tasks[0].service == "drive"
        assert tasks[0].action == "create_folder"

    def test_second_task_is_upload_file(self):
        tasks = self._agent._drive_folder_upload_tasks(
            "create folder 'Reports' and upload 'data.csv'", "create folder 'reports' and upload 'data.csv'"
        )
        assert tasks[1].service == "drive"
        assert tasks[1].action == "upload_file"

    def test_folder_name_extracted_from_quoted_string(self):
        tasks = self._agent._drive_folder_upload_tasks(
            "create folder 'MyArchive' and upload 'document.pdf'",
            "create folder 'myarchive' and upload 'document.pdf'",
        )
        assert tasks[0].parameters["folder_name"] == "MyArchive"

    def test_file_path_extracted_after_upload_keyword(self):
        tasks = self._agent._drive_folder_upload_tasks(
            "create 'Docs' folder and upload 'report.pdf' to drive",
            "create 'docs' folder and upload 'report.pdf' to drive",
        )
        assert tasks[1].parameters["file_path"] == "report.pdf"

    def test_file_path_extracted_after_copy_keyword(self):
        tasks = self._agent._drive_folder_upload_tasks(
            "create folder 'Archive' and copy 'backup.zip' to it",
            "create folder 'archive' and copy 'backup.zip' to it",
        )
        assert tasks[1].parameters["file_path"] == "backup.zip"

    def test_file_path_extracted_after_save_keyword(self):
        tasks = self._agent._drive_folder_upload_tasks(
            "create folder 'Logs' and save 'app.log' there",
            "create folder 'logs' and save 'app.log' there",
        )
        assert tasks[1].parameters["file_path"] == "app.log"

    def test_upload_task_uses_task1_id_placeholder_as_folder_id(self):
        tasks = self._agent._drive_folder_upload_tasks(
            "create folder 'Output' and upload 'result.txt'",
            "create folder 'output' and upload 'result.txt'",
        )
        assert tasks[1].parameters["folder_id"] == "{{task-1.id}}"

    def test_folder_name_defaults_to_new_folder_when_no_quotes(self):
        tasks = self._agent._drive_folder_upload_tasks(
            "create a folder and upload the file", "create a folder and upload the file"
        )
        assert tasks[0].parameters["folder_name"] == "New Folder"

    def test_file_path_defaults_to_empty_string_when_no_quotes(self):
        tasks = self._agent._drive_folder_upload_tasks(
            "create a folder and upload the file", "create a folder and upload the file"
        )
        assert tasks[1].parameters["file_path"] == ""

    def test_second_quoted_string_used_as_file_path_when_no_keyword(self):
        # When no upload/copy/save precedes a quote, the second quoted string becomes file_path
        tasks = self._agent._drive_folder_upload_tasks(
            "put 'MyFolder' folder and include 'data.csv' inside",
            "put 'myfolder' folder and include 'data.csv' inside",
        )
        assert tasks[0].parameters["folder_name"] == "MyFolder"
        assert tasks[1].parameters["file_path"] == "data.csv"

    def test_single_quoted_string_used_as_folder_name_file_defaults(self):
        # Only one quoted string: used for folder_name; file_path defaults to empty string
        tasks = self._agent._drive_folder_upload_tasks(
            "create a folder named 'ProjectFiles' and upload a file",
            "create a folder named 'projectfiles' and upload a file",
        )
        assert tasks[0].parameters["folder_name"] == "ProjectFiles"
        assert tasks[1].parameters["file_path"] == ""

    def test_task_ids_are_task_1_and_task_2(self):
        tasks = self._agent._drive_folder_upload_tasks(
            "create folder 'X' and upload 'Y.txt'",
            "create folder 'x' and upload 'y.txt'",
        )
        assert tasks[0].id == "task-1"
        assert tasks[1].id == "task-2"


# ---------------------------------------------------------------------------
# DriveFolderUploadStrategy — new strategy class
# ---------------------------------------------------------------------------


class TestDriveFolderUploadStrategy:
    """DriveFolderUploadStrategy must have correct priority and matching logic."""

    def _make_ctx(self, text: str, services: list[str]) -> PlanningContext:
        cfg = AppConfigModel(
            provider="openai",
            model="gpt-4.1-mini",
            api_key=None,
            llm_fallback_models=[],
            base_url=None,
            timeout_seconds=30,
            gws_binary_path="/tmp/gws",
            log_file_path="/tmp/assistant.log",
            log_level="INFO",
            verbose=False,
            env_file_path="/tmp/.env",
            setup_complete=True,
            max_retries=3,
            langchain_enabled=False,
            use_heuristic_fallback=True,
            default_recipient_email="test@example.com",
        )
        return PlanningContext(
            text=text,
            lowered=text.lower(),
            services=services,
            config=cfg,
            logger=logging.getLogger("test"),
        )

    def test_priority_returns_72(self):
        strategy = DriveFolderUploadStrategy()
        assert strategy.priority() == 72

    def test_matches_when_drive_in_services_and_upload_request(self):
        strategy = DriveFolderUploadStrategy()
        ctx = self._make_ctx(
            "create a drive folder and upload the file", ["drive"]
        )
        assert strategy.matches(ctx) is True

    def test_does_not_match_when_drive_not_in_services(self):
        strategy = DriveFolderUploadStrategy()
        ctx = self._make_ctx(
            "create a drive folder and upload the file", ["gmail"]
        )
        assert strategy.matches(ctx) is False

    def test_does_not_match_when_upload_request_pattern_fails(self):
        strategy = DriveFolderUploadStrategy()
        # No upload/copy/save verb -> pattern fails
        ctx = self._make_ctx("list files in drive folder", ["drive"])
        assert strategy.matches(ctx) is False


    def test_execute_returns_request_plan_with_two_tasks(self, tmp_path):
        import tempfile
        tmp = tempfile.mkdtemp()
        cfg = AppConfigModel(
            provider="openai",
            model="gpt-4.1-mini",
            api_key=None,
            llm_fallback_models=[],
            base_url=None,
            timeout_seconds=30,
            gws_binary_path=os.path.join(tmp, "gws"),
            log_file_path=os.path.join(tmp, "assistant.log"),
            log_level="INFO",
            verbose=False,
            env_file_path=os.path.join(tmp, ".env"),
            setup_complete=True,
            max_retries=3,
            langchain_enabled=False,
            use_heuristic_fallback=True,
            default_recipient_email="test@example.com",
        )
        agent = WorkspaceAgentSystem(config=cfg, logger=logging.getLogger("test"))
        strategy = DriveFolderUploadStrategy()
        text = "create a drive folder 'Archive' and upload 'notes.txt'"
        ctx = PlanningContext(
            text=text,
            lowered=text.lower(),
            services=["drive"],
            config=cfg,
            logger=logging.getLogger("test"),
        )
        plan = strategy.execute(ctx, agent)
        assert len(plan.tasks) == 2
        assert plan.no_service_detected is False
        assert plan.source == "heuristic"

    def test_execute_returns_confidence_0_75(self, tmp_path):
        import tempfile
        tmp = tempfile.mkdtemp()
        cfg = AppConfigModel(
            provider="openai",
            model="gpt-4.1-mini",
            api_key=None,
            llm_fallback_models=[],
            base_url=None,
            timeout_seconds=30,
            gws_binary_path=os.path.join(tmp, "gws"),
            log_file_path=os.path.join(tmp, "assistant.log"),
            log_level="INFO",
            verbose=False,
            env_file_path=os.path.join(tmp, ".env"),
            setup_complete=True,
            max_retries=3,
            langchain_enabled=False,
            use_heuristic_fallback=True,
            default_recipient_email="test@example.com",
        )
        agent = WorkspaceAgentSystem(config=cfg, logger=logging.getLogger("test"))
        strategy = DriveFolderUploadStrategy()
        text = "create a drive folder and upload 'data.csv'"
        ctx = PlanningContext(
            text=text,
            lowered=text.lower(),
            services=["drive"],
            config=cfg,
            logger=logging.getLogger("test"),
        )
        plan = strategy.execute(ctx, agent)
        assert plan.confidence == 0.75

    def test_execute_summary_includes_task_count(self, tmp_path):
        import tempfile
        tmp = tempfile.mkdtemp()
        cfg = AppConfigModel(
            provider="openai",
            model="gpt-4.1-mini",
            api_key=None,
            llm_fallback_models=[],
            base_url=None,
            timeout_seconds=30,
            gws_binary_path=os.path.join(tmp, "gws"),
            log_file_path=os.path.join(tmp, "assistant.log"),
            log_level="INFO",
            verbose=False,
            env_file_path=os.path.join(tmp, ".env"),
            setup_complete=True,
            max_retries=3,
            langchain_enabled=False,
            use_heuristic_fallback=True,
            default_recipient_email="test@example.com",
        )
        agent = WorkspaceAgentSystem(config=cfg, logger=logging.getLogger("test"))
        strategy = DriveFolderUploadStrategy()
        text = "create a drive folder and upload 'report.pdf'"
        ctx = PlanningContext(
            text=text,
            lowered=text.lower(),
            services=["drive"],
            config=cfg,
            logger=logging.getLogger("test"),
        )
        plan = strategy.execute(ctx, agent)
        assert "2" in plan.summary
        assert "drive.create_folder" in plan.summary
        assert "drive.upload_file" in plan.summary


# ---------------------------------------------------------------------------
# Integration: agent.plan() routes to DriveFolderUploadStrategy
# ---------------------------------------------------------------------------


@pytest.mark.drive
def test_agent_plans_drive_folder_upload(tmp_path):
    """agent.plan() must select the upload strategy, not the move strategy."""
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan("create a folder in drive and upload 'report.pdf'")

    assert plan.no_service_detected is False
    actions = [t.action for t in plan.tasks]
    assert "create_folder" in actions
    assert "upload_file" in actions
    assert "move_file" not in actions


@pytest.mark.drive
def test_agent_upload_strategy_extracts_folder_and_file(tmp_path):
    """Folder name and file path are correctly extracted from quoted strings."""
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan("create folder 'MyDocs' and upload 'readme.md' to drive")

    create_task = next(t for t in plan.tasks if t.action == "create_folder")
    upload_task = next(t for t in plan.tasks if t.action == "upload_file")
    assert create_task.parameters["folder_name"] == "MyDocs"
    assert upload_task.parameters["file_path"] == "readme.md"
    assert upload_task.parameters["folder_id"] == "{{task-1.id}}"


@pytest.mark.drive
def test_agent_upload_request_does_not_use_move_strategy(tmp_path):
    """A request with 'upload' must not be routed to the move strategy."""
    agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
    plan = agent.plan("create a drive folder and upload the file, save it there")

    actions = [t.action for t in plan.tasks]
    assert "move_file" not in actions
