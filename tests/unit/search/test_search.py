import pytest
import json
from gws_assistant.planner import CommandPlanner
from gws_assistant.exceptions import ValidationError

class TestSearchUnit:
    planner = CommandPlanner()

    def test_web_search(self):
        args = self.planner.build_command("search", "web_search", {"query": "Latest Agentic AI news"})
        params = json.loads(args[args.index("--params") + 1])
        assert params["query"] == "Latest Agentic AI news"
