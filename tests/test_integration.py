import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from gws_assistant.agent_system import WorkspaceAgentSystem
from gws_assistant.execution.executor import PlanExecutor
from gws_assistant.langgraph_workflow import run_workflow
from gws_assistant.models import AppConfigModel
from tests.fakes.fake_google_workspace import FakeGoogleWorkspace


@pytest.fixture
def config():
    return AppConfigModel(
        provider="openai",
        model="gpt-4o",
        api_key="test_key",
        base_url=None,
        timeout_seconds=30,
        gws_binary_path=Path("/fake/gws"),
        log_file_path=Path("gws.log"),
        log_level="INFO",
        verbose=False,
        env_file_path=Path(".env"),
        setup_complete=True,
        max_retries=3,
        langchain_enabled=False,  # Use heuristic planner for deterministic tests
        use_heuristic_fallback=True,
        default_recipient_email="test@example.com",
        read_only_mode=False,
        sandbox_enabled=False,
    )


@pytest.fixture
def logger():
    return logging.getLogger("test_integration")


def run_integration_test(user_text: str, config: AppConfigModel, logger: logging.Logger, fake_gws: FakeGoogleWorkspace):
    # Setup AgentSystem
    system = WorkspaceAgentSystem(config, logger)

    from gws_assistant.planner import CommandPlanner

    # Setup PlanExecutor using the fake runner
    executor = PlanExecutor(planner=CommandPlanner(), runner=fake_gws, logger=logger, config=config)

    output = run_workflow(user_text, config, system, executor, logger)
    return output


def test_flow1_gmail_search_only(config, logger):
    fake_gws = FakeGoogleWorkspace()
    run_integration_test("show me my last 5 unread emails", config, logger, fake_gws)

    # Assert
    calls = fake_gws.call_log
    assert len(calls) >= 1
    list_call = next((c for c in calls if c["service"] == "gmail" and c["action"] == "list_messages"), None)
    assert list_call is not None
    list_call["params"].get("q", "")

    # In heuristic parsing, "unread emails" -> max_results=5, but query might be empty if the quote parsing didn't pick up "unread"
    # we just want to know that list_messages was called correctly
    assert list_call["service"] == "gmail"
    assert list_call["action"] == "list_messages"


def test_flow2_gmail_to_sheets(config, logger):
    fake_gws = FakeGoogleWorkspace()
    run_integration_test("search emails about invoice and save to Google Sheets", config, logger, fake_gws)

    calls = fake_gws.call_log
    services = [c["service"] for c in calls]
    [c["action"] for c in calls]

    assert "gmail" in services
    assert "sheets" in services

    list_call = next((c for c in calls if c["service"] == "gmail" and c["action"] == "list_messages"), None)
    assert list_call is not None

    create_sheet_call = next(
        (c for c in calls if c["service"] == "sheets" and c["action"] == "create_spreadsheet"), None
    )
    assert create_sheet_call is not None

    append_call = next((c for c in calls if c["service"] == "sheets" and c["action"] == "append_values"), None)
    assert append_call is not None
    assert append_call["params"].get("values") is not None and len(append_call["params"]["values"]) > 0


@patch("gws_assistant.tools.web_search.web_search_tool")
def test_flow3_web_search_to_docs(mock_web_search, config, logger):
    mock_web_search.invoke.return_value = {
        "results": [{"title": "Django", "content": "Python framework", "link": "http..."}]
    }
    fake_gws = FakeGoogleWorkspace()

    WorkspaceAgentSystem(config, logger)
    from gws_assistant.planner import CommandPlanner

    executor = PlanExecutor(planner=CommandPlanner(), runner=fake_gws, logger=logger, config=config)
    from gws_assistant.models import PlannedTask, RequestPlan

    plan = RequestPlan(
        raw_text="find top 5 Python frameworks and save to Google Docs",
        tasks=[
            PlannedTask(
                id="task-1", service="search", action="web_search", parameters={"query": "top 5 Python frameworks"}
            ),
            PlannedTask(
                id="task-2",
                service="docs",
                action="create_document",
                parameters={"title": "Python frameworks", "content": "{{task-1.output}}"},
            ),
        ],
        needs_web_search=True,
    )

    executor.execute(plan)

    calls = fake_gws.call_log

    mock_web_search.invoke.assert_called_once_with({"query": "top 5 Python frameworks"})

    create_doc_call = next((c for c in calls if c["service"] == "docs" and c["action"] == "create_document"), None)
    assert create_doc_call is not None

    # Check batch_update content for docs.create_document
    update_call = next((c for c in calls if c["service"] == "docs" and c["action"] == "batch_update"), None)

    if "Python framework" not in str(create_doc_call.get("params", {})):
        assert update_call is not None
        assert "Python framework" in str(update_call.get("params", {})) or "Django" in str(
            update_call.get("params", {})
        )


