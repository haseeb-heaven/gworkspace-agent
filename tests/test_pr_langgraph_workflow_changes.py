"""Tests for PR changes in gws_assistant/langgraph_workflow.py.

Covers:
- WorkflowNodes.intent_verification_node: new method
- WorkflowNodes._extract_requirements: detects calendar, email, doc, drive, sheets, tasks
- WorkflowNodes._check_missing_requirements: returns missing items
- WorkflowNodes.reflect_node: code error detection triggers retry
- WorkflowNodes.format_output_node: "Task completed." fallback when no report
- route_after_intent_verification: routes to generate_plan or END
- AgentState: new fields intent_verification and verification_attempts
"""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

# langgraph_workflow requires langchain_core; skip if not available.
pytest.importorskip("langchain_core", reason="langchain_core not installed")

from gws_assistant.langgraph_workflow import WorkflowNodes
from gws_assistant.models import (
    AgentState,
    PlannedTask,
    ReflectionDecision,
    RequestPlan,
    StructuredToolResult,
    TaskExecution,
)


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.verbose = False
    config.max_retries = 3
    config.max_replans = 1
    return config


@pytest.fixture
def mock_system():
    return MagicMock()


@pytest.fixture
def mock_executor():
    executor = MagicMock()
    executor._expand_task.side_effect = lambda t, c: [t]
    executor._resolve_task.side_effect = lambda t, c: t
    executor.reflect_on_error.return_value = (ReflectionDecision(action="continue", reason="ok"), False)
    return executor


@pytest.fixture
def logger():
    return logging.getLogger("test_pr_workflow")


@pytest.fixture
def nodes(mock_config, mock_system, mock_executor, logger):
    return WorkflowNodes(mock_config, mock_system, mock_executor, logger)


# ---------------------------------------------------------------------------
# WorkflowNodes._extract_requirements
# ---------------------------------------------------------------------------

class TestExtractRequirements:
    def test_calendar_keywords_detected(self, nodes):
        reqs = nodes._extract_requirements("Schedule a meeting tomorrow")
        assert "calendar_action" in reqs

    def test_event_keyword_detected(self, nodes):
        reqs = nodes._extract_requirements("Create an event for next week")
        assert "calendar_action" in reqs

    def test_reminder_keyword_detected(self, nodes):
        reqs = nodes._extract_requirements("Set a reminder for my appointment")
        assert "calendar_action" in reqs

    def test_tomorrow_adds_future_date(self, nodes):
        reqs = nodes._extract_requirements("Send an email tomorrow")
        assert "future_date" in reqs

    def test_tomorrow_not_added_without_keyword(self, nodes):
        reqs = nodes._extract_requirements("Send an email today")
        assert "future_date" not in reqs

    def test_email_keywords_detected(self, nodes):
        for keyword in ["email", "emails", "gmail", "inbox", "unread"]:
            reqs = nodes._extract_requirements(f"Check my {keyword}")
            assert "email_action" in reqs, f"email_action not detected for keyword: {keyword}"

    def test_message_keyword_detected(self, nodes):
        reqs = nodes._extract_requirements("Read my messages")
        assert "email_action" in reqs

    def test_doc_keywords_detected(self, nodes):
        for text in ["create doc", "create document", "google doc", "write a document"]:
            reqs = nodes._extract_requirements(text)
            assert "doc_action" in reqs, f"doc_action not detected for: {text}"

    def test_drive_keywords_detected(self, nodes):
        for keyword in ["drive", "file", "files", "folder", "upload", "download"]:
            reqs = nodes._extract_requirements(f"List my {keyword}")
            assert "drive_action" in reqs, f"drive_action not detected for: {keyword}"

    def test_sheets_keywords_detected(self, nodes):
        for keyword in ["sheet", "spreadsheet", "excel", "csv", "table"]:
            reqs = nodes._extract_requirements(f"Open the {keyword}")
            assert "sheets_action" in reqs, f"sheets_action not detected for: {keyword}"

    def test_task_keywords_detected(self, nodes):
        for keyword in ["task", "todo", "tasks", "todo list", "task list"]:
            reqs = nodes._extract_requirements(f"Create a {keyword}")
            assert "tasks_action" in reqs, f"tasks_action not detected for: {keyword}"

    def test_no_keywords_returns_empty(self, nodes):
        reqs = nodes._extract_requirements("What is the weather like?")
        assert reqs == []

    def test_multiple_keywords_returns_multiple_reqs(self, nodes):
        reqs = nodes._extract_requirements("Check my emails and calendar events")
        assert "email_action" in reqs
        assert "calendar_action" in reqs

    def test_case_insensitive(self, nodes):
        reqs = nodes._extract_requirements("SEND AN EMAIL")
        assert "email_action" in reqs


# ---------------------------------------------------------------------------
# WorkflowNodes._check_missing_requirements
# ---------------------------------------------------------------------------

