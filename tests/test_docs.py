import json

from gws_assistant.planner import CommandPlanner


class TestPlannerDocs:
    planner = CommandPlanner()

    def test_create_document(self):
        args = self.planner.build_command("docs", "create_document", {"title": "Test Doc", "content": "Hello World"})
        assert args[:3] == ["docs", "documents", "create"]
        body = json.loads(args[args.index("--json") + 1])
        assert body["title"] == "Test Doc"
        # Content append logic might be in batchUpdate, but check schema

    def test_get_document(self):
        args = self.planner.build_command("docs", "get_document", {"document_id": "doc123"})
        assert args[:3] == ["docs", "documents", "get"]
