import asyncio
import logging
import sys
import os
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from gws_assistant.config import AppConfig

logger = logging.getLogger(__name__)

# The specific commands requested by the user
ALLOWED_COMMANDS = ["mail", "docs", "sheet", "calendar", "notes"]

async def auth_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the user is allowed to interact with the bot based on TELEGRAM_CHAT_ID."""
    if not update.effective_chat:
        return False

    config = context.bot_data.get("config")
    if not config or not config.telegram_chat_id:
        # If no strict chat ID is configured, fail closed or open?
        # User requested: "strictly to bot from .env data only"
        # So if not configured, block.
        logger.warning("TELEGRAM_CHAT_ID not configured. Blocking message.")
        return False

    if str(update.effective_chat.id) != str(config.telegram_chat_id):
        logger.warning(f"Unauthorized access attempt from chat ID {update.effective_chat.id}")
        return False

    return True

async def split_and_send(update: Update, text: str):
    """Split message into <= 4096 character chunks and send."""
    MAX_LEN = 4096

    if not text:
        text = "No output returned."

    # First, try to split by lines
    lines = text.split('\n')
    chunk = ""
    for line in lines:
        if len(chunk) + len(line) + 1 > MAX_LEN:
            if chunk:
                await update.effective_message.reply_text(chunk)
                chunk = ""

            # If a single line is still longer than MAX_LEN, split it strictly
            while len(line) > MAX_LEN:
                await update.effective_message.reply_text(line[:MAX_LEN])
                line = line[MAX_LEN:]
        chunk += line + "\n"

    if chunk.strip():
        await update.effective_message.reply_text(chunk.strip())

async def run_gws_task(update: Update, context: ContextTypes.DEFAULT_TYPE, task_text: str):
    """Execute the task by calling python gws_cli.py --task <task_text>"""

    logger.info(f"Starting command execution for task: {task_text[:50]}...")
    await update.effective_message.reply_text("Received task")
    await update.effective_message.reply_text("Running gws_cli.py")

    try:
        # Execute gws_cli.py --task asynchronously
        # Use sys.executable to ensure the same Python environment
        process = await asyncio.create_subprocess_exec(
            sys.executable, "gws_cli.py", "--task", task_text,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # We also need a timeout to avoid hanging indefinitely.
        config = context.bot_data.get("config")
        # In the config model, the generic execution timeout is `timeout_seconds`,
        # but there is also a specific `gws_timeout_seconds` defined which we use.
        # Fall back to 90 if neither is reliably present.
        timeout_seconds = getattr(config, 'gws_timeout_seconds', getattr(config, 'timeout_seconds', 90)) if config else 90

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.warning(f"Command timed out after {timeout_seconds} seconds for task: {task_text[:50]}...")
            process.kill()
            await process.communicate()
            await update.effective_message.reply_text(f"Command timed out after {timeout_seconds} seconds.")
            return

        stdout = stdout_bytes.decode('utf-8', errors='replace').strip()
        stderr = stderr_bytes.decode('utf-8', errors='replace').strip()

        logger.info(f"Command completed for task: {task_text[:50]}...")
        await update.effective_message.reply_text("Command completed")

        if process.returncode != 0:
            logger.error(f"Task failed with exit code {process.returncode}. Stderr: {stderr}")
            await update.effective_message.reply_text(f"Task failed with exit code {process.returncode}.")

        await update.effective_message.reply_text("Sending result")

        output = stdout if stdout else stderr
        await split_and_send(update, output)

    except Exception as e:
        logger.exception("Exception while executing gws_cli.py")
        await update.effective_message.reply_text(f"Error executing task: {str(e)}")


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_check(update, context):
        return
    await update.effective_message.reply_text("Hello! I am your Google Workspace Assistant. Send me a task or use commands like /mail, /docs, etc.")

async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_check(update, context):
        return
    help_text = (
        "Send me natural language tasks to perform actions in Google Workspace.\n"
        "You can just send text or prefix it with commands:\n"
        "/mail <task>\n"
        "/docs <task>\n"
        "/sheet <task>\n"
        "/calendar <task>\n"
        "/notes <task>\n"
    )
    await update.effective_message.reply_text(help_text)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_check(update, context):
        return

    task_text = update.effective_message.text.strip()
    if not task_text:
        return

    await run_gws_task(update, context, task_text)

async def handle_service_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_check(update, context):
        return

    # Example: /docs Create a new document about project X
    # Here, we keep the service name as part of the task string to let AI parse it better.
    # So "/docs Create a new document" becomes "docs Create a new document"
    text = update.effective_message.text.strip()
    # Strip the leading '/'
    if text.startswith('/'):
        text = text[1:]

    await run_gws_task(update, context, text)

def create_application(config: AppConfig) -> Application:
    """Create and configure the Telegram application."""
    if not config.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in configuration.")

    application = Application.builder().token(config.telegram_bot_token).build()

    # Store config in bot_data for access in handlers
    application.bot_data["config"] = config

    # Add handlers
    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(CommandHandler("help", handle_help))

    for cmd in ALLOWED_COMMANDS:
        application.add_handler(CommandHandler(cmd, handle_service_command))

    # Handle normal text (excluding commands)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    return application
