import os
import sys
import unittest
from unittest.mock import MagicMock, patch

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

    @patch("scripts.telegram_send_message.send_telegram_message")
    @patch("sys.exit")
    def test_main_block_validation(self, mock_exit, mock_send):
        # We need to simulate the __main__ block validation
        # The easiest way without restructuring is to just run the validation logic

        # Test 1: string check
        import subprocess

        script_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "telegram_send_message.py")

        # Test long message exit
        long_str = "A" * 5000
        result = subprocess.run([sys.executable, script_path, long_str], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Message too long", result.stderr)

        # Test valid message passes validation and tries to run (it will fail on env if not mocked, but we just check it doesn't fail on validation)
        # We can just verify it gets past the validation
        result = subprocess.run([sys.executable, script_path, "Valid"], capture_output=True, text=True)
        # It will either succeed (0) or fail due to missing env vars (1), but not due to validation
        self.assertNotIn("Validation error:", result.stderr)


if __name__ == "__main__":
    unittest.main()