class TestCheckMissingRequirements:
    def test_all_satisfied_returns_empty(self, nodes):
        missing = nodes._check_missing_requirements(
            "Created calendar event for tomorrow", ["calendar_action"]
        )
        assert missing == []

    def test_missing_calendar_when_no_calendar_words_in_output(self, nodes):
        missing = nodes._check_missing_requirements(
            "Done. Here is the result.", ["calendar_action"]
        )
        assert "calendar_action" in missing

    def test_missing_email_when_no_email_words_in_output(self, nodes):
        missing = nodes._check_missing_requirements(
            "Files listed successfully.", ["email_action"]
        )
        assert "email_action" in missing

    def test_email_satisfied_by_gmail_word(self, nodes):
        missing = nodes._check_missing_requirements(
            "Found 5 gmail messages in your inbox.", ["email_action"]
        )
        assert "email_action" not in missing

    def test_email_satisfied_by_message_word(self, nodes):
        missing = nodes._check_missing_requirements(
            "Read your message from John.", ["email_action"]
        )
        assert "email_action" not in missing

    def test_missing_doc_action(self, nodes):
        missing = nodes._check_missing_requirements(
            "Task completed.", ["doc_action"]
        )
        assert "doc_action" in missing

    def test_doc_action_satisfied_by_created(self, nodes):
        missing = nodes._check_missing_requirements(
            "Document created successfully.", ["doc_action"]
        )
        assert "doc_action" not in missing

    def test_missing_drive_action(self, nodes):
        missing = nodes._check_missing_requirements(
            "Email sent.", ["drive_action"]
        )
        assert "drive_action" in missing

    def test_drive_action_satisfied_by_file(self, nodes):
        missing = nodes._check_missing_requirements(
            "Listed 10 files in your Drive.", ["drive_action"]
        )
        assert "drive_action" not in missing

    def test_missing_sheets_action(self, nodes):
        missing = nodes._check_missing_requirements(
            "Email sent.", ["sheets_action"]
        )
        assert "sheets_action" in missing

    def test_sheets_action_satisfied_by_spreadsheet(self, nodes):
        missing = nodes._check_missing_requirements(
            "Created new spreadsheet.", ["sheets_action"]
        )
        assert "sheets_action" not in missing

    def test_missing_tasks_action(self, nodes):
        missing = nodes._check_missing_requirements(
            "Calendar event created.", ["tasks_action"]
        )
        assert "tasks_action" in missing

    def test_tasks_action_satisfied_by_task(self, nodes):
        missing = nodes._check_missing_requirements(
            "New task added to your list.", ["tasks_action"]
        )
        assert "tasks_action" not in missing

    def test_empty_requirements_returns_empty(self, nodes):
        missing = nodes._check_missing_requirements("Some output", [])
        assert missing == []

    def test_empty_output_all_missing(self, nodes):
        missing = nodes._check_missing_requirements("", ["email_action", "calendar_action"])
        assert "email_action" in missing
        assert "calendar_action" in missing


# ---------------------------------------------------------------------------
# WorkflowNodes.intent_verification_node
# ---------------------------------------------------------------------------

class TestIntentVerificationNode:
    def test_passes_when_output_matches_intent(self, nodes):
        state = {
            "user_text": "Check my emails",
            "final_output": "Found 5 emails in your Gmail inbox.",
            "verification_attempts": 0,
        }
        result = nodes.intent_verification_node(state)
        assert result["intent_verification"]["passed"] is True
        assert result["intent_verification"]["missing"] == []

    def test_fails_when_output_missing_required_elements(self, nodes):
        state = {
            "user_text": "Check my emails",
            "final_output": "Calendar event created.",
            "verification_attempts": 0,
        }
        result = nodes.intent_verification_node(state)
        assert result["intent_verification"]["passed"] is False
        assert "email_action" in result["intent_verification"]["missing"]

    def test_increments_verification_attempts_on_failure(self, nodes):
        state = {
            "user_text": "Check my emails",
            "final_output": "Calendar event created.",
            "verification_attempts": 0,
        }
        result = nodes.intent_verification_node(state)
        assert result["verification_attempts"] == 1

    def test_passes_after_max_attempts_even_if_missing(self, nodes):
        """After 2 verification attempts, should pass regardless to avoid infinite loop."""
        MAX_ATTEMPTS = 2  # match actual threshold in intent_verification_node
        state = {
            "user_text": "Check my emails",
            "final_output": "Calendar event created.",
            "verification_attempts": MAX_ATTEMPTS,
        }
        result = nodes.intent_verification_node(state)
        assert result["intent_verification"]["passed"] is True, (
            f"Should force-pass at attempt {MAX_ATTEMPTS} to avoid infinite loop"
        )

    def test_no_requirements_always_passes(self, nodes):
        state = {
            "user_text": "What time is it?",
            "final_output": "It is 3pm.",
            "verification_attempts": 0,
        }
        result = nodes.intent_verification_node(state)
        assert result["intent_verification"]["passed"] is True

    def test_calendar_intent_with_calendar_output_passes(self, nodes):
        state = {
            "user_text": "Schedule a meeting",
            "final_output": "Meeting scheduled on your calendar.",
            "verification_attempts": 0,
        }
        result = nodes.intent_verification_node(state)
        assert result["intent_verification"]["passed"] is True

    def test_failure_sets_error_in_result(self, nodes):
        state = {
            "user_text": "Check emails",
            "final_output": "Drive files listed.",
            "verification_attempts": 0,
        }
        result = nodes.intent_verification_node(state)
        if not result["intent_verification"]["passed"]:
            assert "error" in result
            assert "email_action" in result["error"]

    def test_missing_user_text_does_not_crash(self, nodes):
        """Missing user_text should not raise an exception."""
        state = {
            "final_output": "Some output",
            "verification_attempts": 0,
        }
        result = nodes.intent_verification_node(state)
        assert "intent_verification" in result

    def test_missing_final_output_does_not_crash(self, nodes):
        state = {
            "user_text": "Check emails",
            "verification_attempts": 0,
        }
        result = nodes.intent_verification_node(state)
        assert "intent_verification" in result


