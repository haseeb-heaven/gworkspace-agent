from gws_assistant.planner import CommandPlanner

class TestMeetUnit:
    planner = CommandPlanner()

    def test_list_conferences(self):
        args = self.planner.build_command("meet", "list_conferences", {})
        assert args == ["meet", "conferenceRecords", "list"]

    def test_create_meeting(self):
        args = self.planner.build_command("meet", "create_meeting", {})
        assert args == ["meet", "spaces", "create"]
