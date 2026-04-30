"""Telegram Polling Wrapper for Google Workspace Assistant."""

import sys
from pathlib import Path

# Ensure the package is in the PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gws_assistant.config import AppConfig
from gws_assistant.logging_utils import setup_logging
from gws_assistant.telegram_app import create_application


def main():
    config = AppConfig.from_env()
    logger = setup_logging(config)

    if not config.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is not configured in .env")
        sys.exit(1)

    if not config.telegram_chat_id:
        logger.error("TELEGRAM_CHAT_ID is not configured in .env. Bot will block all messages without it.")

    try:
        app = create_application(config)
        logger.info("Starting Telegram Bot in polling mode...")
        app.run_polling()
    except Exception:
        logger.exception("Failed to start Telegram Bot")
        sys.exit(1)


if __name__ == "__main__":
    main()
