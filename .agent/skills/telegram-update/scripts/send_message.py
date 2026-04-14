import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

# Try to import dotenv, fallback gracefully
try:
    from dotenv import dotenv_values
except ImportError:
    dotenv_values = lambda path: {}

def send_telegram_message(message: str):
    # Determine the root directory and find the .env file
    root_dir = Path(__file__).resolve().parents[4]
    env_path = root_dir / ".env"
    
    # Load .env variables
    env = dotenv_values(env_path)
    
    # Use value from .env or fallback to system environment variables
    token = env.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not configured in .env or environment.", file=sys.stderr)
        sys.exit(1)
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    data = json.dumps({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }).encode("utf-8")
    
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
    if len(sys.argv) < 2:
        print("Usage: python send_message.py \"Message text\"", file=sys.stderr)
        sys.exit(1)
        
    message = sys.argv[1]
    send_telegram_message(message)
