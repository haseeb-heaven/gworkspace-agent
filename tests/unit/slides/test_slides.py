import json

import pytest

from gws_assistant.planner import CommandPlanner


class TestSlidesUnit:
    planner = CommandPlanner()

    def test_create_presentation(self):
        args = self.planner.build_command("slides", "create_presentation", {"title": "Test Deck"})
        assert "create" in args
        assert "Test Deck" in args[args.index("--json") + 1]

    def test_get_presentation(self):
        args = self.planner.build_command("slides", "get_presentation", {"presentation_id": "pid_123"})
        params = json.loads(args[args.index("--params") + 1])
        assert params["presentationId"] == "pid_123"
