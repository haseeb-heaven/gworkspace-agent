"""Fast async LLM chat utilities for non-agentic communication."""

import logging

from .llm_client import call_llm
from .models import AppConfigModel

logger = logging.getLogger(__name__)


async def get_chat_response(text: str, config: AppConfigModel) -> str:
    """Get a direct response from the LLM without the heavy agent loop.
    Uses call_llm() from llm_client for robust multi-model support.
    """
    system_prompt = (
        "You are the Google Workspace Assistant. You help users with Mail, Drive, Docs, Sheets, and Calendar. "
        "If the user asks for a specific action, tell them you can do it if they provide more details. "
        "Keep your responses concise and helpful."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text},
    ]

    try:
        # call_llm handles model selection, fallbacks, and rotation internally.
        # We keep this function async for compatibility with existing callers.
        response = call_llm(messages=messages, config=config)
        return response.choices[0].message.content or "I couldn't generate a response."

    except RuntimeError as e:
        logger.error(f"Chat completion failed: {e}")
        return f"I encountered an error while trying to chat: {str(e)}"
