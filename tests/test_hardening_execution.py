import time
from unittest.mock import MagicMock

import gws_assistant.execution.helpers as helpers
from gws_assistant.execution.helpers import HelpersMixin
from gws_assistant.execution.resolver import _UNRESOLVED_MARKER, ResolverMixin
from gws_assistant.models import PlannedTask


class MockApp:
    def __init__(self):
        self.logger = MagicMock()
        self.config = MagicMock()
        self.runner = MagicMock()
        self.config.code_execution_enabled = True
        self.config.gws_timeout_seconds = 30

class MockHandler(ResolverMixin, HelpersMixin, MockApp):
    pass

def test_spreadsheet_auto_fetch_timeout():
    handler = MockHandler()
    handler.runner.run.side_effect = lambda *args, **kwargs: (time.sleep(0.1), MagicMock(success=True, stdout='{"values": [[1,2,3]]}'))[1]

    context = {
        "task_results": {
            "drive": {"files": [{"id": "f1", "name": "sheet1.csv"}]}
        },
        "injected_vars": ["sheet1.csv"] * 20  # Many variables to trigger limits
    }

    task = PlannedTask(id="task-1", service="code", action="execute", parameters={"code": "print(injected_vars)"})

    # We override constants for testing
    old_timeout = helpers.AUTO_FETCH_TOTAL_TIMEOUT
    old_attempts = helpers.MAX_TOTAL_FETCH_ATTEMPTS
    helpers.AUTO_FETCH_TOTAL_TIMEOUT = 0.2
    helpers.MAX_TOTAL_FETCH_ATTEMPTS = 5

    try:
        res = handler._handle_code_execution_task(task, context)
        # Verify that we didn't hang forever and it finished
        assert res.success is True
        # The runner should have been called, but not 20 times
        assert handler.runner.run.call_count <= 5
    finally:
        helpers.AUTO_FETCH_TOTAL_TIMEOUT = old_timeout
        helpers.MAX_TOTAL_FETCH_ATTEMPTS = old_attempts

def test_resolver_redos_protection():
    handler = MockHandler()
    # A string that might cause ReDoS if the regex is too complex
    # Many overlapping groups
    evil_string = "{" * 100 + "task-1" + "}" * 100

    start = time.time()
    res = handler._resolve_placeholders(evil_string, {"task_results": {}})
    duration = time.time() - start

    # Should resolve quickly (even if it returns unresolved marker)
    assert duration < 0.5
    assert _UNRESOLVED_MARKER in res or evil_string in res

def test_resolver_oversized_string_guard():
    handler = MockHandler()
    large_string = "A" * 110000 # > 100k

    start = time.time()
    res = handler._resolve_placeholders(large_string, {})
    duration = time.time() - start

    # Should return immediately without scanning
    assert duration < 0.1
    assert res == large_string

def test_tasks_create_expansion_all_invalid():
    handler = MockHandler()
    task = PlannedTask(id="task-1", service="tasks", action="create_task", parameters={"title": ["", None, "___UNRESOLVED_PLACEHOLDER___"]})

    expanded = handler._expand_task(task, {})

    assert len(expanded) == 1
    assert _UNRESOLVED_MARKER in expanded[0].parameters["title"]
    assert "All titles in list were invalid" in expanded[0].parameters["title"]

def test_telegram_unresolved_placeholder_signaling():
    handler = MockHandler()
    task = PlannedTask(id="task-1", service="telegram", action="send_message", parameters={"message": "{{missing_var}}"})

    res = handler._handle_telegram_task(task, {})

    assert res.success is False
    assert res.error_code == "UNRESOLVED_PLACEHOLDER"
    handler.runner.run.assert_not_called()
