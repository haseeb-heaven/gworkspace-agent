import pytest

from gws_assistant.execution.verifier import TripleVerifier


class MockResult:
    def __init__(self, stdout, success=True):
        self.stdout = stdout
        self.success = success


@pytest.mark.gmail
def test_verifier_handles_polluted_output():
    polluted_stdout = 'Using keyring backend: keyring\n{ "id": "123", "status": "done" }'
    result = MockResult(polluted_stdout)

    # This is what TripleVerifier._payload does internally
    payload = TripleVerifier._payload(result)

    # If TripleVerifier._payload fails to parse JSON, it returns the string.
    # We want it to be a dict.
    assert isinstance(payload, dict), f"Expected dict, got {type(payload)}: {payload}"
    assert payload["id"] == "123"


@pytest.mark.gmail
def test_verifier_handles_another_pollution():
    polluted_stdout = 'Some diagnostic message\nAnother one\n{ "key": "value" }\nFooter message'
    result = MockResult(polluted_stdout)

    payload = TripleVerifier._payload(result)
    assert isinstance(payload, dict)
    assert payload["key"] == "value"


@pytest.mark.gmail
def test_verifier_handles_inline_pollution():
    polluted_stdout = 'Using keyring backend: keyring{ "key": "value" }'
    result = MockResult(polluted_stdout)

    payload = TripleVerifier._payload(result)
    assert isinstance(payload, dict)
    assert payload["key"] == "value"


@pytest.mark.gmail
def test_verifier_handles_garbage_at_end():
    polluted_stdout = '{ "key": "value" } some trailing garbage'
    result = MockResult(polluted_stdout)

    payload = TripleVerifier._payload(result)
    assert isinstance(payload, dict)
    assert payload["key"] == "value"
