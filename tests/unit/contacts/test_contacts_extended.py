import json
import pytest
from gws_assistant.planner import CommandPlanner
from gws_assistant.exceptions import ValidationError

class TestContactsExtended:
    planner = CommandPlanner()

    def test_list_contacts_default(self):
        args = self.planner.build_command("contacts", "list_contacts", {})
        params = json.loads(args[args.index("--params") + 1])
        assert params["pageSize"] == 10
        assert params["resourceName"] == "people/me"
        assert "personFields" in params

    def test_list_contacts_custom_page_size(self):
        args = self.planner.build_command("contacts", "list_contacts", {"page_size": 50})
        params = json.loads(args[args.index("--params") + 1])
        assert params["pageSize"] == 50

    def test_list_contacts_invalid_page_size(self):
        # Should fallback to default 10
        args = self.planner.build_command("contacts", "list_contacts", {"page_size": "invalid"})
        params = json.loads(args[args.index("--params") + 1])
        assert params["pageSize"] == 10

    def test_unsupported_action(self):
        with pytest.raises(ValidationError):
            self.planner.build_command("contacts", "non_existent_action", {})
