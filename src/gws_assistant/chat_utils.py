"""Fast async LLM chat utilities for non-agentic communication."""

import asyncio
import logging

from openai import AsyncOpenAI

from .models import AppConfigModel

logger = logging.getLogger(__name__)


async def get_chat_response(text: str, config: AppConfigModel) -> str:
    """Get a direct response from the LLM without the heavy agent loop.
    Implements API key rotation on rate limits (429).
    """
    if not config.api_key and not config.openrouter_api_keys:
        return "I'm sorry, I don't have an LLM API key configured to chat."

    max_retries = config.max_retries or 3

    for attempt in range(max_retries):
        try:
            client = AsyncOpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=15.0,  # Slightly longer for stability
            )

            system_prompt = (
                "You are the Google Workspace Assistant. You help users with Mail, Drive, Docs, Sheets, and Calendar. "
                "If the user asks for a specific action, tell them you can do it if they provide more details. "
                "Keep your responses concise and helpful."
            )

            response = await client.chat.completions.create(
                model=config.api_model_name(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                max_tokens=200,
                temperature=0.7,
            )

            return response.choices[0].message.content or "I couldn't generate a response."

        except Exception as e:
            msg = str(e).lower()
            is_rate_limit = "429" in msg or "rate limit" in msg or "quota" in msg

            if is_rate_limit and attempt < max_retries - 1:
                delay = 2**attempt
                logger.warning(f"LLM rate limit detected in Chat. Rotating key and retrying in {delay}s...")
                config.rotate_api_key()
                await asyncio.sleep(delay)
                continue

            logger.error(f"Chat completion failed after {attempt + 1} attempts: {e}")
            return f"I encountered an error while trying to chat: {str(e)}"

    return "I'm sorry, I reached my rate limit and couldn't get a response after several attempts."
