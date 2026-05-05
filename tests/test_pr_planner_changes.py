"""Tests for PR changes in gws_assistant/planner.py.

Covers:
- list_messages: fields now includes 'snippet' in addition to id/threadId
- get_message: accepts both 'message_id' and 'id' parameters
- batch_update (docs): validates that JSON body is not empty
"""
from __future__ import annotations

import json

import pytest

from gws_assistant.exceptions import ValidationError
from gws_assistant.planner import CommandPlanner


@pytest.fixture
def planner():
    return CommandPlanner()


# ---------------------------------------------------------------------------
# list_messages — fields includes snippet
# ---------------------------------------------------------------------------

class TestListMessagesSnippet:
    def test_list_messages_includes_snippet_in_fields(self, planner):
        """PR change: list_messages now requests snippet in fields."""
        args = planner.build_command("gmail", "list_messages", {})
        params_idx = args.index("--params") + 1
        params = json.loads(args[params_idx])
        assert "snippet" in params["fields"]

    def test_list_messages_fields_include_id_and_thread_id(self, planner):
        """Regression: id and threadId are still requested in fields."""
        args = planner.build_command("gmail", "list_messages", {})
        params_idx = args.index("--params") + 1
        params = json.loads(args[params_idx])
        assert "id" in params["fields"]
        assert "threadId" in params["fields"]

    def test_list_messages_fields_format_is_messages_tuple(self, planner):
        """Fields should use messages(id,threadId,snippet) format."""
        args = planner.build_command("gmail", "list_messages", {})
        params_idx = args.index("--params") + 1
        params = json.loads(args[params_idx])
        fields = params["fields"]
        # Should start with messages(
        assert fields.startswith("messages(")

    def test_list_messages_with_max_results(self, planner):
        args = planner.build_command("gmail", "list_messages", {"max_results": 5})
        params_idx = args.index("--params") + 1
        params = json.loads(args[params_idx])
        assert params["maxResults"] == 5

    def test_list_messages_with_query(self, planner):
        args = planner.build_command("gmail", "list_messages", {"q": "is:unread"})
        params_idx = args.index("--params") + 1
        params = json.loads(args[params_idx])
        assert "q" in params


# ---------------------------------------------------------------------------
# get_message — accepts both message_id and id
# ---------------------------------------------------------------------------

class TestGetMessageIdParameter:
    def test_get_message_with_message_id(self, planner):
        """message_id parameter still works."""
        args = planner.build_command("gmail", "get_message", {"message_id": "abc123"})
        params_idx = args.index("--params") + 1
        params = json.loads(args[params_idx])
        assert params["id"] == "abc123"

    def test_get_message_with_id_parameter(self, planner):
        """PR change: 'id' parameter is now accepted in addition to 'message_id'."""
        args = planner.build_command("gmail", "get_message", {"id": "xyz789"})
        params_idx = args.index("--params") + 1
        params = json.loads(args[params_idx])
        assert params["id"] == "xyz789"

    def test_get_message_message_id_takes_priority_over_id(self, planner):
        """When both are provided, message_id takes priority."""
        args = planner.build_command("gmail", "get_message", {"message_id": "primary", "id": "secondary"})
        params_idx = args.index("--params") + 1
        params = json.loads(args[params_idx])
        assert params["id"] == "primary"

    def test_get_message_without_id_uses_placeholder(self, planner):
        """Without any id, falls back to {{message_id}} placeholder."""
        args = planner.build_command("gmail", "get_message", {})
        params_idx = args.index("--params") + 1
        params = json.loads(args[params_idx])
        assert params["id"] == "{{message_id}}"

    def test_get_message_command_structure(self, planner):
        """Regression: command structure should be gmail/users/messages/get."""
        args = planner.build_command("gmail", "get_message", {"message_id": "msg1"})
        assert args[:4] == ["gmail", "users", "messages", "get"]


# ---------------------------------------------------------------------------
# batch_update (docs) — validates non-empty JSON body
# ---------------------------------------------------------------------------

class TestBatchUpdateJsonBodyValidation:
    def test_batch_update_with_text_produces_valid_json_body(self, planner):
        """Normal batch_update with text should succeed."""
        args = planner.build_command(
            "docs",
            "batch_update",
            {"document_id": "doc123", "text": "Hello, world!"},
        )
        json_idx = args.index("--json") + 1
        body = json.loads(args[json_idx])
        assert "requests" in body
        assert len(body["requests"]) > 0

    def test_batch_update_json_body_contains_insert_text(self, planner):
        args = planner.build_command(
            "docs",
            "batch_update",
            {"document_id": "doc123", "text": "Some content"},
        )
        json_idx = args.index("--json") + 1
        body = json.loads(args[json_idx])
        assert "insertText" in body["requests"][0]

    def test_batch_update_json_body_contains_text(self, planner):
        args = planner.build_command(
            "docs",
            "batch_update",
            {"document_id": "doc123", "text": "My inserted text"},
        )
        json_idx = args.index("--json") + 1
        body = json.loads(args[json_idx])
        insert_text = body["requests"][0]["insertText"]
        assert insert_text["text"] == "My inserted text"

    def test_batch_update_with_index_uses_location(self, planner):
        """When 'index' is provided, use location with index."""
        args = planner.build_command(
            "docs",
            "batch_update",
            {"document_id": "doc123", "text": "Hello", "index": 10},
        )
        json_idx = args.index("--json") + 1
        body = json.loads(args[json_idx])
        insert_text = body["requests"][0]["insertText"]
        assert "location" in insert_text
        assert insert_text["location"]["index"] == 10

    def test_batch_update_without_index_uses_end_of_segment(self, planner):
        """Without index, uses endOfSegmentLocation."""
        args = planner.build_command(
            "docs",
            "batch_update",
            {"document_id": "doc123", "text": "Hello"},
        )
        json_idx = args.index("--json") + 1
        body = json.loads(args[json_idx])
        insert_text = body["requests"][0]["insertText"]
        assert "endOfSegmentLocation" in insert_text

    def test_batch_update_command_structure(self, planner):
        """Regression: command structure should be docs/documents/batchUpdate."""
        args = planner.build_command(
            "docs",
            "batch_update",
            {"document_id": "doc123", "text": "Content"},
        )
        assert args[:3] == ["docs", "documents", "batchUpdate"]

    def test_batch_update_document_id_in_params(self, planner):
        args = planner.build_command(
            "docs",
            "batch_update",
            {"document_id": "doc456", "text": "Hello"},
        )
        params_idx = args.index("--params") + 1
        params = json.loads(args[params_idx])
        assert params["documentId"] == "doc456"