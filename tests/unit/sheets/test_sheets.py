import pytest
import json
from gws_assistant.planner import CommandPlanner
from gws_assistant.exceptions import ValidationError

class TestSheetsUnit:
    planner = CommandPlanner()

    def test_create_spreadsheet(self):
        args = self.planner.build_command("sheets", "create_spreadsheet", {"title": "Test Title"})
        body = json.loads(args[args.index("--json") + 1])
        assert body["properties"]["title"] == "Test Title"

    def test_get_spreadsheet(self):
        args = self.planner.build_command("sheets", "get_spreadsheet", {"spreadsheet_id": "sid_123"})
        params = json.loads(args[args.index("--params") + 1])
        assert params["spreadsheetId"] == "sid_123"

    def test_get_values(self):
        args = self.planner.build_command("sheets", "get_values", {"spreadsheet_id": "sid_123", "range": "A1:B2"})
        assert args == ["sheets", "+read", "--spreadsheet", "sid_123", "--range", "A1:B2"]

    def test_append_values(self):
        args = self.planner.build_command("sheets", "append_values", {"spreadsheet_id": "sid_123", "range": "A1", "values": [["x", "y"]]})
        assert args[0:4] == ["sheets", "spreadsheets", "values", "append"]
        params = json.loads(args[args.index("--params") + 1])
        assert params["spreadsheetId"] == "sid_123"
        body = json.loads(args[args.index("--json") + 1])
        assert body["values"] == [["x", "y"]]
