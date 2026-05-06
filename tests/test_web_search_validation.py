import pytest
from unittest.mock import MagicMock, patch
from gws_assistant.execution.helpers import HelpersMixin
from gws_assistant.models import ExecutionResult

class MockTask:
    def __init__(self, parameters):
        self.parameters = parameters

class TestWebSearchValidation:
    @patch("gws_assistant.tools.web_search.web_search_tool")
    def test_handle_web_search_task_validation(self, mock_tool):
        # Setup mixin with mocks
        mixin = HelpersMixin()
        mixin.logger = MagicMock()
        mixin._resolve_placeholders = MagicMock()

        # Mock web_search_tool
        mock_tool.invoke.return_value = {"results": []}

        context = {}

        # Test Case 1: Valid query
        task = MockTask({"query": "Valid query"})
        mixin._resolve_placeholders.return_value = "Valid query"
        res = mixin._handle_web_search_task(task, context)
        assert res.success is True
        mock_tool.invoke.assert_called_with({"query": "Valid query"})

        # Test Case 2: None resolution -> Fallback
        task = MockTask({"query": "{{invalid}}"})
        mixin._resolve_placeholders.return_value = None
        res = mixin._handle_web_search_task(task, context)
        assert res.success is True
        mock_tool.invoke.assert_called_with({"query": "Google Workspace"})

        # Test Case 3: Empty string resolution -> Fallback
        mixin._resolve_placeholders.return_value = "   "
        res = mixin._handle_web_search_task(task, context)
        assert res.success is True
        mock_tool.invoke.assert_called_with({"query": "Google Workspace"})

        # Test Case 4: _UNRESOLVED_MARKER -> Fallback
        from gws_assistant.execution.resolver import _UNRESOLVED_MARKER
        mixin._resolve_placeholders.return_value = _UNRESOLVED_MARKER
        res = mixin._handle_web_search_task(task, context)
        assert res.success is True
        mock_tool.invoke.assert_called_with({"query": "Google Workspace"})

        # Test Case 5: Non-string resolution -> Fallback
        mixin._resolve_placeholders.return_value = 123
        res = mixin._handle_web_search_task(task, context)
        assert res.success is True
        mock_tool.invoke.assert_called_with({"query": "Google Workspace"})
