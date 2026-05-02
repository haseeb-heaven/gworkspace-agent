"""Telegram implementation for the human gate."""

import asyncio
import json
import logging
import os
import uuid
from typing import Optional

from telegram import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from gws_assistant.human_gate.base import HumanGateBase

logger = logging.getLogger(__name__)


class TelegramHumanGate(HumanGateBase):
    """Telegram implementation for the human gate."""

    def __init__(self):
        """Initialize the Telegram human gate."""
        self.token = os.getenv("TELEGRAM_HUMAN_GATE_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_HUMAN_GATE_CHAT_ID")

        try:
            self.question_timeout = float(os.getenv("TELEGRAM_QUESTION_TIMEOUT", "300"))
        except ValueError:
            self.question_timeout = 300.0

        try:
            self.approval_timeout = float(os.getenv("TELEGRAM_APPROVAL_TIMEOUT", "60"))
        except ValueError:
            self.approval_timeout = 60.0

        if not self.token or not self.chat_id:
            logger.warning("Telegram Human Gate is not fully configured (missing token or chat ID).")

        self.pending: dict[str, asyncio.Future] = {}
        self.msg_to_qid: dict[int, str] = {}
        self.lock = asyncio.Lock()
        self._app: Optional[Application] = None
        self._polling_task: Optional[asyncio.Task] = None
        self._is_running = False

    async def start(self) -> None:
        """Start the Telegram polling loop in the background."""
        if self._is_running:
            return

        if not self.token:
            raise ValueError("TELEGRAM_HUMAN_GATE_TOKEN not set")

        logger.info("Starting Telegram Human Gate...")

        # Build the application
        self._app = Application.builder().token(self.token).build()

        # Register handlers
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        self._app.add_handler(CallbackQueryHandler(self._handle_callback))

        # Initialize and start polling in background
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)

        self._is_running = True
        logger.info("Telegram Human Gate started.")

    async def stop(self) -> None:
        """Stop the Telegram polling loop."""
        if not self._is_running or not self._app:
            return

        logger.info("Stopping Telegram Human Gate...")
        await self._app.updater.stop()
        await self._app.stop()
        await self._app.shutdown()
        self._is_running = False
        logger.info("Telegram Human Gate stopped.")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages (specifically replies)."""
        if not update.message or str(update.message.chat_id) != str(self.chat_id):
            return

        reply_to = update.message.reply_to_message
        if not reply_to:
            return

        reply_msg_id = reply_to.message_id

        async with self.lock:
            qid = self.msg_to_qid.get(reply_msg_id)
            if qid and qid in self.pending:
                future = self.pending[qid]
                if not future.done():
                    future.set_result(update.message.text)
                    await update.message.reply_text("✅ Got it!")

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming inline keyboard callbacks."""
        query = update.callback_query
        if not query or not query.message or str(query.message.chat_id) != str(self.chat_id):
            return

        await query.answer()  # Remove loading spinner

        try:
            data = json.loads(query.data)
            qid = data.get("qid")
            answer = data.get("answer")

            async with self.lock:
                if qid and qid in self.pending:
                    future = self.pending[qid]
                    if not future.done():
                        future.set_result(answer)

                        # Edit message to show selection
                        try:
                            await query.edit_message_text(
                                f"{query.message.text}\n\n✅ Selected: {answer}"
                            )
                        except Exception as e:
                            logger.error(f"Error editing message: {e}")
        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.error(f"Error handling callback: {e}")

    async def notify(self, message: str) -> None:
        """Send a simple text notification to the configured chat."""
        if not self._app or not self.chat_id:
            return

        try:
            await self._app.bot.send_message(chat_id=self.chat_id, text=message)
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    async def ask_text(self, question: str, context: str = "", timeout: float = 300) -> str:
        """Ask a free-text question."""
        if not self._app or not self.chat_id:
            raise RuntimeError("Telegram Human Gate not started or not configured")

        qid = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()

        async with self.lock:
            self.pending[qid] = future

        try:
            text = f"❓ Question\n\n{question}"
            if context:
                text += f"\n\nContext: {context}"
            text += "\n\n[Reply to this message]"

            msg = await self._app.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                reply_markup=ForceReply(selective=True)
            )

            async with self.lock:
                self.msg_to_qid[msg.message_id] = qid

            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            await self.notify("⏰ Timeout — action cancelled")
            raise TimeoutError("Timed out waiting for text reply")
        finally:
            async with self.lock:
                self.pending.pop(qid, None)

    async def ask_approval(self, action: str, details: str, timeout: float = 60) -> bool:
        """Ask for approval with yes/no buttons."""
        if not self._app or not self.chat_id:
            raise RuntimeError("Telegram Human Gate not started or not configured")

        qid = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()

        async with self.lock:
            self.pending[qid] = future

        try:
            text = f"⚠️ Approval Required\n\nAction: {action}\nDetails: {details}"

            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=json.dumps({"qid": qid, "answer": "yes"})),
                    InlineKeyboardButton("❌ Reject", callback_data=json.dumps({"qid": qid, "answer": "no"}))
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await self._app.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                reply_markup=reply_markup
            )

            result = await asyncio.wait_for(future, timeout=timeout)
            return result == "yes"
        except asyncio.TimeoutError:
            await self.notify("⏰ Timeout — action cancelled")
            raise TimeoutError("Timed out waiting for approval")
        finally:
            async with self.lock:
                self.pending.pop(qid, None)

    async def ask_choice(self, question: str, choices: list[str], timeout: float = 120) -> str:
        """Ask to choose from a list of options."""
        if not self._app or not self.chat_id:
            raise RuntimeError("Telegram Human Gate not started or not configured")

        qid = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()

        async with self.lock:
            self.pending[qid] = future

        try:
            keyboard = []
            for choice in choices:
                # Ensure callback_data size is within Telegram limits (64 bytes)
                cb_data = json.dumps({"qid": qid, "answer": choice})
                if len(cb_data) > 64:
                    # Fallback or error if too long, though UUID takes 36 bytes.
                    # Might need a mapping if choices are very long.
                    logger.warning(f"Callback data might be too long: {len(cb_data)} bytes")

                keyboard.append([InlineKeyboardButton(choice, callback_data=cb_data)])

            reply_markup = InlineKeyboardMarkup(keyboard)

            await self._app.bot.send_message(
                chat_id=self.chat_id,
                text=f"❓ {question}",
                reply_markup=reply_markup
            )

            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            await self.notify("⏰ Timeout — action cancelled")
            raise TimeoutError("Timed out waiting for choice")
        finally:
            async with self.lock:
                self.pending.pop(qid, None)
