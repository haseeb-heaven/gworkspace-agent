import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class JsonExtractionError(ValueError):
    """Raised when polluted or malformed text cannot be parsed into JSON."""


def extract_json(text: str) -> Any:
    """
    Extracts and parses the first JSON object or array found in the text.
    Handles pollution from diagnostic messages (like keyring warnings).
    """
    if not text:
        return None

    # Try direct parse first
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Specifically handle common diagnostic prefixes
    # "Using keyring backend: keyring"
    # "Using keyring backend: keyring\n{...}"
    cleaned = text
    prefixes = [
        r"Using keyring backend:.*",
    ]
    for pattern in prefixes:
        cleaned = re.sub(pattern, "", cleaned).strip()

    try:
        if cleaned:
            return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fallback: Find the first { or [ and try to decode from there using JSONDecoder
    decoder = json.JSONDecoder()
    for i, char in enumerate(text):
        if char in ('{', '['):
            try:
                obj, _ = decoder.raw_decode(text[i:])
                return obj
            except json.JSONDecodeError:
                continue

    # If all fails, raise the original error
    raise JsonExtractionError(f"Could not extract valid JSON from text: {text[:100]}...")


def safe_json_loads(text: str, fallback_to_string: bool = False) -> Any:
    """
    Safely loads JSON from potentially polluted text.
    """
    try:
        return extract_json(text)
    except (JsonExtractionError, json.JSONDecodeError, ValueError):
        if fallback_to_string:
            logger.warning("Falling back to raw text after JSON decode failure.")
            return text
        raise
