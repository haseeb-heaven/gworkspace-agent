import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError

# Add the root directory to sys.path to import the script
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.telegram_send_message as telegram_script


class TestTelegramSendMessage(unittest.TestCase):
    @patch("scripts.telegram_send_message.dotenv_values")
    @patch("scripts.telegram_send_message.urllib.request.urlopen")
    @patch("scripts.telegram_send_message.os.environ.get")
    def test_send_telegram_message_validation(self, mock_env_get, mock_urlopen, mock_dotenv):
        # Mock configuration
        mock_dotenv.return_value = {"TELEGRAM_BOT_TOKEN": "bot123", "TELEGRAM_CHAT_ID": "chat123"}
        mock_env_get.side_effect = lambda k: None

        # Define mock response for valid cases
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"ok": true}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        # 1. Test with a very long message
        long_message = "A" * 5000
        # This SHOULD raise ValueError after fix
        with self.assertRaises(ValueError) as cm:
            telegram_script.send_telegram_message(long_message)
        self.assertIn("Message too long", str(cm.exception))

        # 2. Test with empty message
        with self.assertRaises(ValueError) as cm:
            telegram_script.send_telegram_message("")
        self.assertIn("Message cannot be empty", str(cm.exception))

        # 3. Test with non-string message
        with self.assertRaises(TypeError) as cm:
            telegram_script.send_telegram_message(123)
        self.assertIn("Message must be a string", str(cm.exception))

        # 4. Test with valid message (should not raise)
        telegram_script.send_telegram_message("Valid message")
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("scripts.telegram_send_message.dotenv_values")
    @patch("scripts.telegram_send_message.urllib.request.urlopen")
    @patch("scripts.telegram_send_message.os.environ.get")
    @patch("scripts.telegram_send_message.time.sleep")
    def test_send_telegram_message_retries_transient_failures(self, _sleep, mock_env_get, mock_urlopen, mock_dotenv):
        mock_dotenv.return_value = {"TELEGRAM_BOT_TOKEN": "bot123", "TELEGRAM_CHAT_ID": "chat123"}
        mock_env_get.side_effect = lambda k: None
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"ok": true}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.side_effect = [URLError("failed"), URLError("failed again"), mock_response]

        telegram_script.send_telegram_message("Valid message")
        self.assertEqual(mock_urlopen.call_count, 3)

    @patch("scripts.telegram_send_message.dotenv_values")
    @patch("scripts.telegram_send_message.urllib.request.urlopen")
    @patch("scripts.telegram_send_message.os.environ.get")
    @patch("scripts.telegram_send_message._safe_stderr")
    def test_send_telegram_message_does_not_print_raw_failure_payload(
        self, mock_safe_stderr, mock_env_get, mock_urlopen, mock_dotenv
    ):
        mock_dotenv.return_value = {"TELEGRAM_BOT_TOKEN": "bot123", "TELEGRAM_CHAT_ID": "chat123"}
        mock_env_get.side_effect = lambda k: None
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"ok": false, "parameters": {"migrate_to_chat_id": "123456"}}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        telegram_script.send_telegram_message("Valid message")
        logged = "".join(str(call.args[0]) for call in mock_safe_stderr.call_args_list)
        self.assertNotIn("migrate_to_chat_id", logged)



class TestTelegramMainValidation(unittest.TestCase):
    SCRIPT_PATH = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "scripts", "telegram_send_message.py")
    )

    def test_main_rejects_oversized_message(self):
        import subprocess
        env = os.environ.copy()
        env["TELEGRAM_BOT_TOKEN"] = "mock_token"
        env["TELEGRAM_CHAT_ID"] = "mock_chat"
        result = subprocess.run(
            [sys.executable, self.SCRIPT_PATH, "A" * 4097],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("too long", result.stderr.lower())

    def test_main_accepts_message_at_limit(self):
        import subprocess
        env = os.environ.copy()
        env["TELEGRAM_BOT_TOKEN"] = "mock_token"
        env["TELEGRAM_CHAT_ID"] = "mock_chat"
        # Mocking the success by preventing the actual URL call via token check in script?
        # Actually, if we just want to check validation, we can just ensure it doesn't fail on "too long"
        result = subprocess.run(
            [sys.executable, self.SCRIPT_PATH, "A" * 4096],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertNotIn("too long", result.stderr.lower())

    def test_main_rejects_non_string_is_unreachable_via_cli(self):
        import subprocess
        env = os.environ.copy()
        env["TELEGRAM_BOT_TOKEN"] = "mock_token"
        env["TELEGRAM_CHAT_ID"] = "mock_chat"
        result = subprocess.run(
            [sys.executable, self.SCRIPT_PATH, "hello"],
            capture_output=True,
            text=True,
            env=env,
        )
        stderr = result.stderr.lower()
        self.assertNotIn("must be a string", stderr)
        self.assertNotIn("too long", stderr)


if __name__ == "__main__":
    unittest.main()
