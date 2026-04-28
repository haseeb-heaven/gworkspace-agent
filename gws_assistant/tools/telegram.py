import json
import logging
import os
import re
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


_SECRET_ENV_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "AUTH")
_SECRET_PATTERNS = (
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"(sk|or|m0)-[A-Za-z0-9._-]{12,}"),
    re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b"),
)


def redact_sensitive(text: object) -> str:
    """Redact secrets before writing logs or sending Telegram updates."""
    redacted = str(text)
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)

    for name, value in os.environ.items():
        if not value or len(value) < 6:
            continue
        if any(marker in name.upper() for marker in _SECRET_ENV_MARKERS):
            redacted = redacted.replace(value, "[REDACTED]")
    return redacted


def send_telegram(message, context=None):
    """
    Send a message to Telegram.
    If context is provided, it can be used to enrich the message.
    """
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not found in .env")
        return False

    # Try to enrich message with LongTermMemory (Mem0) if available
    enriched_message = message
    try:
        from gws_assistant.config import AppConfig
        from gws_assistant.memory_backend import get_memory_backend

        config = AppConfig.from_env()
        memory = get_memory_backend(config)

        memories = memory.search(str(message), user_id=config.mem0_user_id)
        if memories:
            memory_context = "\n\n--- Relevant Context ---\n" + "\n".join(
                f"- {m.get('memory', m.get('text', str(m)))}" for m in memories[:3]
            )
            enriched_message += memory_context
    except Exception as e:
        logger.debug(f"Could not enrich Telegram message with memory: {e}")

    payload = {
        "chat_id": chat_id,
        "text": redact_sensitive(enriched_message),
    }

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read()
        print("Telegram message sent.")
        return True
    except urllib.error.URLError as e:
        print(f"Error sending Telegram message: {e}")
        return False
    except Exception as e:
        print(f"Exception sending Telegram message: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        send_telegram(" ".join(sys.argv[1:]))
    else:
        print("Usage: python send_telegram.py <message>")
