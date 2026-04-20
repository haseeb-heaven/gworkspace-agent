import json

import pytest

from gws_assistant.exceptions import ValidationError
from gws_assistant.planner import CommandPlanner


class TestFormsUnit:
    planner = CommandPlanner()

    def test_create_form(self):
        cmd = self.planner.build_command("forms", "create_form", {"title": "My New Form"})
        assert cmd[0] == "forms"
        assert cmd[1] == "forms"
        assert cmd[2] == "create"
        assert "--json" in cmd
        payload = json.loads(cmd[cmd.index("--json") + 1])
        assert payload["info"]["title"] == "My New Form"

    def test_get_form(self):
        cmd = self.planner.build_command("forms", "get_form", {"form_id": "form123"})
        assert cmd == ["forms", "forms", "get", "--params", json.dumps({"formId": "form123"})]

    def test_get_form_missing_id(self):
        with pytest.raises(ValidationError):
            self.planner.build_command("forms", "get_form", {})

    def test_unsupported_action(self):
        with pytest.raises(ValidationError):
            self.planner.build_command("forms", "unsupported", {})

    def test_sync_data_is_unsupported(self):
        # The original test checked for an exception on "sync_data"
        with pytest.raises(ValidationError):
            self.planner.build_command("forms", "sync_data", {"form_id": "frm2", "data": "Responses"})
