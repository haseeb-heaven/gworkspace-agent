import asyncio
import logging
import sys

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
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
    lines = text.split("\n")
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
    await update.effective_message.reply_text("Received task. Processing...")

    config = context.bot_data.get("config")
    timeout = 300
    if config and hasattr(config, "gws_timeout_seconds") and config.gws_timeout_seconds > 0:
        timeout = config.gws_timeout_seconds

    try:
        # Execute gws_cli.py --task asynchronously
        # Use sys.executable to ensure the same Python environment
        import os

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "gws_cli.py",
            "--task",
            task_text,
            "--read-write",
            "--no-sandbox",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # Execute gws_cli.py until it naturally finishes
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                process.kill()
                await process.wait()
            except Exception:
                pass
            logger.error(f"Task timed out after {timeout} seconds: {task_text[:50]}")
            await update.effective_message.reply_text(f"Error: Task timed out after {timeout}s.")
            return

        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()

        logger.info(f"Command completed for task: {task_text[:50]}...")

        if process.returncode != 0:
            logger.error(f"Task failed with exit code {process.returncode}. Stderr: {stderr}")
            # If we have stderr, show it, otherwise show a generic error
            msg = f"Task failed with exit code {process.returncode}."
            if stderr:
                msg += f"\n\nDetails:\n{stderr}"
            await update.effective_message.reply_text(msg)
            return

        output = stdout if stdout else stderr
        await split_and_send(update, output)

    except Exception as e:
        logger.exception("Exception while executing gws_cli.py")
        await update.effective_message.reply_text(f"Error executing task: {str(e)}")


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_check(update, context):
        return
    await update.effective_message.reply_text(
        "Hello! I am your Google Workspace Assistant. Send me a task or use commands like /mail, /docs, etc."
    )


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

    # 1. Simple greeting / conversational check to avoid 90s timeout
    greetings = {"hi", "hello", "hey", "hola", "yo", "greeting", "morning", "afternoon", "evening"}
    lowered = task_text.lower().rstrip(".!?")

    if lowered in greetings:
        await update.effective_message.reply_text(
            "Hello! I'm your Google Workspace Assistant. I can help you with Mail, Drive, Docs, Sheets, Calendar and more. "
            "What would you like me to do?"
        )
        return

    if lowered in {"help", "what can you do", "commands"}:
        await handle_help(update, context)
        return

    if lowered in {"thanks", "thank you", "nice", "cool", "great"}:
        await update.effective_message.reply_text(
            "You're welcome! Let me know if there's anything else I can help with."
        )
        return

    # 2. Check if it's likely a Google Workspace task before running the heavy agent
    # We use a simple keyword check as a first-pass filter
    gws_keywords = {
        "email",
        "mail",
        "gmail",
        "inbox",
        "message",
        "send",
        "subject",
        "body",
        "drive",
        "file",
        "folder",
        "upload",
        "download",
        "export",
        "move",
        "find",
        "doc",
        "document",
        "sheet",
        "spreadsheet",
        "table",
        "append",
        "row",
        "column",
        "calendar",
        "event",
        "meeting",
        "meet",
        "schedule",
        "reminder",
        "appointment",
        "task",
        "todo",
        "note",
        "keep",
    }

    has_gws_intent = any(kw in lowered for kw in gws_keywords)

    # If it has no obvious GWS intent and it's short, it's likely chat
    if not has_gws_intent and len(task_text.split()) < 5:
        config = context.bot_data.get("config")
        if config:
            from .chat_utils import get_chat_response

            response = await get_chat_response(task_text, config)
            await update.effective_message.reply_text(response)
            return

    # 3. If it looks like a task, run the full agent
    await run_gws_task(update, context, task_text)


async def handle_service_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_check(update, context):
        return

    # Example: /docs Create a new document about project X
    # Here, we keep the service name as part of the task string to let AI parse it better.
    # So "/docs Create a new document" becomes "docs Create a new document"
    text = update.effective_message.text.strip()
    # Strip the leading '/'
    if text.startswith("/"):
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
