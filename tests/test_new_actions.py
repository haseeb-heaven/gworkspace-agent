from __future__ import annotations

import json

from gws_assistant.planner import CommandPlanner


def test_build_calendar_delete_event():
    planner = CommandPlanner()
    args = planner.build_command("calendar", "delete_event", {"event_id": "abc-123", "calendar_id": "primary"})
    assert args == ["calendar", "events", "delete", "--params", '{"calendarId": "primary", "eventId": "abc-123"}']


def test_build_telegram_send_message():
    planner = CommandPlanner()
    args = planner.build_command("telegram", "send_message", {"message": "Test update"})
    assert "telegram_send_message.py" in args[1]
    assert "Test update" in args[2]


def test_build_calendar_update_event():
    planner = CommandPlanner()
    args = planner.build_command("calendar", "update_event", {"event_id": "abc-123", "summary": "New Title"})
    assert args[0:3] == ["calendar", "events", "patch"]
    # Check json part
    json_idx = args.index("--json") + 1
    body = json.loads(args[json_idx])
    assert body["summary"] == "New Title"