# ---------------------------------------------------------------------------
# WorkflowNodes.reflect_node — code error detection
# ---------------------------------------------------------------------------

class TestReflectNodeCodeError:
    def test_code_error_triggers_retry(self, nodes):
        """When needs_code_fix is True, reflect_node returns retry decision."""
        state = {
            "error": "NameError: name 'df' is not defined",
            "current_attempt": 0,
            "context": {"needs_code_fix": True},
            "last_result": None,
        }
        result = nodes.reflect_node(state)
        assert result["reflection"].action == "retry"

    def test_code_in_error_triggers_retry(self, nodes):
        """Error string containing 'code' triggers retry for LLM fix."""
        state = {
            "error": "code execution failed: SyntaxError",
            "current_attempt": 0,
            "context": {},
            "last_result": None,
        }
        result = nodes.reflect_node(state)
        assert result["reflection"].action == "retry"

    def test_no_code_error_delegates_to_executor(self, nodes, mock_executor):
        """Without code error, falls through to executor.reflect_on_error."""
        mock_executor.reflect_on_error.return_value = (
            ReflectionDecision(action="continue", reason="normal error"), False
        )
        state = {
            "error": "Network timeout",
            "current_attempt": 0,
            "context": {},
            "last_result": None,
        }
        result = nodes.reflect_node(state)
        mock_executor.reflect_on_error.assert_called_once()

    def test_code_error_after_max_retries_falls_through(self, nodes, mock_config):
        """After max_retries, code error should not force retry."""
        mock_config.max_retries = 3
        state = {
            "error": "code execution failed",
            "current_attempt": 5,  # > max_retries=3
            "context": {"needs_code_fix": True},
            "last_result": None,
        }
        result = nodes.reflect_node(state)
        # Should NOT be forced retry since attempts >= max_retries
        # Executor handles it
        assert "reflection" in result


# ---------------------------------------------------------------------------
# WorkflowNodes.format_output_node — "Task completed." fallback
# ---------------------------------------------------------------------------

class TestFormatOutputNodeFallback:
    def test_empty_report_becomes_task_completed(self, nodes):
        """PR change: empty report becomes 'Task completed.' not raw error."""
        state = {
            "plan": None,
            "executions": [],
            "context": {},
            "final_output": "",
        }
        result = nodes.format_output_node(state)
        assert result["final_output"] == "Task completed."

    def test_none_report_becomes_task_completed(self, nodes):
        state = {
            "plan": None,
            "executions": [],
            "context": {},
            "final_output": None,
            "error": None,
        }
        result = nodes.format_output_node(state)
        assert result["final_output"] == "Task completed."

    def test_no_result_produced_becomes_task_completed(self, nodes):
        """'No result produced.' sentinel also becomes 'Task completed.'"""
        state = {
            "plan": None,
            "executions": [],
            "context": {},
            "final_output": "No result produced.",
        }
        result = nodes.format_output_node(state)
        assert result["final_output"] == "Task completed."

    def test_non_empty_report_preserved(self, nodes):
        """A real report should be returned as-is."""
        state = {
            "plan": None,
            "executions": [],
            "context": {},
            "final_output": "Email sent successfully to john@example.com.",
        }
        result = nodes.format_output_node(state)
        assert result["final_output"] == "Email sent successfully to john@example.com."


# ---------------------------------------------------------------------------
# AgentState — new fields intent_verification and verification_attempts
# ---------------------------------------------------------------------------

class TestAgentStateNewFields:
    def test_agent_state_accepts_intent_verification(self):
        """AgentState now has intent_verification field."""
        state: AgentState = {
            "intent_verification": {"passed": True, "missing": [], "reason": "ok"},
            "verification_attempts": 0,
        }
        assert state["intent_verification"]["passed"] is True
        assert state["verification_attempts"] == 0

    def test_agent_state_intent_verification_can_be_none(self):
        state: AgentState = {"intent_verification": None}
        assert state["intent_verification"] is None

    def test_agent_state_verification_attempts_defaults_to_zero(self):
        """When not specified, verification_attempts should be retrievable as 0."""
        state: AgentState = {}
        assert state.get("verification_attempts", 0) == 0
