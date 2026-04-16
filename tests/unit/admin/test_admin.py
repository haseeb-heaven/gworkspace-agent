import pytest

from gws_assistant.planner import CommandPlanner


class TestAdminUnit:
    planner = CommandPlanner()

    def test_list_users(self):
        with pytest.raises(Exception):
            self.planner.build_command("admin", "list_users", {"customer": "my_customer", "page_size": 20})
