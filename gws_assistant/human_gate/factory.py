"""Factory for creating human gate instances."""

import logging
import os

from gws_assistant.human_gate.base import HumanGateBase
from gws_assistant.human_gate.console_gate import ConsoleFallbackGate
from gws_assistant.human_gate.telegram_gate import TelegramHumanGate

logger = logging.getLogger(__name__)


def get_human_gate() -> HumanGateBase:
    """
    Get the appropriate human gate instance based on environment variables.

    If TELEGRAM_HUMAN_GATE_TOKEN and TELEGRAM_HUMAN_GATE_CHAT_ID are set,
    returns a TelegramHumanGate. Otherwise, returns a ConsoleFallbackGate.

    Returns:
        An instance of a HumanGateBase subclass.
    """
    token = os.getenv("TELEGRAM_HUMAN_GATE_TOKEN")
    chat_id = os.getenv("TELEGRAM_HUMAN_GATE_CHAT_ID")

    if token and chat_id:
        logger.info("Using Telegram Human Gate")
        return TelegramHumanGate()
    else:
        logger.info("Using Console Fallback Human Gate")
        return ConsoleFallbackGate()
