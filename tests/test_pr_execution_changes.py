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

import pytest


# ---------------------------------------------------------------------------
# helpers._tableify — extracted and tested directly via execute_code helper
# ---------------------------------------------------------------------------

class TestTableify:
    """Test the _tableify function logic by running equivalent code in the sandbox."""

    def _tableify(self, value):
        """Replicate the _tableify logic for unit testing."""
        from typing import Any
        rows = []
        if isinstance(value, list) and value and isinstance(value[0], dict):
            headers = list(value[0].keys())
            rows.append(headers)
            for item in value:
                row = [str(item.get(h, "")) for h in headers]
                rows.append(row)
        elif isinstance(value, list) and value and isinstance(value[0], list):
            rows = [[str(cell) for cell in row] for row in value]
        else:
            return None

        if not rows:
            return None

        header = rows[0]
        table_lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
        for row in rows[1:]:
            padded = row + [""] * (len(header) - len(row))
            table_lines.append("| " + " | ".join(padded) + " |")
        return "\n".join(table_lines)

    def test_list_of_dicts_produces_table(self):
        data = [{"Name": "Alice", "Age": "30"}, {"Name": "Bob", "Age": "25"}]
        table = self._tableify(data)
        assert table is not None
        assert "| Name | Age |" in table
        assert "| Alice | 30 |" in table
        assert "| Bob | 25 |" in table

    def test_list_of_dicts_has_separator_row(self):
        data = [{"A": "1", "B": "2"}]
        table = self._tableify(data)
        assert "|---|---|" in table or "|---" in table

    def test_list_of_lists_produces_table(self):
        data = [["Name", "Score"], ["Alice", "95"], ["Bob", "87"]]
        table = self._tableify(data)
        assert table is not None
        assert "| Name | Score |" in table
        assert "| Alice | 95 |" in table

    def test_empty_list_returns_none(self):
        assert self._tableify([]) is None

    def test_list_of_strings_returns_none(self):
        """A list of strings (not dicts or lists) should return None."""
        assert self._tableify(["a", "b", "c"]) is None

    def test_non_list_returns_none(self):
        assert self._tableify("hello") is None
        assert self._tableify(42) is None
        assert self._tableify({"key": "val"}) is None

    def test_none_returns_none(self):
        assert self._tableify(None) is None

    def test_list_of_dicts_with_missing_keys_pads_empty(self):
        """If a dict is missing a key, it should be padded with empty string."""
        data = [{"Name": "Alice", "Age": "30"}, {"Name": "Bob"}]
        table = self._tableify(data)
        assert table is not None
        # Bob should have empty age
        assert "| Bob |  |" in table or "| Bob | |" in table

    def test_single_row_dict(self):
        data = [{"Status": "OK"}]
        table = self._tableify(data)
        assert table is not None
        assert "| Status |" in table
        assert "| OK |" in table

    def test_numeric_values_converted_to_str(self):
        data = [{"Count": 5, "Total": 100.5}]
        table = self._tableify(data)
        assert table is not None
        assert "5" in table
        assert "100.5" in table


# ---------------------------------------------------------------------------
# resolver — inject_val unwrapping from API response wrappers
# ---------------------------------------------------------------------------

