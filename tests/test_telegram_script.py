import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add the root directory to sys.path to import the script
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import scripts.telegram_send_message as telegram_script


class TestTelegramSendMessage(unittest.TestCase):

    @patch('scripts.telegram_send_message.dotenv_values')
    @patch('scripts.telegram_send_message.urllib.request.urlopen')
    @patch('scripts.telegram_send_message.os.environ.get')
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

if __name__ == "__main__":
    unittest.main()
