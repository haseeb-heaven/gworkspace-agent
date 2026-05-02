"""Tests for the human gate module."""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from gws_assistant.human_gate.console_gate import ConsoleFallbackGate
from gws_assistant.human_gate.telegram_gate import TelegramHumanGate
from gws_assistant.human_gate.factory import get_human_gate

# Ensure tests have required markers
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_HUMAN_GATE_TOKEN", "mocked_bot_token_string")
    monkeypatch.setenv("TELEGRAM_HUMAN_GATE_CHAT_ID", "123456")


async def test_console_gate_ask_text():
    """Test console gate ask_text."""
    gate = ConsoleFallbackGate()
    with patch("builtins.print") as mock_print:
        with patch("builtins.input", return_value="answer"):
            res = await gate.ask_text("What?")
            assert res == "answer"  # nosec


async def test_console_gate_ask_text_timeout():
    """Test console gate timeout for ask_text."""
    gate = ConsoleFallbackGate()

    def slow_ask(*args, **kwargs):
        import time
        time.sleep(0.2)
        return "late"

    with patch("builtins.print"):
        with patch("builtins.input", side_effect=slow_ask):
            with pytest.raises(TimeoutError):
                await gate.ask_text("What?", timeout=0.1)


async def test_telegram_gate_initialization(mock_env):
    """Test Telegram gate initializes with correct config."""
    gate = TelegramHumanGate()
    assert gate.token == "mocked_bot_token_string"  # nosec
    assert gate.chat_id == "123456"  # nosec
    assert gate.question_timeout == 300.0  # nosec


async def test_telegram_gate_notify(mock_env):
    """Test Telegram gate notify."""
    gate = TelegramHumanGate()
    gate._app = MagicMock()
    gate._app.bot = MagicMock()
    gate._app.bot.send_message = AsyncMock()

    await gate.notify("hello")
    gate._app.bot.send_message.assert_called_once_with(chat_id="123456", text="hello")


async def test_telegram_gate_ask_text_timeout(mock_env):
    """Test Telegram gate ask_text timeout."""
    gate = TelegramHumanGate()
    gate._app = MagicMock()
    gate._app.bot = MagicMock()

    mock_msg = MagicMock()
    mock_msg.message_id = 42
    gate._app.bot.send_message = AsyncMock(return_value=mock_msg)

    with pytest.raises(TimeoutError):
        await gate.ask_text("Question?", timeout=0.1)


def test_factory_returns_telegram(mock_env):
    """Test factory returns telegram gate when env is set."""
    gate = get_human_gate()
    assert isinstance(gate, TelegramHumanGate)  # nosec


def test_factory_returns_console(monkeypatch):
    """Test factory returns console gate when env is missing."""
    monkeypatch.delenv("TELEGRAM_HUMAN_GATE_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_HUMAN_GATE_CHAT_ID", raising=False)
    gate = get_human_gate()
    assert isinstance(gate, ConsoleFallbackGate)  # nosec

async def test_telegram_gate_ask_approval(mock_env):
    """Test Telegram gate ask_approval."""
    gate = TelegramHumanGate()
    gate._app = MagicMock()
    gate._app.bot = MagicMock()

    mock_msg = MagicMock()
    mock_msg.message_id = 42
    gate._app.bot.send_message = AsyncMock(return_value=mock_msg)

    import asyncio
    async def simulate_callback():
        await asyncio.sleep(0.01)
        # Find the pending qid
        qid = list(gate.pending.keys())[0]
        gate.pending[qid].set_result("yes")

    asyncio.create_task(simulate_callback())

    result = await gate.ask_approval("Action", "Details")
    assert result is True  # nosec
    gate._app.bot.send_message.assert_called_once()


async def test_telegram_gate_ask_choice(mock_env):
    """Test Telegram gate ask_choice."""
    gate = TelegramHumanGate()
    gate._app = MagicMock()
    gate._app.bot = MagicMock()

    mock_msg = MagicMock()
    mock_msg.message_id = 42
    gate._app.bot.send_message = AsyncMock(return_value=mock_msg)

    import asyncio
    async def simulate_callback():
        await asyncio.sleep(0.01)
        qid = list(gate.pending.keys())[0]
        # set answer for mock simulation
        gate.pending[qid].set_result("opt1")

    asyncio.create_task(simulate_callback())

    result = await gate.ask_choice("Question", ["opt1", "opt2"])
    assert result == "opt1"  # nosec
    gate._app.bot.send_message.assert_called_once()


async def test_console_gate_ask_approval():
    """Test console gate ask_approval."""
    gate = ConsoleFallbackGate()
    with patch("builtins.print"):
        with patch("builtins.input", return_value="y"):
            res = await gate.ask_approval("Action", "Details")
            assert res is True  # nosec


async def test_console_gate_ask_choice():
    """Test console gate ask_choice."""
    gate = ConsoleFallbackGate()
    with patch("builtins.print"):
        with patch("builtins.input", return_value="1"):
            res = await gate.ask_choice("Question", ["opt1", "opt2"])
            assert res == "opt1"  # nosec
