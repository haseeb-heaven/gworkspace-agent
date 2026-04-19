import json

from gws_assistant.planner import CommandPlanner


class TestChatUnit:
    planner = CommandPlanner()

    def test_list_spaces(self):
        args = self.planner.build_command("chat", "list_spaces", {"page_size": 20})
        params = json.loads(args[args.index("--params") + 1])
        assert params["pageSize"] == 20

    def test_send_message(self):
        args = self.planner.build_command("chat", "send_message", {"space": "spaces/xyz", "text": "Hello"})
        params = json.loads(args[args.index("--params") + 1])
        assert params["parent"] == "spaces/xyz"
        body = json.loads(args[args.index("--json") + 1])
        assert body["text"] == "Hello"
