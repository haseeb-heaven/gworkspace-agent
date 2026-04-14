import pytest
import json
from gws_assistant.planner import CommandPlanner
from gws_assistant.exceptions import ValidationError

class TestFormsUnit:
    planner = CommandPlanner()

    def test_sync_data(self):
        with pytest.raises(Exception):
            args = self.planner.build_command("forms", "sync_data", {"form_id": "frm2", "data": "Responses"})
