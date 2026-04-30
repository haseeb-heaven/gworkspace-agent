import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from gws_assistant.tools.telegram import redact_sensitive

# Try to import dotenv, fallback gracefully
try:
    from dotenv import dotenv_values
except ImportError:
    def dotenv_values(path): return {}


def _safe_stderr(message: object) -> None:
    print(redact_sensitive(message), file=sys.stderr)


def send_telegram_message(message: str, max_retries: int = 3):
    """
    Send a message to Telegram with basic validation.
    The message must be a string, not empty, and <= 4096 characters.
    """
    if not isinstance(message, str):
        raise TypeError("Message must be a string.")

    message = message.strip()
    if not message:
        raise ValueError("Message cannot be empty.")

    if len(message) > 4096:
        error_text = (
            f"Message too long: {len(message)} characters. "
            f"Max allowed is 4096."
        )
        raise ValueError(error_text)

    # Determine the root directory and find the .env file
    root_dir = Path(__file__).resolve().parents[1]
    env_path = root_dir / ".env"
    # Load .env variables
    env = dotenv_values(env_path)

    # Use value from .env or fallback to system environment variables
    token = env.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(
            "Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not configured in .env or environment.", file=sys.stderr
        )
        sys.exit(1)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                result = json.loads(response.read().decode())
                if result.get("ok"):
                    print("Telegram message sent successfully.")
                    return
                _safe_stderr("Telegram API rejected the message.")
                return
        except urllib.error.URLError as e:
            last_error = e
            if attempt == max_retries - 1:
                break
            time.sleep(2**attempt)
    if last_error is not None:
        _safe_stderr("Failed to send Telegram message due to a transient network error.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send a Telegram message using .env configuration.")
    parser.add_argument("message", nargs="?")
    parser.add_argument("--text", dest="text")
    parser.add_argument("--chat_id", dest="chat_id")
    args = parser.parse_args()

    message = args.text or args.message
    if not message:
        print('Usage: python telegram_send_message.py "Message text"', file=sys.stderr)
        sys.exit(1)

    try:
        send_telegram_message(message)
    except (TypeError, ValueError) as e:
        _safe_stderr(f"Validation error: {e}")
        sys.exit(1)
