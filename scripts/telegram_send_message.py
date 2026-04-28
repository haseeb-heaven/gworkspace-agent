import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Try to import dotenv, fallback gracefully
try:
    from dotenv import dotenv_values
except ImportError:
    def dotenv_values(path): return {}


def send_telegram_message(message: str):
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
        raise ValueError(f"Message too long: {len(message)} characters. Max allowed is 4096.")

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
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            if result.get("ok"):
                print("Telegram message sent successfully.")
            else:
                print(f"Failed to send: {result}", file=sys.stderr)
    except urllib.error.URLError as e:
        print(f"Failed to send Telegram message: {e}", file=sys.stderr)


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
        print(f"Validation error: {e}", file=sys.stderr)
        sys.exit(1)
