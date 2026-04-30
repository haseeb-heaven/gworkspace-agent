import pytest
pytestmark = pytest.mark.gmail

import base64

from gws_assistant.execution.context_updater import ContextUpdaterMixin


class MockTask:
    def __init__(self, service="gmail", action="get_message", task_id="task-1"):
        self.service = service
        self.action = action
        self.id = task_id

def test_find_body_robustness():
    updater = ContextUpdaterMixin()
    task = MockTask()

    # 1. Test with malformed payload (not a dict)
    context = {}
    data = {"payload": ["not a dict"]}
    updater._update_context_from_result(data, context, task)
    assert "gmail_message_body_text" not in context

    # 2. Test with body as non-dict
    context = {}
    data = {"payload": {"body": "should be a dict"}}
    updater._update_context_from_result(data, context, task)
    assert "gmail_message_body_text" not in context

    # 3. Test with parts as non-list
    context = {}
    data = {"payload": {"parts": "should be a list"}}
    updater._update_context_from_result(data, context, task)
    assert "gmail_message_body_text" not in context

    # 4. Test successful recursive body finding
    context = {}
    body_content = "Hello World"
    encoded_body = base64.urlsafe_b64encode(body_content.encode("utf-8")).decode("utf-8")
    data = {
        "payload": {
            "parts": [
                {
                    "parts": [
                        {"body": {"data": encoded_body}}
                    ]
                }
            ]
        }
    }
    updater._update_context_from_result(data, context, task)
    assert context.get("gmail_message_body_text") == body_content

def test_find_body_handles_none_p():
    # This specifically tests 'if not isinstance(p, dict): return ""'
    # Although p_item loop in context_updater already checks isinstance(p_item, dict)
    # the recursive call 'res = find_body(part)' could potentially pass something weird if parts had non-dicts.
    updater = ContextUpdaterMixin()
    task = MockTask()
    context = {}
    data = {
        "payload": {
            "parts": [None, 123, []]
        }
    }
    # This should not crash
    updater._update_context_from_result(data, context, task)
    assert "gmail_message_body_text" not in context
