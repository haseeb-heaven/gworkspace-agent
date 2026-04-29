from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Chat, Message, Update
from telegram.ext import ContextTypes

from gws_assistant.config import AppConfigModel
from gws_assistant.telegram_app import (
    auth_check,
    handle_service_command,
    handle_text,
    run_gws_task,
    split_and_send,
)


@pytest.fixture
def mock_config():
    config = AppConfigModel(
        provider="openrouter",
        model="openrouter/free",
        api_key="test-key",
        llm_fallback_models=[],
        base_url=None,
        timeout_seconds=30,
        gws_binary_path=None,
        log_file_path=None,
        log_level="INFO",
        verbose=False,
        env_file_path=None,
        setup_complete=True,
        max_retries=3,
        langchain_enabled=True,
        telegram_bot_token="test_bot_token",
        telegram_chat_id="12345",
    )
    return config


@pytest.fixture
def mock_update():
    update = AsyncMock(spec=Update)
    chat = MagicMock(spec=Chat)
    chat.id = 12345
    update.effective_chat = chat
    message = AsyncMock(spec=Message)
    update.effective_message = message
    return update


@pytest.fixture
def mock_context(mock_config):
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot_data = {"config": mock_config}
    return context


@pytest.mark.asyncio
async def test_auth_check_allowed(mock_update, mock_context):
    assert await auth_check(mock_update, mock_context) is True


@pytest.mark.asyncio
async def test_auth_check_denied(mock_update, mock_context):
    mock_update.effective_chat.id = 99999
    assert await auth_check(mock_update, mock_context) is False


@pytest.mark.asyncio
async def test_auth_check_no_config(mock_update):
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot_data = {}
    assert await auth_check(mock_update, context) is False


@pytest.mark.asyncio
async def test_split_and_send_short(mock_update):
    await split_and_send(mock_update, "short message")
    mock_update.effective_message.reply_text.assert_called_once_with("short message")


@pytest.mark.asyncio
async def test_split_and_send_long(mock_update):
    long_msg = "A" * 4000 + "\n" + "B" * 1000
    await split_and_send(mock_update, long_msg)
    assert mock_update.effective_message.reply_text.call_count == 2

    calls = mock_update.effective_message.reply_text.call_args_list
    assert calls[0][0][0].strip() == "A" * 4000
    assert calls[1][0][0].strip() == "B" * 1000


@pytest.mark.asyncio
async def test_split_and_send_empty(mock_update):
    await split_and_send(mock_update, "")
    mock_update.effective_message.reply_text.assert_called_once_with("No output returned.")


@pytest.mark.asyncio
@patch("gws_assistant.telegram_app.asyncio.create_subprocess_exec")
async def test_run_gws_task_success(mock_create_subprocess, mock_update, mock_context):
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"mock stdout", b"mock stderr")
    mock_process.returncode = 0
    mock_create_subprocess.return_value = mock_process

    await run_gws_task(mock_update, mock_context, "test task")

    mock_create_subprocess.assert_called_once()
    assert mock_create_subprocess.call_args[0][2] == "--task"
    assert mock_create_subprocess.call_args[0][3] == "test task"

    # Check messages
    calls = mock_update.effective_message.reply_text.call_args_list
    assert any("mock stdout" in call[0][0] for call in calls)


@pytest.mark.asyncio
@patch("gws_assistant.telegram_app.asyncio.create_subprocess_exec")
async def test_run_gws_task_stderr_fallback(mock_create_subprocess, mock_update, mock_context):
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"", b"mock stderr")
    mock_process.returncode = 1
    mock_create_subprocess.return_value = mock_process

    await run_gws_task(mock_update, mock_context, "test task")

    calls = mock_update.effective_message.reply_text.call_args_list
    assert any("mock stderr" in call[0][0] for call in calls)
    assert any("Task failed with exit code 1" in call[0][0] for call in calls)


@pytest.mark.asyncio
async def test_handle_text(mock_update, mock_context):
    with patch("gws_assistant.telegram_app.run_gws_task", new_callable=AsyncMock) as mock_run_task:
        mock_update.effective_message.text = "send email"
        await handle_text(mock_update, mock_context)
        mock_run_task.assert_called_once_with(mock_update, mock_context, "send email")


@pytest.mark.asyncio
async def test_handle_text_unauthorized(mock_update, mock_context):
    with patch("gws_assistant.telegram_app.run_gws_task", new_callable=AsyncMock) as mock_run_task:
        mock_update.effective_chat.id = 99999
        await handle_text(mock_update, mock_context)
        mock_run_task.assert_not_called()


@pytest.mark.asyncio
async def test_handle_service_command(mock_update, mock_context):
    with patch("gws_assistant.telegram_app.run_gws_task", new_callable=AsyncMock) as mock_run_task:
        mock_update.effective_message.text = "/docs Create a doc"
        await handle_service_command(mock_update, mock_context)
        mock_run_task.assert_called_once_with(mock_update, mock_context, "docs Create a doc")


@pytest.mark.asyncio
async def test_auth_rejects_wrong_chat_id(mock_update, mock_context):
    mock_context.bot_data["config"].telegram_chat_id = "111111"
    mock_update.effective_chat.id = 999999

    with patch("gws_assistant.telegram_app.run_gws_task", new_callable=AsyncMock) as mock_run_task:
        await handle_text(mock_update, mock_context)
        mock_run_task.assert_not_called()
        mock_update.effective_message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_auth_accepts_correct_chat_id(mock_update, mock_context):
    mock_context.bot_data["config"].telegram_chat_id = "111111"
    mock_update.effective_chat.id = 111111
    mock_update.effective_message.text = "send email"

    with patch("gws_assistant.telegram_app.run_gws_task", new_callable=AsyncMock) as mock_run_task:
        await handle_text(mock_update, mock_context)
        mock_run_task.assert_called_once_with(mock_update, mock_context, "send email")


@pytest.mark.asyncio
async def test_auth_rejects_when_chat_id_env_missing(mock_update, mock_context):
    mock_context.bot_data["config"].telegram_chat_id = ""
    mock_update.effective_message.text = "do something"

    with patch("gws_assistant.telegram_app.run_gws_task", new_callable=AsyncMock) as mock_run_task:
        await handle_text(mock_update, mock_context)
        mock_run_task.assert_not_called()
        mock_update.effective_message.reply_text.assert_not_called()
