---
name: telegram-update
description: Sends a message to the user via Telegram to keep them updated on task progress.
---

# Telegram Update Skill

## When to use this skill
- Whenever you finish a significant portion of a plan.
- At the start or end of complex tasks.
- Whenever the user explicitly asks to be kept updated.

## How it works
This skill uses a Python script to send a message via the Telegram API. It automatically loads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from the repository's `.env` file.

## Instructions
To send an update, run the provided script with your message as an argument:
```bash
& "D:\henv\Scripts\python.exe" .agent/skills/telegram-update/scripts/send_message.py "Your message here"
```
