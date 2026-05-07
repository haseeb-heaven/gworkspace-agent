"""Tests for PR changes in execution modules:
- gws_assistant/execution/context_updater.py
- gws_assistant/execution/helpers.py
- gws_assistant/execution/resolver.py

Covers:
- context_updater: snippet_val fallback when empty -> "From: sender | Subject: subject | Date: date"
- helpers: _tableify function for converting lists to markdown tables
- helpers: last_code_result_table context key when parsed_value is a list/list-of-dicts
- resolver: inject_val unwrapped from API response wrappers (messages, files, events, etc.)
- resolver: from/subject/date header extraction for email entries
- resolver: from_ normalization for LLM code generation
"""
from __future__ import annotations

from typing import Any

from gws_assistant.execution.context_updater import (
    _normalize_entry,
    _tableify,
    _unwrap,
)

# ---------------------------------------------------------------------------
# helpers._tableify — extracted and tested directly
# ---------------------------------------------------------------------------

class TestTableify:
    """Test the _tableify function logic."""

    def test_list_of_dicts_produces_table(self) -> None:
        data = [{"Name": "Alice", "Age": "30"}, {"Name": "Bob", "Age": "25"}]
        table = _tableify(data)
        assert table is not None
        assert "| Name | Age |" in table
        assert "| Alice | 30 |" in table
        assert "| Bob | 25 |" in table

    def test_list_of_dicts_has_separator_row(self) -> None:
        data = [{"A": "1", "B": "2"}]
        table = _tableify(data)
        assert "|---|---|" in table

    def test_list_of_lists_produces_table(self) -> None:
        data = [["Name", "Score"], ["Alice", "95"], ["Bob", "87"]]
        table = _tableify(data)
        assert table is not None
        assert "| Name | Score |" in table
        assert "| Alice | 95 |" in table

    def test_empty_list_returns_none(self) -> None:
        assert _tableify([]) is None

    def test_list_of_strings_returns_none(self) -> None:
        """A list of strings (not dicts or lists) should return None."""
        assert _tableify(["a", "b", "c"]) is None

    def test_non_list_returns_none(self) -> None:
        assert _tableify("hello") is None
        assert _tableify(42) is None
        assert _tableify({"key": "val"}) is None

    def test_none_returns_none(self) -> None:
        assert _tableify(None) is None

    def test_list_of_dicts_with_missing_keys_pads_empty(self) -> None:
        """If a dict is missing a key, it should be padded with empty string."""
        data = [{"Name": "Alice", "Age": "30"}, {"Name": "Bob"}]
        table = _tableify(data)
        assert table is not None
        # Bob should have empty age, with consistent ' | ' padding
        assert "| Bob |  |" in table

    def test_single_row_dict(self) -> None:
        data = [{"Status": "OK"}]
        table = _tableify(data)
        assert table is not None
        assert "| Status |" in table
        assert "| OK |" in table

    def test_numeric_values_converted_to_str(self) -> None:
        data: list[dict[str, Any]] = [{"Count": 5, "Total": 100.5}]
        table = _tableify(data)
        assert table is not None
        assert "5" in table
        assert "100.5" in table


# ---------------------------------------------------------------------------
# resolver.inject_val unwrapping
# ---------------------------------------------------------------------------

class TestResolverInjectValUnwrapping:
    """Test unwrapping list of results from API response wrappers."""

    def test_messages_key_unwrapped(self) -> None:
        res = {"messages": [{"id": "m1"}, {"id": "m2"}], "resultSizeEstimate": 2}
        inject = _unwrap(res)
        assert inject == [{"id": "m1"}, {"id": "m2"}]

    def test_files_key_unwrapped(self) -> None:
        res = {"files": [{"id": "f1"}], "kind": "drive#fileList"}
        inject = _unwrap(res)
        assert inject == [{"id": "f1"}]

    def test_events_key_unwrapped(self) -> None:
        res = {"items": [{"id": "e1"}], "kind": "calendar#events"}
        inject = _unwrap(res)
        assert inject == [{"id": "e1"}]

    def test_tasks_key_unwrapped(self) -> None:
        res = {"items": [{"id": "t1"}], "kind": "tasks#tasks"}
        inject = _unwrap(res)
        assert inject == [{"id": "t1"}]

    def test_items_key_unwrapped(self) -> None:
        res = {"items": [{"id": "i1"}]}
        inject = _unwrap(res)
        assert inject == [{"id": "i1"}]

    def test_notes_key_unwrapped(self) -> None:
        res = {"notes": [{"name": "n1"}]}
        inject = _unwrap(res)
        assert inject == [{"name": "n1"}]

    def test_spaces_key_unwrapped(self) -> None:
        res = {"spaces": [{"name": "s1"}]}
        inject = _unwrap(res)
        assert inject == [{"name": "s1"}]

    def test_people_key_unwrapped(self) -> None:
        res = {"people": [{"resourceName": "p1"}]}
        inject = _unwrap(res)
        assert inject == [{"resourceName": "p1"}]

    def test_activities_key_unwrapped(self) -> None:
        res = {"activities": [{"id": "a1"}]}
        inject = _unwrap(res)
        assert inject == [{"id": "a1"}]

    def test_non_dict_not_changed(self) -> None:
        assert _unwrap("string") == "string"

    def test_dict_without_known_keys_not_changed(self) -> None:
        res = {"spreadsheetId": "abc", "values": [[1, 2]]}
        inject = _unwrap(res)
        assert inject == res  # unchanged

    def test_first_match_wins_for_multiple_keys(self) -> None:
        res = {"messages": [{"id": "m1"}], "files": [{"id": "f1"}]}
        inject = _unwrap(res)
        assert inject == [{"id": "m1"}]

    def test_empty_list_value_unwrapped(self) -> None:
        res = {"messages": [], "resultSizeEstimate": 0}
        inject = _unwrap(res)
        assert inject == []


