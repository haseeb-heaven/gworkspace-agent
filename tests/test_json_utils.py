import pytest

from gws_assistant.json_utils import extract_json


@pytest.mark.gmail
def test_extract_json_greedy_bug():
    text = """
    Diagnostic message 1 {ignore this}
    {"key": "value"}
    Diagnostic message 2 {ignore this too}
    """

    result = extract_json(text)
    assert result == {"key": "value"}

@pytest.mark.gmail
def test_extract_json_nested():
    text = """
    Garbage
    {"a": {"b": 1}}
    More garbage
    """

    result = extract_json(text)
    assert result == {"a": {"b": 1}}

@pytest.mark.gmail
def test_extract_json_array():
    text = """
    Garbage
    [{"a": 1}, {"b": 2}]
    More garbage
    """

    result = extract_json(text)
    assert result == [{"a": 1}, {"b": 2}]