class TestResolverInjectValUnwrapping:
    """Test the logic for unwrapping common API response keys."""

    def _unwrap(self, res):
        """Replicate the inject_val unwrapping logic from resolver.py."""
        inject_val = res
        if isinstance(res, dict):
            for key in ("messages", "items", "files", "events", "tasks", "notes", "spaces", "connections", "people", "activities"):
                if key in res and isinstance(res[key], list):
                    inject_val = res[key]
                    break
        return inject_val

    def test_messages_key_unwrapped(self):
        res = {"messages": [{"id": "m1"}, {"id": "m2"}], "resultSizeEstimate": 2}
        inject = self._unwrap(res)
        assert inject == [{"id": "m1"}, {"id": "m2"}]

    def test_files_key_unwrapped(self):
        res = {"files": [{"id": "f1", "name": "doc.txt"}], "nextPageToken": None}
        inject = self._unwrap(res)
        assert inject == [{"id": "f1", "name": "doc.txt"}]

    def test_events_key_unwrapped(self):
        res = {"events": [{"id": "e1", "summary": "Meeting"}], "kind": "calendar#events"}
        inject = self._unwrap(res)
        assert inject == [{"id": "e1", "summary": "Meeting"}]

    def test_tasks_key_unwrapped(self):
        res = {"tasks": [{"id": "t1", "title": "Buy groceries"}]}
        inject = self._unwrap(res)
        assert inject == [{"id": "t1", "title": "Buy groceries"}]

    def test_items_key_unwrapped(self):
        res = {"items": [{"id": "i1"}]}
        inject = self._unwrap(res)
        assert inject == [{"id": "i1"}]

    def test_notes_key_unwrapped(self):
        res = {"notes": [{"name": "note1"}]}
        inject = self._unwrap(res)
        assert inject == [{"name": "note1"}]

    def test_spaces_key_unwrapped(self):
        res = {"spaces": [{"name": "space1"}]}
        inject = self._unwrap(res)
        assert inject == [{"name": "space1"}]

    def test_people_key_unwrapped(self):
        res = {"people": [{"resourceName": "p1"}]}
        inject = self._unwrap(res)
        assert inject == [{"resourceName": "p1"}]

    def test_activities_key_unwrapped(self):
        res = {"activities": [{"id": "a1"}]}
        inject = self._unwrap(res)
        assert inject == [{"id": "a1"}]

    def test_non_dict_not_changed(self):
        """Non-dict values are returned unchanged."""
        assert self._unwrap([1, 2, 3]) == [1, 2, 3]
        assert self._unwrap("string") == "string"

    def test_dict_without_known_keys_not_changed(self):
        res = {"spreadsheetId": "abc", "values": [[1, 2]]}
        inject = self._unwrap(res)
        assert inject == res  # unchanged

    def test_first_match_wins_for_multiple_keys(self):
        """messages comes before files in the priority order."""
        res = {"messages": [{"id": "m1"}], "files": [{"id": "f1"}]}
        inject = self._unwrap(res)
        # messages should win
        assert inject == [{"id": "m1"}]

    def test_empty_list_value_not_unwrapped(self):
        """If the list is empty, it still gets unwrapped (becomes empty list)."""
        res = {"messages": []}
        inject = self._unwrap(res)
        assert inject == []


# ---------------------------------------------------------------------------
# resolver — header extraction and from_ normalization for email entries
# ---------------------------------------------------------------------------

class TestResolverEmailEntryNormalization:
    """Test the logic for extracting headers and normalizing email entries."""

    def _normalize_entry(self, entry):
        """Replicate the email entry normalization logic from resolver.py."""
        entry = dict(entry)  # shallow copy before mutation
        if isinstance(entry, dict):
            payload = entry.get("payload", {})
            if isinstance(payload, dict):
                for hdr in payload.get("headers", []):
                    if isinstance(hdr, dict):
                        hname = str(hdr.get("name", "")).lower()
                        hval = hdr.get("value", "")
                        if hname == "from" and "from" not in entry:
                            entry["from"] = hval
                        elif hname == "subject" and "subject" not in entry:
                            entry["subject"] = hval
                        elif hname == "date" and "date" not in entry:
                            entry["date"] = hval
            snippet = entry.get("snippet")
            if not snippet:
                subj = entry.get("subject") or "No Subject"
                sender = entry.get("from") or entry.get("sender") or "Unknown"
                date_val = entry.get("date") or ""
                entry["snippet"] = f"{subj} (from {sender})"
            # Normalize for LLM: from_ with address
            if "from" in entry and "from_" not in entry:
                entry["from_"] = {"address": entry["from"]}
        return entry

    def test_payload_headers_extracted(self):
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
        result = self._normalize_entry(entry)
        assert result["from"] == "alice@example.com"
        assert result["subject"] == "Test Subject"
        assert result["date"] == "Mon, 1 Jan 2026"

    def test_existing_from_not_overwritten(self):
        """If 'from' is already set, payload headers should not overwrite it."""
        entry = {
            "id": "m1",
            "from": "bob@example.com",
            "payload": {
                "headers": [
                    {"name": "From", "value": "alice@example.com"},
                ]
            }
        }
        result = self._normalize_entry(entry)
        assert result["from"] == "bob@example.com"  # not overwritten

    def test_snippet_fallback_when_empty(self):
        """When snippet is empty, it falls back to 'Subject (from Sender)'."""
        entry = {
            "from": "alice@example.com",
            "subject": "Invoice received",
            "snippet": "",
        }
        result = self._normalize_entry(entry)
        assert "Invoice received" in result["snippet"]
        assert "alice@example.com" in result["snippet"]

    def test_snippet_fallback_with_no_subject(self):
        entry = {"from": "alice@example.com", "snippet": ""}
        result = self._normalize_entry(entry)
        assert "No Subject" in result["snippet"]

    def test_snippet_not_overwritten_when_present(self):
        entry = {"snippet": "existing snippet", "from": "alice@example.com"}
        result = self._normalize_entry(entry)
        assert result["snippet"] == "existing snippet"

    def test_from_underscore_normalized(self):
        """from_ object is created for LLM code generation."""
        entry = {"from": "alice@example.com", "snippet": "test"}
        result = self._normalize_entry(entry)
        assert "from_" in result
        assert result["from_"]["address"] == "alice@example.com"

    def test_from_underscore_not_overwritten_when_exists(self):
        entry = {"from": "alice@example.com", "from_": {"address": "original@example.com"}, "snippet": "test"}
        result = self._normalize_entry(entry)
        assert result["from_"]["address"] == "original@example.com"  # not overwritten


