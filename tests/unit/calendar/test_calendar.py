import json
from gws_assistant.planner import CommandPlanner

class TestCalendarUnit:
    planner = CommandPlanner()

    def test_list_events(self):
        args = self.planner.build_command("calendar", "list_events", {"calendar_id": "primary"})
        params = json.loads(args[args.index("--params") + 1])
        assert params["calendarId"] == "primary"

    def test_create_event(self):
        args = self.planner.build_command("calendar", "create_event", {"summary": "Sync", "start_date": "2026-04-15"})
        body = json.loads(args[args.index("--json") + 1])
        assert body["summary"] == "Sync"
        assert body["start"]["date"] == "2026-04-15"
