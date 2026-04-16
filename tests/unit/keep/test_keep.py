import json
from gws_assistant.planner import CommandPlanner

class TestKeepUnit:
    def setup_method(self):
        self.planner = CommandPlanner()

    def test_list_notes(self):
        args = self.planner.build_command("keep", "list_notes", {"page_size": 5})
        assert args == ["keep", "notes", "list", "--params", json.dumps({"pageSize": 5})]

    def test_create_note(self):
        args = self.planner.build_command("keep", "create_note", {"title": "Test Note", "body": "Test Body"})
        assert args == ["keep", "notes", "create", "--json", json.dumps({"title": "Test Note", "body": {"text": {"text": "Test Body"}}})]
