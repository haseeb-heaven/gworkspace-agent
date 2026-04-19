import pytest

from gws_assistant.planner import CommandPlanner


class TestAdminUnit:
    planner = CommandPlanner()

    def test_list_users(self):
        with pytest.raises(Exception):
            self.planner.build_command("admin", "list_users", {"customer": "my_customer", "page_size": 20})

    def test_log_activity(self):
        cmd = self.planner.build_command("admin", "log_activity", {"data": "test"})
        assert cmd == ["admin", "log_activity", "internal"]

    def test_list_activities(self):
        cmd = self.planner.build_command("admin", "list_activities", {"application_name": "drive", "max_results": 5})
        assert cmd[0] == "admin-reports"
        assert cmd[1] == "activities"
        assert cmd[2] == "list"
        assert "--params" in cmd
