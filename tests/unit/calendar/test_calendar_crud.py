import json

import pytest

from gws_assistant.exceptions import ValidationError
from gws_assistant.planner import CommandPlanner


class TestCalendarCRUD:
    planner = CommandPlanner()

    def test_insert_event(self):
        """Verify create_event maps to 'insert' command."""
        params = {
            "summary": "Meeting",
            "start_date": "2026-04-18",
            "description": "Project sync"
        }
        args = self.planner.build_command("calendar", "create_event", params)
        assert args[0:3] == ["calendar", "events", "insert"]

        # Verify JSON body
        json_idx = args.index("--json")
        body = json.loads(args[json_idx + 1])
        assert body["summary"] == "Meeting"
        assert body["description"] == "Project sync"
        assert body["start"]["date"] == "2026-04-18"

    def test_get_event(self):
        """Verify get_event maps to 'get' command."""
        params = {
            "event_id": "event123",
            "calendar_id": "primary"
        }
        args = self.planner.build_command("calendar", "get_event", params)
        assert args[0:3] == ["calendar", "events", "get"]

        # Verify params
        params_idx = args.index("--params")
        p = json.loads(args[params_idx + 1])
        assert p["eventId"] == "event123"
        assert p["calendarId"] == "primary"

    def test_update_event(self):
        """Verify update_event maps to 'patch' command."""
        params = {
            "event_id": "event123",
            "summary": "Updated Meeting"
        }
        args = self.planner.build_command("calendar", "update_event", params)
        assert args[0:3] == ["calendar", "events", "patch"]

        # Verify JSON body
        json_idx = args.index("--json")
        body = json.loads(args[json_idx + 1])
        assert body["summary"] == "Updated Meeting"

    def test_delete_event(self):
        """Verify delete_event maps to 'delete' command."""
        params = {
            "event_id": "event123"
        }
        args = self.planner.build_command("calendar", "delete_event", params)
        assert args[0:3] == ["calendar", "events", "delete"]

        # Verify params
        params_idx = args.index("--params")
        p = json.loads(args[params_idx + 1])
        assert p["eventId"] == "event123"
        assert p["calendarId"] == "primary" # Default

    def test_missing_event_id_fails(self):
        """Verify get_event fails without event_id."""
        with pytest.raises(ValidationError) as exc:
            self.planner.build_command("calendar", "get_event", {})
        assert "Missing required parameter: event_id" in str(exc.value)
