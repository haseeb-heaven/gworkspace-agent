import pytest
import json
from gws_assistant.planner import CommandPlanner
from gws_assistant.exceptions import ValidationError

class TestAdminUnit:
    planner = CommandPlanner()

    def test_list_users(self):
        with pytest.raises(Exception):
            args = self.planner.build_command("admin", "list_users", {"customer": "my_customer", "page_size": 20})
