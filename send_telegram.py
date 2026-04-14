
import os
import sys
import json
import subprocess
from dotenv import load_dotenv

def send_telegram(message):
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not found in .env")
        return False
    
    client_path = r"C:\Users\hasee\.gemini\extensions\telegram\src\client.py"
    
    payload = {
        "chat_id": chat_id,
        "text": message
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
