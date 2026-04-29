import pytest

from gws_assistant.gmail_query_builder import sanitize_gmail_query

@pytest.mark.parametrize(
    "raw, expected",
    [
        # = to : operator conversion
        ("from=user@example.com", "from:user@example.com"),
        ("subject='foo bar'", 'subject:"foo bar"'),
        ('has="attachment"', "has:attachment"),
        ("label=important", "label:important"),

        # Redundant quotes stripping
        ('subject:"foo"', "subject:foo"),
        ('from:"user@example.com"', "from:user@example.com"),
        ('to:"test"', "to:test"),

        # Keep quotes when value contains spaces
        ('subject:"foo bar"', 'subject:"foo bar"'),
        ('label:"my label"', 'label:"my label"'),

        # Bare double-quoted token without operator
        ('"some topic"', 'subject:"some topic" OR "some topic"'),
        ('"hello world"', 'subject:"hello world" OR "hello world"'),

        # Valid syntax that should be untouched
        ("foo bar", "foo bar"),
        ("subject:test has:attachment", "subject:test has:attachment"),
        ("from:user@example.com to:admin@example.com", "from:user@example.com to:admin@example.com"),
        ("is:unread", "is:unread"),
        ("in:inbox", "in:inbox"),
    ]
)
def test_sanitize_gmail_query(raw, expected):
    assert sanitize_gmail_query(raw) == expected

def test_sanitize_gmail_query_empty():
    assert sanitize_gmail_query("") == ""
    assert sanitize_gmail_query("   ") == ""

def test_sanitize_gmail_query_none():
    with pytest.raises(AttributeError):
        sanitize_gmail_query(None)
