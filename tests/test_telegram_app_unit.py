"""Tests for telegram_app module — covers auth_check, split_and_send, and handler stubs."""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from gws_assistant.telegram_app import auth_check, handle_text, split_and_send


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


@pytest.mark.asyncio
async def test_run_gws_task_success():
    """run_gws_task handles successful command execution."""
    update = MagicMock()
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    mock_config = MagicMock()
    mock_config.gws_timeout_seconds = 300
    context.bot_data = {"config": mock_config}
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"output", b"")
        mock_process.returncode = 0
        mock_exec.return_value = mock_process
        
        from gws_assistant.telegram_app import run_gws_task
        await run_gws_task(update, context, "test task")
        
        assert update.effective_message.reply_text.called
        mock_exec.assert_called()


@pytest.mark.asyncio
async def test_handle_text_requires_yes_no_for_pending_confirmation():
    future = asyncio.get_running_loop().create_future()
    update = MagicMock()
    update.effective_chat.id = 12345
    update.effective_message.text = "what is the status?"
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    mock_config = MagicMock()
    mock_config.telegram_chat_id = "12345"
    context.bot_data = {"config": mock_config}
    context.application.bot_data = {"pending_confirmations": {12345: future}}

    await handle_text(update, context)

    assert not future.done()
    update.effective_message.reply_text.assert_called_once()
