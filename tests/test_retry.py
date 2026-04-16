from unittest.mock import MagicMock

from gws_assistant.gws_runner import GWSRunner
from gws_assistant.models import ExecutionResult


def test_gws_runner_retry_success_after_failure(mocker, tmp_path):
    runner = GWSRunner(tmp_path / "gws.exe", MagicMock())

    # Mock self.run to fail twice then succeed
    side_effects = [
        ExecutionResult(success=False, command=[], return_code=500, error="Internal Server Error"),
        ExecutionResult(success=False, command=[], return_code=503, error="Service Unavailable"),
        ExecutionResult(success=True, command=[], return_code=0, stdout="success!"),
    ]
    mocker.patch.object(runner, "run", side_effect=side_effects)

    # Mock time.sleep so test runs fast
    mocker.patch("time.sleep")

    result = runner.run_with_retry(["some", "args"], max_retries=3)
    assert result.success is True
    assert result.stdout == "success!"
    assert runner.run.call_count == 3

def test_gws_runner_retry_permanent_failure(mocker, tmp_path):
    runner = GWSRunner(tmp_path / "gws.exe", MagicMock())

    # Mock self.run to always fail
    mocker.patch.object(runner, "run", return_value=ExecutionResult(
        success=False, command=[], return_code=500, error="Internal Server Error"
    ))
    mocker.patch("time.sleep")

    result = runner.run_with_retry(["args"], max_retries=3)
    assert result.success is False
    assert runner.run.call_count == 3

def test_gws_runner_no_retry_for_non_transient(mocker, tmp_path):
    runner = GWSRunner(tmp_path / "gws.exe", MagicMock())

    # Validation error -> should not retry
    mocker.patch.object(runner, "run", return_value=ExecutionResult(
        success=False, command=[], return_code=400, error="Bad Request"
    ))
    mocker.patch("time.sleep")

    result = runner.run_with_retry(["args"], max_retries=3)
    assert result.success is False
    assert runner.run.call_count == 1  # Only tried once
