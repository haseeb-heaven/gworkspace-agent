import pytest

from gws_assistant import json_utils
from gws_assistant.json_utils import JsonExtractionError, extract_json, safe_json_loads


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


def test_safe_json_loads_fallback_only_on_decode_failure():
    assert safe_json_loads("not json", fallback_to_string=True) == "not json"


def test_safe_json_loads_does_not_swallow_non_decode_errors(monkeypatch):
    def boom(_text: str):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(json_utils, "extract_json", boom)
    with pytest.raises(RuntimeError, match="unexpected"):
        safe_json_loads("{}", fallback_to_string=True)