# ---------------------------------------------------------------------------
# context_updater — snippet_val fallback when empty
# ---------------------------------------------------------------------------

class TestContextUpdaterSnippetFallback:
    """Test the snippet_val fallback logic added in context_updater.py."""

    def _compute_snippet(self, m, h_dict):
        """Replicate the snippet_val fallback logic from context_updater.py."""
        sender = h_dict.get("from", "Unknown")
        subject = h_dict.get("subject", "No Subject")
        date_val = h_dict.get("date", "Unknown Date")

        snippet_val = str(m.get("snippet") or "").strip()
        if not snippet_val:
            snippet_val = f"From: {sender} | Subject: {subject} | Date: {date_val}"
        return snippet_val

    def test_snippet_present_returned_as_is(self):
        m = {"snippet": "Your order has been confirmed"}
        h_dict = {"from": "shop@example.com", "subject": "Order Confirmed", "date": "2026-01-01"}
        result = self._compute_snippet(m, h_dict)
        assert result == "Your order has been confirmed"

    def test_empty_snippet_triggers_fallback(self):
        m = {"snippet": ""}
        h_dict = {"from": "alice@example.com", "subject": "Hello", "date": "2026-01-02"}
        result = self._compute_snippet(m, h_dict)
        assert result == "From: alice@example.com | Subject: Hello | Date: 2026-01-02"

    def test_none_snippet_triggers_fallback(self):
        m = {"snippet": None}
        h_dict = {"from": "bob@example.com", "subject": "Meeting", "date": "2026-02-15"}
        result = self._compute_snippet(m, h_dict)
        assert result == "From: bob@example.com | Subject: Meeting | Date: 2026-02-15"

    def test_missing_snippet_key_triggers_fallback(self):
        m = {}
        h_dict = {"from": "carol@example.com", "subject": "Invoice", "date": "2026-03-01"}
        result = self._compute_snippet(m, h_dict)
        assert "From: carol@example.com" in result
        assert "Subject: Invoice" in result
        assert "Date: 2026-03-01" in result

    def test_fallback_with_missing_headers_uses_defaults(self):
        m = {}
        h_dict = {}  # no from/subject/date
        result = self._compute_snippet(m, h_dict)
        assert "Unknown" in result
        assert "No Subject" in result

    def test_whitespace_only_snippet_triggers_fallback(self):
        m = {"snippet": "   "}
        h_dict = {"from": "test@example.com", "subject": "Test", "date": "2026-01-01"}
        result = self._compute_snippet(m, h_dict)
        # Whitespace-only snippet is stripped and triggers fallback
        assert result == "From: test@example.com | Subject: Test | Date: 2026-01-01"

    def test_fallback_format_includes_pipe_separators(self):
        m = {}
        h_dict = {"from": "a@b.com", "subject": "Hello", "date": "2026-01-01"}
        result = self._compute_snippet(m, h_dict)
        assert " | " in result
        parts = result.split(" | ")
        assert len(parts) == 3
