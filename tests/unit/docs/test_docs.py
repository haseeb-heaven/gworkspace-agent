import json

from gws_assistant.planner import CommandPlanner

import pytest
from gws_assistant.models import ExecutionResult

@pytest.fixture(autouse=True)
def mock_runner_run(mocker):
    mocker.patch("gws_assistant.gws_runner.GWSRunner.run", return_value=ExecutionResult(
        success=True,
        command=[],
        stdout='{"id": "fake-id-1234567890"}',
        output={"id": "fake-id-1234567890"}
    ))



class TestDocsUnit:
    planner = CommandPlanner()

    def test_create_document(self):
        args = self.planner.build_command("docs", "create_document", {"title": "Test Doc"})
        body = json.loads(args[args.index("--json") + 1])
        assert body["title"] == "Test Doc"

    def test_get_document(self):
        args = self.planner.build_command("docs", "get_document", {"document_id": "doc123"})
        params = json.loads(args[args.index("--params") + 1])
        assert params["documentId"] == "doc123"

    def test_batch_update(self):
        args = self.planner.build_command("docs", "batch_update", {"document_id": "doc123", "text": "Hello"})
        params = json.loads(args[args.index("--params") + 1])
        assert params["documentId"] == "doc123"
        body = json.loads(args[args.index("--json") + 1])
        assert body["requests"][0]["insertText"]["text"] == "Hello"
