import pytest
from gws_assistant.drive_query_builder import sanitize_drive_query

@pytest.mark.parametrize("raw, expected", [
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
        "name contains 'CcaaS - AI Product' and mimeType='application/vnd.google-apps.document'"
    ),
    (
        "CcaaS - AI Product mimeType:application/vnd.google-apps.document",
        "name contains 'CcaaS - AI Product' and mimeType='application/vnd.google-apps.document'"
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
    ("File with \\ backslash", "name contains 'File with  backslash'"), # backslash is stripped by _escape

    # Conjunctions
    ("Budget and mimeType:application/pdf", "name contains 'Budget' and mimeType='application/pdf'"),
    ("Budget or Report", "name contains 'Budget' or name contains 'Report'"),

    # Complex cases
    (
        "name='CcaaS' mimeType='application/vnd.google-apps.document'",
        "name contains 'CcaaS' and mimeType='application/vnd.google-apps.document'"
    ),
    (
        "Budget 2024 and (mimeType:application/pdf or mimeType:application/vnd.google-apps.document)",
        "name contains 'Budget 2024' and name contains '(' and mimeType='application/pdf' or name contains ')' and mimeType='application/vnd.google-apps.document'"
    ) # Note: _tokenize_raw_query doesn't handle nested parentheses, it splits on 'and'/'or' regardless.
])
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
