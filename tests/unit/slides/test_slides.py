import pytest
import json
from gws_assistant.planner import CommandPlanner

class TestSlidesUnit:
    planner = CommandPlanner()

    def test_create_presentation(self):
        with pytest.raises(Exception):
            self.planner.build_command("slides", "create_presentation", {"title": "Test Deck"})

    def test_get_presentation(self):
        args = self.planner.build_command("slides", "get_presentation", {"presentation_id": "pid_123"})
        params = json.loads(args[args.index("--params") + 1])
        assert params["presentationId"] == "pid_123"