# ---------------------------------------------------------------------------
# resolver.email_entry normalization
# ---------------------------------------------------------------------------

class TestResolverEmailEntryNormalization:
    """Test extracting from/subject/date and normalizing from_."""

    def test_payload_headers_extracted(self) -> None:
        entry = {
            "id": "m1",
            "payload": {
                "headers": [
                    {"name": "From", "value": "alice@example.com"},
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "Date", "value": "Mon, 1 Jan 2026"},
                ]
            }
        }
        result = _normalize_entry(entry)
        assert result["from"] == "alice@example.com"
        assert result["subject"] == "Test Subject"
        assert result["date"] == "Mon, 1 Jan 2026"

    def test_existing_from_not_overwritten(self) -> None:
        entry = {
            "from": "bob@example.com",
            "payload": {"headers": [{"name": "From", "value": "alice@example.com"}]}
        }
        result = _normalize_entry(entry)
        assert result["from"] == "bob@example.com"

    def test_snippet_fallback_when_empty(self) -> None:
        entry = {"from": "a@b.com", "subject": "Hi", "date": "Jan 1"}
        result = _normalize_entry(entry)
        assert result["snippet"] == "From: a@b.com | Subject: Hi | Date: Jan 1"

    def test_snippet_fallback_with_no_subject(self) -> None:
        entry = {"from": "a@b.com"}
        result = _normalize_entry(entry)
        assert "No Subject" in result["snippet"]

    def test_snippet_not_overwritten_when_present(self) -> None:
        entry = {"snippet": "existing snippet", "from": "alice@example.com"}
        result = _normalize_entry(entry)
        assert result["snippet"] == "existing snippet"

    def test_from_underscore_normalized(self) -> None:
        entry = {"from": "alice@example.com"}
        result = _normalize_entry(entry)
        assert result["from_"]["address"] == "alice@example.com"

    def test_from_underscore_not_overwritten_when_exists(self) -> None:
        entry = {"from": "alice@example.com", "from_": {"name": "Alice"}}
        result = _normalize_entry(entry)
        assert result["from_"] == {"name": "Alice"}


# ---------------------------------------------------------------------------
# context_updater.snippet_val fallback
# ---------------------------------------------------------------------------

class TestContextUpdaterSnippetFallback:
    """Test the _generate_fallback_snippet helper used by context_updater."""

    def setup_method(self) -> None:
        from gws_assistant.execution.context_updater import ContextUpdaterMixin
        self.updater = ContextUpdaterMixin()

    def test_snippet_present_returned_as_is(self) -> None:
        m = {"snippet": "Your order has been confirmed"}
        h_dict = {"from": "store@example.com", "subject": "Order Confirmed", "date": "2026-01-01"}
        result = self.updater._generate_fallback_snippet(m, h_dict)
        assert result == "Your order has been confirmed"

    def test_empty_snippet_triggers_fallback(self) -> None:
        m = {"snippet": ""}
        h_dict = {"from": "alice@example.com", "subject": "Hello", "date": "2026-01-02"}
        result = self.updater._generate_fallback_snippet(m, h_dict)
        assert result == "From: alice@example.com | Subject: Hello | Date: 2026-01-02"

    def test_none_snippet_triggers_fallback(self) -> None:
        m = {"snippet": None}
        h_dict = {"from": "bob@example.com", "subject": "Meeting", "date": "2026-02-15"}
        result = self.updater._generate_fallback_snippet(m, h_dict)
        assert result == "From: bob@example.com | Subject: Meeting | Date: 2026-02-15"

    def test_missing_snippet_key_triggers_fallback(self) -> None:
        m: dict[str, Any] = {}
        h_dict = {"from": "carol@example.com", "subject": "Invoice", "date": "2026-03-01"}
        result = self.updater._generate_fallback_snippet(m, h_dict)
        assert result == "From: carol@example.com | Subject: Invoice | Date: 2026-03-01"

    def test_fallback_with_missing_headers_uses_defaults(self) -> None:
        m: dict[str, Any] = {}
        h_dict: dict[str, str] = {}  # no from/subject/date
        result = self.updater._generate_fallback_snippet(m, h_dict)
        assert "Unknown" in result
        assert "No Subject" in result

    def test_whitespace_only_snippet_triggers_fallback(self) -> None:
        m = {"snippet": "   "}
        h_dict = {"from": "test@example.com", "subject": "Test", "date": "2026-01-01"}
        result = self.updater._generate_fallback_snippet(m, h_dict)
        # Whitespace-only snippet is stripped and triggers fallback
        assert result == "From: test@example.com | Subject: Test | Date: 2026-01-01"

    def test_fallback_format_includes_pipe_separators(self) -> None:
        m: dict[str, Any] = {}
        h_dict = {"from": "a@b.com", "subject": "Hello", "date": "2026-01-01"}
        result = self.updater._generate_fallback_snippet(m, h_dict)
        assert " | " in result
        parts = result.split(" | ")
        assert len(parts) == 3
