from dotenv import load_dotenv

load_dotenv()
import json
import os

import pytest

from gws_assistant.exceptions import ValidationError
from gws_assistant.planner import CommandPlanner


class TestGmailUnit:
    planner = CommandPlanner()

    def test_list_messages_with_query(self):
        args = self.planner.build_command("gmail", "list_messages", {"q": "from:boss@company.com", "max_results": 5})
        assert args[:4] == ["gmail", "users", "messages", "list"]
        params = json.loads(args[args.index("--params") + 1])
        assert params["q"] == "from:boss@company.com"
        assert params["maxResults"] == 5

    def test_get_message(self):
        args = self.planner.build_command("gmail", "get_message", {"message_id": "abc123"})
        assert args[:4] == ["gmail", "users", "messages", "get"]
        params = json.loads(args[args.index("--params") + 1])
        assert params["id"] == "abc123"

    def test_send_message_builds_raw_email(self):
        args = self.planner.build_command(
            "gmail",
            "send_message",
            {
                "to_email": os.getenv("DEFAULT_RECIPIENT_EMAIL") or "test@example.com",
                "subject": "Test Subject",
                "body": "Hello World",
            },
        )
        assert args[:4] == ["gmail", "users", "messages", "send"]
        body = json.loads(args[args.index("--json") + 1])
        assert "raw" in body
        import base64

        decoded = base64.urlsafe_b64decode(body["raw"]).decode("utf-8")
        assert f"To: {os.getenv('DEFAULT_RECIPIENT_EMAIL') or 'test@example.com'}" in decoded
        assert "Subject: Test Subject" in decoded
        assert "Hello World" in decoded

    def test_send_rejects_missing_to_email(self):
        with pytest.raises(ValidationError):
            self.planner.build_command("gmail", "send_message", {"subject": "X", "body": "Y"})
