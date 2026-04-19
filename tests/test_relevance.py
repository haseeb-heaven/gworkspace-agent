from __future__ import annotations

import pytest
from gws_assistant.relevance import (
    extract_keywords,
    score_item,
    filter_drive_files,
    filter_gmail_messages,
)

def test_extract_keywords_empty():
    assert extract_keywords("") == []
    assert extract_keywords("   ") == []

def test_extract_keywords_quoted_phrases():
    # Quoted phrases should be extracted first and lowered
    keywords = extract_keywords('find "Project Titan" notes')
    assert "project titan" in keywords
    assert "notes" in keywords

def test_extract_keywords_stop_words():
    # "the", "a", "is" are stop words. "budget" is not.
    keywords = extract_keywords("the budget is high")
    assert "budget" in keywords
    assert "the" not in keywords
    assert "is" not in keywords

def test_extract_keywords_min_length():
    # Words shorter than 3 chars are ignored by the regex [a-zA-Z]{3,}
    keywords = extract_keywords("my budget ok")
    assert "budget" in keywords
    assert "my" not in keywords
    assert "ok" not in keywords

def test_extract_keywords_no_duplicates():
    keywords = extract_keywords("budget budget BUDGET")
    assert keywords == ["budget"]

def test_score_item_empty():
    assert score_item("", ["test"]) == 0.0
    assert score_item("test", []) == 0.0
    assert score_item("", []) == 0.0

def test_score_item_single_word():
    # weight = 1 + 1 = 2
    # total = 2, max = 2 -> 1.0
    assert score_item("the quick brown fox", ["quick"]) == 1.0
    assert score_item("the brown fox", ["quick"]) == 0.0

def test_score_item_phrase_weight():
    # Single word "quick": weight = 1 + 1 = 2
    # Phrase "quick brown": weight = 2 + 1 = 3
    # Text: "the quick brown fox"
    # Both match: total = 2 + 3 = 5, max = 5 -> 1.0
    assert score_item("the quick brown fox", ["quick", "quick brown"]) == 1.0

    # Text: "the quick fox"
    # Only "quick" matches: total = 2, max = 5 -> 0.4
    assert score_item("the quick fox", ["quick", "quick brown"]) == 0.4

def test_score_item_case_insensitivity():
    assert score_item("BUDGET", ["budget"]) == 1.0
    assert score_item("budget", ["BUDGET"]) == 1.0

def test_filter_drive_files_basic():
    files = [
        {"name": "budget.pdf", "mimeType": "application/pdf"},
        {"name": "vacation.jpg", "mimeType": "image/jpeg"},
    ]
    keywords = ["budget"]
    filtered = filter_drive_files(files, keywords)
    assert len(filtered) == 1
    assert filtered[0]["name"] == "budget.pdf"

def test_filter_drive_files_fallback():
    # If nothing matches, return all
    files = [
        {"name": "notes.txt", "mimeType": "text/plain"},
        {"name": "todo.txt", "mimeType": "text/plain"},
    ]
    keywords = ["budget"]
    filtered = filter_drive_files(files, keywords, min_score=0.5)
    assert len(filtered) == 2

def test_filter_gmail_messages_basic():
    messages = [
        {
            "snippet": "Here is the budget report",
            "payload": {
                "headers": [{"name": "Subject", "value": "Budget 2024"}]
            }
        },
        {
            "snippet": "Lunch tomorrow?",
            "payload": {
                "headers": [{"name": "Subject", "value": "Lunch"}]
            }
        }
    ]
    keywords = ["budget"]
    filtered = filter_gmail_messages(messages, keywords)
    assert len(filtered) == 1
    assert "budget" in filtered[0]["snippet"].lower()

def test_filter_gmail_messages_headers():
    messages = [
        {
            "snippet": "Checking in",
            "payload": {
                "headers": [
                    {"name": "From", "value": "boss@company.com"},
                    {"name": "Subject", "value": "Urgent"}
                ]
            }
        }
    ]
    # Match on Subject
    assert len(filter_gmail_messages(messages, ["urgent"])) == 1
    # Match on From
    assert len(filter_gmail_messages(messages, ["boss"])) == 1
    # No match
    filtered = filter_gmail_messages(messages, ["lunch"], min_score=0.1)
    # Fallback to original
    assert len(filtered) == 1
