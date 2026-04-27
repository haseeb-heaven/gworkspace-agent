"""Tests for LLM plan completeness validation.

Verifies that _is_plan_complete() rejects plans that miss services
the user clearly asked for (e.g., user asks for sheets + email but
LLM only returns gmail.list_messages).
"""

from gws_assistant.langchain_agent import _is_plan_complete


class TestPlanCompleteness:
    """Tests for _is_plan_complete()."""

    def test_plan_with_sheets_when_user_asks_for_sheet(self):
        """Plan has sheets task → complete."""
        plan = {
            "tasks": [
                {"service": "gmail", "action": "list_messages"},
                {"service": "sheets", "action": "create_spreadsheet"},
                {"service": "gmail", "action": "send_message"},
            ]
        }
        assert _is_plan_complete(plan, "search gmail and save to a sheet then send email") is True

    def test_plan_missing_sheets_when_user_asks_for_sheet(self):
        """Plan has no sheets task but user mentioned sheet → incomplete."""
        plan = {
            "tasks": [
                {"service": "gmail", "action": "list_messages"},
            ]
        }
        assert _is_plan_complete(plan, "search gmail and save to a Google Sheet") is False

    def test_plan_missing_send_when_user_asks_to_send_email(self):
        """Plan has no send_message but user wants to send email → incomplete."""
        plan = {
            "tasks": [
                {"service": "gmail", "action": "list_messages"},
                {"service": "sheets", "action": "create_spreadsheet"},
            ]
        }
        assert _is_plan_complete(plan, "search gmail, create sheet, send email to x@y.com") is False

    def test_plan_with_send_message(self):
        """Plan has send_message → complete regarding email."""
        plan = {
            "tasks": [
                {"service": "gmail", "action": "list_messages"},
                {"service": "sheets", "action": "create_spreadsheet"},
                {"service": "gmail", "action": "send_message"},
            ]
        }
        assert _is_plan_complete(plan, "search gmail, create sheet, send email to x@y.com") is True

    def test_plan_for_simple_gmail_search(self):
        """User only asks for search, no sheets/email → always complete."""
        plan = {
            "tasks": [
                {"service": "gmail", "action": "list_messages"},
            ]
        }
        assert _is_plan_complete(plan, "search gmail for emails from john") is True

    def test_empty_plan_data(self):
        """Empty plan_data returns True (caught by is_valid_plan)."""
        assert _is_plan_complete({}, "whatever") is True
        assert _is_plan_complete({"tasks": []}, "whatever") is True

    def test_non_dict_plan(self):
        """Non-dict returns True (caught elsewhere)."""
        assert _is_plan_complete("not a dict", "whatever") is True

    def test_plan_missing_docs_when_user_asks_for_doc(self):
        """User mentions Google doc but plan has no docs task → incomplete."""
        plan = {
            "tasks": [
                {"service": "gmail", "action": "list_messages"},
            ]
        }
        assert _is_plan_complete(plan, "search gmail and create a google doc summary") is False

    def test_exact_user_request_from_bug_report(self):
        """Reproduces the exact scenario: user asks for Sheet + email, gets only list_messages."""
        plan = {
            "tasks": [
                {
                    "id": "task-1",
                    "service": "gmail",
                    "action": "list_messages",
                    "parameters": {"q": "from:noreply@x.ai", "maxResults": 100},
                }
            ]
        }
        request = (
            "Search Gmail for all emails from 'noreply@x.ai' "
            "extract sender names and email addresses to a new Google Sheet, "
            "then send email to haseebmir.hm@gmail.com with the sheet link"
        )
        assert _is_plan_complete(plan, request) is False
