"""Tests for resolver.py — covers ResolverMixin methods and placeholder resolution."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from gws_assistant.execution.resolver import ResolverMixin
from gws_assistant.models import PlannedTask


@pytest.fixture

def logger():

    return logging.getLogger("test_resolver")





class MockResolver(ResolverMixin):

    def __init__(self, config=None, runner=None, logger_=None):

        self.config = config

        self.runner = runner

        self.logger = logger_ or logging.getLogger("test")





class TestResolverMixin:

    def test_expand_task_no_expansion(self, logger):

        resolver = MockResolver(logger_=logger)

        task = PlannedTask(id="1", service="drive", action="create_file", parameters={"title": "test"})

        expanded = resolver._expand_task(task, {})

        assert len(expanded) == 1

        assert expanded[0] == task



    def test_expand_task_gmail_get_message(self, logger):

        resolver = MockResolver(logger_=logger)

        task = PlannedTask(id="1", service="gmail", action="get_message", parameters={"message_id": ["id1", "id2"]})

        expanded = resolver._expand_task(task, {})

        assert len(expanded) == 2

        assert expanded[0].parameters["message_id"] == "id1"

        assert expanded[1].parameters["message_id"] == "id2"

        assert expanded[0].id == "1-1"

        assert expanded[1].id == "1-2"



    def test_expand_task_gmail_get_message_context_injection(self, logger):

        resolver = MockResolver(logger_=logger)

        task = PlannedTask(id="1", service="gmail", action="get_message", parameters={"message_id": "{{message_id}}"})

        context = {"gmail_message_ids": ["ctx1", "ctx2"]}

        expanded = resolver._expand_task(task, context)

        assert len(expanded) == 2

        assert expanded[0].parameters["message_id"] == "ctx1"

        assert expanded[1].parameters["message_id"] == "ctx2"



    def test_expand_task_drive_move_file(self, logger):

        resolver = MockResolver(logger_=logger)

        task = PlannedTask(id="1", service="drive", action="move_file", parameters={"file_id": ["f1", "f2"]})

        expanded = resolver._expand_task(task, {})

        assert len(expanded) == 2

        assert expanded[0].parameters["file_id"] == "f1"



    def test_expand_task_drive_delete_file(self, logger):

        resolver = MockResolver(logger_=logger)

        task = PlannedTask(id="1", service="drive", action="delete_file", parameters={"file_id": "$placeholder"})

        context = {"drive_file_ids": ["df1", "df2"]}

        expanded = resolver._expand_task(task, context)

        assert len(expanded) == 2

        assert expanded[0].parameters["file_id"] == "df1"



    def test_resolve_task_sheets_range_fix(self, logger):

        resolver = MockResolver(logger_=logger)

        task = PlannedTask(id="1", service="sheets", action="append_values", parameters={"range": "Sheet1!A1"})

        context = {"last_spreadsheet_title": "My Sheet"}

        resolved = resolver._resolve_task(task, context)

        assert resolved.parameters["range"] == "'My Sheet'!A1"



    def test_resolve_task_gmail_body_links(self, logger):

        resolver = MockResolver(logger_=logger)

        # Mock _get_artifact_links_body

        resolver._get_artifact_links_body = MagicMock(return_value="body with links")

        task = PlannedTask(id="1", service="gmail", action="send_message", parameters={"body": "original body"})

        resolved = resolver._resolve_task(task, {})

        assert resolved.parameters["body"] == "body with links"



    def test_resolve_task_drive_export_mime_inference(self, logger):

        resolver = MockResolver(logger_=logger)

        context = {"last_spreadsheet_id": "s123"}

        task = PlannedTask(id="1", service="drive", action="export_file", parameters={"file_id": "s123"})

        resolved = resolver._resolve_task(task, context)

        assert resolved.parameters["source_mime"] == "application/vnd.google-apps.spreadsheet"



    def test_resolve_task_sheets_id_fallback(self, logger):

        resolver = MockResolver(logger_=logger)

        context = {"last_spreadsheet_id": "fallback_id"}

        task = PlannedTask(id="1", service="sheets", action="get_values", parameters={"spreadsheet_id": "{{id}}"})

        resolved = resolver._resolve_task(task, context)

        assert resolved.parameters["spreadsheet_id"] == "fallback_id"



    def test_resolve_task_security_redirect(self, logger):

        config = MagicMock()

        config.default_recipient_email = "secure@example.com"

        resolver = MockResolver(config=config, logger_=logger)

        task = PlannedTask(id="1", service="gmail", action="send_message", parameters={"to_email": "hack@attacker.com"})

        resolved = resolver._resolve_task(task, {})

        assert resolved.parameters["to_email"] == "secure@example.com"



    def test_resolve_placeholders_shorthand_semantic(self, logger):

        resolver = MockResolver(logger_=logger)

        context = {"task_results": {"get_message": "msg_content"}}

        val = resolver._resolve_placeholders("{{:get_message}}", context)

        assert val == "msg_content"



    def test_resolve_placeholders_shorthand_with_colon_braces(self, logger):

        resolver = MockResolver(logger_=logger)

        context = {"task_results": {"get_message": "msg_content"}}

        val = resolver._resolve_placeholders("{{:get_message}}", context)

        assert val == "msg_content"



    def test_resolve_placeholders_smart_unwrap_content(self, logger):

        resolver = MockResolver(logger_=logger)

        context = {"task_results": {"task-1": {"content": "hello"}}}

        val = resolver._resolve_placeholders("{{task-1}}", context)

        assert val == "hello"



    def test_resolve_placeholders_smart_unwrap_list_singular_suffix(self, logger):

        resolver = MockResolver(logger_=logger)

        context = {"task_results": {"task-1": {"files": [{"id": "f1", "mimeType": "text/plain"}]}}}

        # {{task-1.files.id}} -> ['f1'] -> smart unwrap to 'f1'

        val = resolver._resolve_placeholders("{{task-1.id}}", context)

        assert val == "f1"



    def test_resolve_placeholders_partial_string(self, logger):

        resolver = MockResolver(logger_=logger)

        context = {"task_results": {"task-1": "World"}}

        val = resolver._resolve_placeholders("Hello {{task-1}}!", context)

        assert val == "Hello World!"



    def test_resolve_placeholders_context_nested_index(self, logger):

        resolver = MockResolver(logger_=logger)

        context = {

            "contacts_summary_rows": [

                ["Alice", "alice@example.com", "+1-555-0100"],

                ["Bob", "bob@example.com", "+1-555-0101"],

            ]

        }

        val = resolver._resolve_placeholders(

            "Top contact: {{contacts_summary_rows[0][0]}} ({{contacts_summary_rows[0][1]}})",

            context,

        )

        assert val == "Top contact: Alice (alice@example.com)"



    def test_resolve_placeholders_context_nested_list_return(self, logger):

        resolver = MockResolver(logger_=logger)

        context = {"contacts_summary_rows": [["Alice", "alice@example.com"]]}

        val = resolver._resolve_placeholders("{{contacts_summary_rows[0]}}", context)

        assert val == ["Alice", "alice@example.com"]



    def test_get_value_by_path_complex(self, logger):

        resolver = MockResolver(logger_=logger)

        data = {

            "task-1": {

                "files": [

                    {"id": "f1", "name": "file1"},

                    {"id": "f2", "name": "file2"}

                ]

            }

        }

        # Exact match

        assert resolver._get_value_by_path(data, "task-1") == data["task-1"]

        # Nested access

        assert resolver._get_value_by_path(data, "task-1.files[0].id") == "f1"

        # Auto-unwrap files

        assert resolver._get_value_by_path(data, "task-1[1].name") == "file2"

        # Mapping across list

        assert resolver._get_value_by_path(data, "task-1.files.name") == ["file1", "file2"]



    def test_get_value_by_path_flattened_key_with_array_index(self, logger):

        resolver = MockResolver(logger_=logger)

        # Test case for flattened keys like 'task-7.result' with array indexing
        data = {

            "task-7.result": ["action_item_1", "action_item_2", "action_item_3"],

            "task-7.stdout": "code execution output",

            "7.result": ["alt_1", "alt_2"]

        }

        # Access first element of flattened key with array index

        assert resolver._get_value_by_path(data, "task-7.result[0]") == "action_item_1"

        # Access second element

        assert resolver._get_value_by_path(data, "task-7.result[1]") == "action_item_2"

        # Access out of bounds should return None

        assert resolver._get_value_by_path(data, "task-7.result[10]") is None

        # Access non-list flattened key with index should return None

        assert resolver._get_value_by_path(data, "task-7.stdout[0]") is None

        # Test with numeric key variant

        assert resolver._get_value_by_path(data, "7.result[0]") == "alt_1"



    def test_get_value_by_path_flattened_key_with_array_index_and_field_access(self, logger):

        resolver = MockResolver(logger_=logger)

        # Test case for flattened keys like 'task-1.messages' (list of dicts) with array indexing and field access
        # This is the scenario that was failing in the user's command
        data = {

            "task-1.messages": [

                {"id": "msg1", "subject": "Subject 1"},

                {"id": "msg2", "subject": "Subject 2"},

                {"id": "msg3", "subject": "Subject 3"}

            ]

        }

        # Access id field of first message

        assert resolver._get_value_by_path(data, "task-1.messages[0].id") == "msg1"

        # Access subject field of second message

        assert resolver._get_value_by_path(data, "task-1.messages[1].subject") == "Subject 2"

        # Access out of bounds should return None

        assert resolver._get_value_by_path(data, "task-1.messages[10].id") is None

        # Access non-existent field should return None

        assert resolver._get_value_by_path(data, "task-1.messages[0].nonexistent") is None



    def test_get_value_by_path_flattened_key_field_mapping(self, logger):

        resolver = MockResolver(logger_=logger)

        # Test case for mapping a field across a flattened list
        # This handles 'task-1.messages.id' to extract all IDs from the messages list
        data = {

            "task-1.messages": [

                {"id": "msg1", "subject": "Subject 1"},

                {"id": "msg2", "subject": "Subject 2"},

                {"id": "msg3", "subject": "Subject 3"}

            ]

        }

        # Map id field across all messages

        assert resolver._get_value_by_path(data, "task-1.messages.id") == ["msg1", "msg2", "msg3"]

        # Map subject field across all messages

        assert resolver._get_value_by_path(data, "task-1.messages.subject") == ["Subject 1", "Subject 2", "Subject 3"]

        # Map across empty list

        data_empty = {"task-1.messages": []}

        assert resolver._get_value_by_path(data_empty, "task-1.messages.id") == []

        # Map across list with non-dict items should return list of None

        data_mixed = {"task-1.messages": [{"id": "msg1"}, "string", 123]}

        result = resolver._get_value_by_path(data_mixed, "task-1.messages.id")

        assert result[0] == "msg1"

        assert result[1] is None

        assert result[2] is None



    def test_get_artifact_links_body(self, logger):

        resolver = MockResolver(logger_=logger)

        context = {"last_document_url": "doc_url", "last_spreadsheet_url": "sheet_url"}

        body = resolver._get_artifact_links_body("Hello", context)

        assert "Google Doc: doc_url" in body

        assert "Google Sheet: sheet_url" in body



    def test_resolve_placeholders_large_artifact_skip(self, logger):

        resolver = MockResolver(logger_=logger)

        large_val = "A" * 6000

        # No placeholders

        result = resolver._resolve_placeholders(large_val, {})

        assert result == large_val



    def test_resolve_placeholders_flatten_list(self, logger):

        resolver = MockResolver(logger_=logger)

        context = {"key": ["a", "b"]}

        val = ["{{key}}"]

        result = resolver._resolve_placeholders(val, context)

        assert result == ["a", "b"]



    def test_resolve_placeholders_legacy(self, logger):

        resolver = MockResolver(logger_=logger)

        context = {"last_spreadsheet_id": "sheet123"}

        val = resolver._resolve_placeholders("$last_spreadsheet_id", context)

        assert val == "sheet123"



    def test_resolve_placeholders_braces(self, logger):

        resolver = MockResolver(logger_=logger)

        context = {"task_results": {"task-1": "result1"}}

        val = resolver._resolve_placeholders("{{task-1}}", context)

        assert val == "result1"



    def test_resolve_placeholders_shorthand(self, logger):

        resolver = MockResolver(logger_=logger)

        context = {"task_results": {"create_doc": "doc123"}}

        val = resolver._resolve_placeholders("{{:doc}}", context)

        assert val == "doc123"



    def test_resolve_placeholders_recursive(self, logger):

        resolver = MockResolver(logger_=logger)

        context = {"task_results": {"task-1": "result1"}, "var": "prefix-{{task-1}}"}

        val = resolver._resolve_placeholders(["{{var}}"], context)

        assert val == ["prefix-{{task-1}}"]



    def test_resolve_placeholders_max_depth(self, logger):

        resolver = MockResolver(logger_=logger)

        # Deep nested structure

        val = ["a"]

        for _ in range(20):

            val = [val]

        result = resolver._resolve_placeholders(val, {}, depth=0)

        # It should hit max depth and return

        assert isinstance(result, list)



    def test_resolve_placeholders_dict(self, logger):

        resolver = MockResolver(logger_=logger)

        context = {"key": "val"}

        val = {"p": "{{key}}"}

        result = resolver._resolve_placeholders(val, context)

        assert result["p"] == "val"
