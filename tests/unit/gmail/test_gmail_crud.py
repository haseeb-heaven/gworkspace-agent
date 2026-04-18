import json
import os
from gws_assistant.planner import CommandPlanner
from gws_assistant.exceptions import ValidationError
import pytest

def test_gmail_crud_lifecycle():
    planner = CommandPlanner()
    message_id = "test_msg_123"
    
    # 1. List
    args = planner.build_command("gmail", "list_messages", {"q": "test"})
    assert args[:4] == ["gmail", "users", "messages", "list"]
    
    # 2. Send (using DEFAULT_RECIPIENT_EMAIL)
    to_email = os.getenv("DEFAULT_RECIPIENT_EMAIL", "test@example.com")
    args = planner.build_command("gmail", "send_message", {"to_email": to_email, "subject": "S", "body": "B"})
    assert args[:4] == ["gmail", "users", "messages", "send"]
    
    # 3. Get
    args = planner.build_command("gmail", "get_message", {"message_id": message_id})
    assert args[:4] == ["gmail", "users", "messages", "get"]
    params = json.loads(args[args.index("--params") + 1])
    assert params["id"] == message_id
    
    # 4. Trash
    args = planner.build_command("gmail", "trash_message", {"message_id": message_id})
    assert args[:4] == ["gmail", "users", "messages", "trash"]
    params = json.loads(args[args.index("--params") + 1])
    assert params["id"] == message_id

    # 5. Delete
    args = planner.build_command("gmail", "delete_message", {"message_id": message_id})
    assert args[:4] == ["gmail", "users", "messages", "delete"]
    params = json.loads(args[args.index("--params") + 1])
    assert params["id"] == message_id
