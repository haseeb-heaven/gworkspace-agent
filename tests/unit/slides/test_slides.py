import json

from gws_assistant.output_formatter import HumanReadableFormatter
from gws_assistant.planner import CommandPlanner


class TestSlidesUnit:
    planner = CommandPlanner()
    formatter = HumanReadableFormatter()

    def test_create_presentation(self):
        args = self.planner.build_command("slides", "create_presentation", {"title": "Test Deck"})
        assert "create" in args
        assert "Test Deck" in args[args.index("--json") + 1]

    def test_get_presentation(self):
        args = self.planner.build_command("slides", "get_presentation", {"presentation_id": "pid_123"})
        params = json.loads(args[args.index("--params") + 1])
        assert params["presentationId"] == "pid_123"

    def test_format_slides(self):
        from gws_assistant.models import ExecutionResult
        payload = {
            "slides": [{}, {}],
            "title": "My Deck",
            "presentationId": "p123"
        }
        result = ExecutionResult(
            success=True,
            command=["slides", "get"],
            stdout=json.dumps(payload),
            stderr="",
            return_code=0
        )
        output = self.formatter.format_execution_result(result)
        assert "Presentation: My Deck" in output
        assert "Slides: 2" in output
        assert "Presentation ID: p123" in output
