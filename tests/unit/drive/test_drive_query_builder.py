import pytest
from unittest.mock import patch

from gws_assistant.drive_query_builder import (
    sanitize_drive_query,
    _classify_and_fix_clause,
)

@pytest.mark.parametrize(
    "raw, expected",
    [
        # Basic text queries
        ("Budget 2024", "name contains 'Budget 2024'"),
        ('"Budget 2024"', "name contains 'Budget 2024'"),
        ("CcaaS - AI Product", "name contains 'CcaaS - AI Product'"),
        # Malformed mimeType patterns
        ("mimeType:application/vnd.google-apps.document", "mimeType='application/vnd.google-apps.document'"),
        ("mimeType=application/vnd.google-apps.document", "mimeType='application/vnd.google-apps.document'"),
        ('mimeType="application/vnd.google-apps.document"', "mimeType='application/vnd.google-apps.document'"),
        # Mixed text and mimeType
        (
            '"CcaaS - AI Product" mimeType="application/vnd.google-apps.document"',
            "name contains 'CcaaS - AI Product' and mimeType='application/vnd.google-apps.document'",
        ),
        (
            "CcaaS - AI Product mimeType:application/vnd.google-apps.document",
            "name contains 'CcaaS - AI Product' and mimeType='application/vnd.google-apps.document'",
        ),
        # Already valid queries (should be preserved or normalized)
        ("name contains 'Budget'", "name contains 'Budget'"),
        ("mimeType = 'application/pdf'", "mimeType = 'application/pdf'"),
        ("trashed = false", "trashed = false"),
        ("starred = true", "starred = true"),
        ("sharedWithMe = true", "sharedWithMe = true"),
        ("parents in 'some_id'", "parents in 'some_id'"),
        # name= and name: variants
        ("name='Budget 2024'", "name contains 'Budget 2024'"),
        ("name:Budget 2024", "name contains 'Budget 2024'"),
        ('name="Budget 2024"', "name contains 'Budget 2024'"),
        # Escaping
        ("Don't forget", "name contains 'Don\\'t forget'"),
        ("File with \\ backslash", "name contains 'File with  backslash'"),  # backslash is stripped by _escape
        # Conjunctions
        ("Budget and mimeType:application/pdf", "name contains 'Budget' and mimeType='application/pdf'"),
        ("Budget or Report", "name contains 'Budget' or name contains 'Report'"),
        # Missing quotes on operators
        ("parents in 12345", "parents in '12345'"),
        ("fullText contains something", "fullText contains 'something'"),
        ("name = budget", "name contains 'budget'"), # Name equality falls back to contains per _NAME_EQ_RE
        ("name != budget", "name != 'budget'"),
        # Complex cases
        (
            "name='CcaaS' mimeType='application/vnd.google-apps.document'",
            "name contains 'CcaaS' and mimeType='application/vnd.google-apps.document'",
        ),
        (
            "Budget 2024 and (mimeType:application/pdf or mimeType:application/vnd.google-apps.document)",
            "name contains 'Budget 2024' and name contains '(' and mimeType='application/pdf' or name contains ')' and mimeType='application/vnd.google-apps.document'",
        ),  # Note: _tokenize_raw_query doesn't handle nested parentheses, it splits on 'and'/'or' regardless.
    ],
)
def test_sanitize_drive_query(raw, expected):
    assert sanitize_drive_query(raw) == expected


def test_sanitize_drive_query_empty():
    assert sanitize_drive_query("") == ""
    assert sanitize_drive_query("   ") == ""


def test_sanitize_drive_query_none():
    with pytest.raises(AttributeError):
        sanitize_drive_query(None)


def test_sanitize_drive_query_already_valid_complex():
    q = "name contains 'Budget' and mimeType = 'application/pdf' and trashed = false"
    assert sanitize_drive_query(q) == q


def test_sanitize_drive_query_mixed_valid_and_invalid():
    # 'trashed = false' is valid. 'mimeType:pdf' is not.
    q = "trashed = false and mimeType:application/pdf"
    expected = "trashed = false and mimeType='application/pdf'"
    assert sanitize_drive_query(q) == expected


def test_sanitize_drive_query_empty_clause():
    assert _classify_and_fix_clause("   ") == []


def test_sanitize_drive_query_already_operator():
    assert sanitize_drive_query("name contains budget") == "name contains 'budget'"
    assert sanitize_drive_query("fullText contains 'budget'") == "fullText contains 'budget'"


def test_sanitize_drive_query_invalid_operator():
    assert sanitize_drive_query("trashed yes") == "name contains 'trashed yes'"
    assert sanitize_drive_query("properties = true") == "name contains 'properties = true'"


def test_sanitize_drive_query_empty_result():
    assert sanitize_drive_query('""') == "name contains ''"
    assert sanitize_drive_query('" "') == "name contains ''"


def test_sanitize_drive_query_fallback():
    with patch("gws_assistant.drive_query_builder._classify_and_fix_clause", return_value=["just some text without op"]):
        assert sanitize_drive_query("fake input") == "name contains 'just some text without op'"


def test_sanitize_drive_query_valid_operator_missing_quotes():
    # Tests that when an already-valid subclause (like `trashed=false`) is
    # part of a broader invalid clause (due to missing "and"), it is correctly extracted.
    assert sanitize_drive_query("trashed=false mimeType:application/pdf") == "trashed=false and mimeType='application/pdf'"
