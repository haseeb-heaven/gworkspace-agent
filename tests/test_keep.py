from gws_assistant.planner import CommandPlanner
import json

class TestPlannerKeep:
    planner = CommandPlanner()
    
    def test_create_note(self):
        args = self.planner.build_command("keep", "create_note", {"title": "Test Note", "body": "Keep content"})
        assert args[:3] == ["keep", "notes", "create"]
        body = json.loads(args[args.index("--json") + 1])
        assert body["title"] == "Test Note"
        assert body["body"]["text"]["text"] == "Keep content"

    def test_list_notes(self):
        args = self.planner.build_command("keep", "list_notes", {"page_size": 5})
        assert args[:3] == ["keep", "notes", "list"]
        params = json.loads(args[args.index("--params") + 1])
        assert params["pageSize"] == 5
