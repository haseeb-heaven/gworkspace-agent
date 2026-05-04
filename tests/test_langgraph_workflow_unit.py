"""Unit tests for langgraph_workflow.py — covers helper functions and logic."""
from __future__ import annotations

from langchain_core.messages import HumanMessage

from gws_assistant.langgraph_workflow import _is_llm_refusal, _trim_history


def test_trim_history():
    messages = [HumanMessage(content=f"m{i}") for i in range(20)]
    trimmed = _trim_history(messages)
    assert len(trimmed) == 10
    assert trimmed[-1].content == "m19"
    assert trimmed[0].content == "m10"


def test_is_llm_refusal():
    assert _is_llm_refusal("I'm sorry, I cannot assist with that.") is True
    assert _is_llm_refusal("As a language model, I don't have feelings.") is True
    assert _is_llm_refusal("def hello(): print('hi')") is False
    assert _is_llm_refusal("import os; os.system('ls')") is False


def test_is_llm_refusal_case_insensitive():
    assert _is_llm_refusal("I AM SORRY") is True
    assert _is_llm_refusal("I CANNOT ASSIST") is True
