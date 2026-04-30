"""Tests for telegram_app module — covers auth_check, split_and_send, and handler stubs."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from gws_assistant.telegram_app import auth_check, split_and_send


@pytest.mark.asyncio
async def test_auth_check_blocks_no_chat():
    """auth_check returns False when update has no effective_chat."""
    update = MagicMock()
    update.effective_chat = None
    context = MagicMock()
    assert await auth_check(update, context) is False


@pytest.mark.asyncio
async def test_auth_check_blocks_no_config():
    """auth_check returns False when bot_data has no config."""
    update = MagicMock()
    update.effective_chat.id = 12345
    context = MagicMock()
    context.bot_data = {}
    assert await auth_check(update, context) is False


@pytest.mark.asyncio
async def test_auth_check_blocks_wrong_chat_id():
    """auth_check returns False when chat ID doesn't match."""
    update = MagicMock()
    update.effective_chat.id = 99999
    config = MagicMock()
    config.telegram_chat_id = "12345"
    context = MagicMock()
    context.bot_data = {"config": config}
    assert await auth_check(update, context) is False


@pytest.mark.asyncio
async def test_auth_check_allows_correct_chat_id():
    """auth_check returns True when chat ID matches."""
    update = MagicMock()
    update.effective_chat.id = 12345
    config = MagicMock()
    config.telegram_chat_id = "12345"
    context = MagicMock()
    context.bot_data = {"config": config}
    assert await auth_check(update, context) is True


@pytest.mark.asyncio
async def test_split_and_send_short_message():
    """Short messages go through without splitting."""
    update = MagicMock()
    update.effective_message.reply_text = AsyncMock()
    await split_and_send(update, "Hello world")
    update.effective_message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_split_and_send_long_message():
    """Messages longer than 4096 chars get split into chunks."""
    update = MagicMock()
    update.effective_message.reply_text = AsyncMock()
    long_text = "A" * 5000
    await split_and_send(update, long_text)
    assert update.effective_message.reply_text.call_count == 2
