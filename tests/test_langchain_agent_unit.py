"""Unit tests for langchain_agent.py — covers helper functions and logic."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from litellm.exceptions import RateLimitError
from gws_assistant.langchain_agent import (
    _backoff_delay,
    _is_rate_limit_error,
    _is_endpoint_missing_error,
    _request_requires_send_email,
    _plan_has_send_task,
    _extract_explicit_email,
    _derive_next_task_id,
    _derive_email_subject,
    _derive_email_body_placeholder,
    is_valid_plan,
    _is_plan_complete,
    _safe_invoke_structured_output,
)


def test_backoff_delay():
    assert _backoff_delay(0) == 2.0
    assert _backoff_delay(1) == 4.0
    assert _backoff_delay(100) == 30.0


def test_is_rate_limit_error():
    assert _is_rate_limit_error(Exception("429 Too Many Requests")) is True
    assert _is_rate_limit_error(Exception("Rate limit reached")) is True
    assert _is_rate_limit_error(Exception("Quota exceeded")) is True
    assert _is_rate_limit_error(Exception("Generic error")) is False


def test_is_endpoint_missing_error():
    assert _is_endpoint_missing_error(Exception("404 Not Found")) is True
    assert _is_endpoint_missing_error(Exception("no endpoints found")) is True
    assert _is_endpoint_missing_error(Exception("Generic error")) is False


def test_request_requires_send_email():
    assert _request_requires_send_email("send an email to test@example.com") is True
    assert _request_requires_send_email("email me the report") is True
    assert _request_requires_send_email("just list files") is False
    assert _request_requires_send_email("create a doc") is False


def test_plan_has_send_task():
    assert _plan_has_send_task([{"service": "gmail", "action": "send_message"}]) is True
    assert _plan_has_send_task([{"service": "drive", "action": "list_files"}]) is False
    assert _plan_has_send_task(["not a dict"]) is False


def test_extract_explicit_email():
    assert _extract_explicit_email("send to test@example.com") == "test@example.com"
    assert _extract_explicit_email("email haseeb mir <haseeb@example.com>") == "haseeb@example.com"
    assert _extract_explicit_email("no email here") == ""


def test_derive_next_task_id():
    assert _derive_next_task_id([]) == "task-1"
    assert _derive_next_task_id([{"id": "task-1"}]) == "task-2"
    assert _derive_next_task_id([{"id": "1"}]) == "2"


def test_derive_email_subject():
    assert _derive_email_subject("Please send me the report") == "Report"
    assert _derive_email_subject("find my files") == "My files"
    assert _derive_email_subject("send") == "Your Requested Summary"
    assert _derive_email_subject("A" * 100) == ("A" * 57) + "..."


def test_derive_email_body_placeholder():
    assert _derive_email_body_placeholder([{"service": "code"}]) == "$code_output"
    assert _derive_email_body_placeholder([{"service": "sheets"}]) == "$sheet_summary_table"
    assert _derive_email_body_placeholder([{"service": "gmail"}]) == "$gmail_summary_table"
    assert _derive_email_body_placeholder([{"service": "search"}]) == "$search_summary_table"
    assert _derive_email_body_placeholder([]) == "Here are the results of your Google Workspace request."


def test_is_valid_plan_invalid_inputs():
    assert is_valid_plan(None) is False
    assert is_valid_plan({"tasks": []}) is False
    assert is_valid_plan({"tasks": ["not a dict"]}) is False


def test_is_valid_plan_unknown_service():
    assert is_valid_plan({"tasks": [{"service": "unknown", "action": "act"}]}) is False


def test_is_valid_plan_valid():
    # 'gmail' and 'send_message' are known
    plan = {
        "tasks": [{
            "id": "1",
            "service": "gmail",
            "action": "send_message",
            "parameters": {"to_email": "t@e.com", "subject": "S", "body": "B"}
        }]
    }
    # Note: depends on actual SERVICES catalog.
    # If I don't want to depend on catalog, I should mock it or just assume it's there.
    # Let's assume 'gmail' 'send_message' is there.
    assert is_valid_plan(plan) is True


def test_is_plan_complete():
    # User mentions sheets, plan must have sheets
    assert _is_plan_complete({"tasks": [{"service": "drive"}]}, "create a spreadsheet") is False
    assert _is_plan_complete({"tasks": [{"service": "sheets"}]}, "create a spreadsheet") is True
    
    # User mentions send email, plan must have send_message
    assert _is_plan_complete({"tasks": [{"service": "gmail", "action": "list"}]}, "send an email") is False
    assert _is_plan_complete({"tasks": [{"service": "gmail", "action": "send_message"}]}, "send an email") is True


def test_safe_invoke_structured_output_success():
    chain = MagicMock()
    chain.invoke.return_value = {"tasks": []}
    logger = MagicMock()
    res = _safe_invoke_structured_output(chain, {}, logger)
    assert res == {"tasks": []}


def test_safe_invoke_structured_output_parse_error():
    chain = MagicMock()
    chain.invoke.side_effect = TypeError("Parse error")
    logger = MagicMock()
    res = _safe_invoke_structured_output(chain, {}, logger)
    assert res is None
    assert logger.info.called


def test_safe_invoke_structured_output_rate_limit_reraise():
    chain = MagicMock()
    chain.invoke.side_effect = RateLimitError("429", model="m", llm_provider="p")
    logger = MagicMock()
    with pytest.raises(RateLimitError):
        _safe_invoke_structured_output(chain, {}, logger)
