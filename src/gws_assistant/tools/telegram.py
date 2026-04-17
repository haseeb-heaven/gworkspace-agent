import json
import os
import subprocess
import sys
import logging

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

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
        from gws_assistant.memory import LongTermMemory
        
        config = AppConfig.from_env()
        memory = LongTermMemory(config)
        
        memories = memory.search(message)
        if memories:
            memory_context = "\n\n--- Relevant Context ---\n" + "\n".join(
                f"- {m.get('memory', m.get('text', str(m)))}" for m in memories[:3]
            )
            enriched_message += memory_context
    except Exception as e:
        logger.debug(f"Could not enrich Telegram message with memory: {e}")

    client_path = r"C:\Users\hasee\.gemini\extensions\telegram\src\client.py"

    payload = {
        "chat_id": chat_id,
        "text": enriched_message
    }

    try:
        # Use D:\henv\Scripts\python.exe as requested in memories
        process = subprocess.Popen(
            [r"D:\henv\Scripts\python.exe", client_path, "send_message"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=json.dumps(payload))

        if process.returncode == 0:
            print(f"Telegram message sent: {stdout}")
            return True
        else:
            print(f"Error sending Telegram message: {stderr}")
            return False
    except Exception as e:
        print(f"Exception sending Telegram message: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        send_telegram(" ".join(sys.argv[1:]))
    else:
        print("Usage: python send_telegram.py <message>")
