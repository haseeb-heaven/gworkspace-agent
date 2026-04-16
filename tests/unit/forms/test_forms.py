import pytest

from gws_assistant.planner import CommandPlanner


class TestFormsUnit:
    planner = CommandPlanner()

    def test_sync_data(self):
        with pytest.raises(Exception):
            self.planner.build_command("forms", "sync_data", {"form_id": "frm2", "data": "Responses"})
