import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


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

    # Fallback: Find the first { or [ and the last } or ]
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if match:
        candidate = match.group(1)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # Try to be even more aggressive if there's trailing garbage
            # like "Footer message" after the JSON
            # We search for the LAST } that makes it a valid JSON
            for i in range(len(candidate), 0, -1):
                if candidate[i - 1] in ("}", "]"):
                    try:
                        return json.loads(candidate[:i])
                    except json.JSONDecodeError:
                        continue

    # If all fails, raise the original error or return as is?
    # For compatibility with existing callers, we might want to return the string
    # but the goal is to fix parsing.
    raise ValueError(f"Could not extract valid JSON from text: {text[:100]}...")


def safe_json_loads(text: str, fallback_to_string: bool = False) -> Any:
    """
    Safely loads JSON from potentially polluted text.
    """
    try:
        return extract_json(text)
    except Exception as e:
        if fallback_to_string:
            return text
        raise e
