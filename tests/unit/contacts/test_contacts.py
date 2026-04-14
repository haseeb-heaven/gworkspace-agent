import pytest
import json
from gws_assistant.planner import CommandPlanner
from gws_assistant.exceptions import ValidationError

class TestContactsUnit:
    planner = CommandPlanner()

    def test_list_contacts(self):
        args = self.planner.build_command("contacts", "list_contacts", {"page_size": 20})
        params = json.loads(args[args.index("--params") + 1])
        assert params["pageSize"] == 20
        assert params["resourceName"] == "people/me"