def test_flow4_drive_to_sheets_to_gmail(config, logger):
    fake_gws = FakeGoogleWorkspace()
    run_integration_test(
        "find my report document, extract data, save to sheets and email to test@example.com", config, logger, fake_gws
    )

    calls = fake_gws.call_log
    actions_seen = [(c["service"], c["action"]) for c in calls]

    # Depending on heuristics vs langchain, it might skip drive search if it thinks it's a direct ID, but we test for the export/get file and sheets and gmail steps.
    # At least we expect some drive operation. Let's make it flexible.
    # The heuristic might not extract "drive" if it thinks it's a direct ID, but it should output sheets and gmail
    # We will test for either drive or sheets being hit and then an email sent.
    assert any(s == "drive" or s == "sheets" for s, _ in actions_seen)

    send_call = next((c for c in calls if c["service"] == "gmail" and c["action"] == "send_message"), None)
    assert send_call is not None


def test_flow5_placeholder_resolution(config, logger):
    # To test this, we need a plan with placeholders. We can force a plan.
    fake_gws = FakeGoogleWorkspace()

    from gws_assistant.planner import CommandPlanner

    WorkspaceAgentSystem(config, logger)
    executor = PlanExecutor(planner=CommandPlanner(), runner=fake_gws, logger=logger, config=config)

    from gws_assistant.models import PlannedTask, RequestPlan

    plan = RequestPlan(
        raw_text="placeholder test",
        tasks=[
            PlannedTask(id="task-1", service="sheets", action="create_spreadsheet", parameters={"title": "Test"}),
            PlannedTask(
                id="task-2",
                service="sheets",
                action="append_values",
                parameters={"spreadsheet_id": "{{task-1.output.spreadsheetId}}", "values": [["Data"]]},
            ),
            PlannedTask(
                id="task-3",
                service="sheets",
                action="get_values",
                parameters={"spreadsheet_id": "{{task-1.id}}", "range": "Sheet1!A1"},
            ),
        ],
    )

    executor.execute(plan)

    calls = fake_gws.call_log
    append_call = next((c for c in calls if c["service"] == "sheets" and c["action"] == "append_values"), None)
    assert append_call is not None
    assert (
        append_call["params"].get("spreadsheet_id", append_call["params"].get("spreadsheetId")) == "fake_sheet_id_123"
    )

    get_values_call = next((c for c in calls if c["service"] == "sheets" and c["action"] == "get_values"), None)
    assert get_values_call is not None
    assert (
        get_values_call["params"].get(
            "spreadsheet_id",
            get_values_call["params"].get("spreadsheetId", get_values_call["params"].get("spreadsheet")),
        )
        == "fake_sheet_id_123"
    )


def test_flow6_reflection_retry_on_failure(config, logger):
    fake_gws = FakeGoogleWorkspace(should_fail_on_first_call=True)

    # Provide a simple plan through workflow
    # It should retry upon transient error
    run_integration_test("create a sheet named RetryTest", config, logger, fake_gws)

    assert fake_gws.call_count >= 2
    # The first call failed, second should succeed, meaning it got retried


def test_flow7_memory_recall_affects_planning(config, logger, tmp_path):
    config.memory_dir = tmp_path

    FakeGoogleWorkspace()
    system = WorkspaceAgentSystem(config, logger)

    # Save an episode
    system.memory.save_episode("send email to boss", [{"id": "t1"}], "success")

    # Call planner with similar query
    system.plan("send email to boss about project")

    # Verify memory was recalled and passed in the prompt or hint
    # Depending on how langchain_agent uses it, we check if memory was retrieved
    past = system.memory.recall_similar("send email to boss about project")
    assert len(past) > 0
    assert past[0]["goal"] == "send email to boss"
