"""Fast async LLM chat utilities for non-agentic communication."""

import logging

from openai import AsyncOpenAI

from .models import AppConfigModel

logger = logging.getLogger(__name__)

async def get_chat_response(text: str, config: AppConfigModel) -> str:
    """Get a direct response from the LLM without the heavy agent loop."""
    if not config.api_key:
        return "I'm sorry, I don't have an LLM API key configured to chat."

    try:
        client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=10.0 # Fast timeout for chat
        )

        system_prompt = (
            "You are the Google Workspace Assistant. You help users with Mail, Drive, Docs, Sheets, and Calendar. "
            "If the user asks for a specific action, tell them you can do it if they provide more details. "
            "Keep your responses concise and helpful."
        )

        response = await client.chat.completions.create(
            model=config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            max_tokens=200,
            temperature=0.7
        )

        return response.choices[0].message.content or "I couldn't generate a response."
    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        return f"I encountered an error while trying to chat: {str(e)}"
