"""Post-retrieval relevance scoring and filtering.

Ensures that fetched results (Drive files, Gmail messages) actually match
the user's original query intent, filtering out irrelevant items.
"""

from __future__ import annotations

import re
from typing import Any

_QUOTED_PHRASE_RE = re.compile(r"""['"]([^'"]{2,80})['"]""")
_WORD_RE = re.compile(r"[a-zA-Z]{3,}")


def extract_keywords(text: str) -> list[str]:
    """Extract meaningful search keywords from user text.

    Pulls quoted phrases first, then significant individual words,
    filtering out common stop words and short tokens.
    """
    keywords: list[str] = []

    # Extract quoted phrases (highest priority)
    for match in _QUOTED_PHRASE_RE.findall(text):
        keywords.append(match.strip().lower())

    # Extract significant words (skip stop words)
    stop_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "for",
        "of",
        "in",
        "on",
        "at",
        "is",
        "it",
        "this",
        "that",
        "with",
        "from",
        "by",
        "as",
        "all",
        "my",
        "me",
        "do",
        "if",
        "so",
        "up",
        "can",
        "also",
        "then",
        "into",
        "using",
        "about",
        "should",
        "would",
        "could",
        "please",
        "search",
        "find",
        "list",
        "show",
        "get",
        "create",
        "send",
        "email",
        "google",
        "drive",
        "sheet",
        "sheets",
        "calendar",
        "documents",
        "document",
        "files",
        "file",
        "data",
        "table",
        "format",
        "save",
        "extract",
        "content",
        "relevant",
        "structured",
        "well",
        "convert",
        "these",
        "those",
        "needed",
        "ensure",
        "generate",
        "handle",
        "maintain",
        "including",
        "attach",
        "attachment",
        "link",
        "clean",
        "remove",
        "duplicate",
        "proper",
        "column",
        "headers",
        "summary",
        "concise",
        "key",
        "insights",
        "highlight",
        "multiple",
        "matching",
        "selecting",
        "most",
        "one",
        "version",
        "history",
        "set",
        "reminders",
        "organize",
        "related",
        "folder",
        "log",
        "activity",
        "tracking",
        "auditing",
        "notification",
        "via",
        "chat",
        "store",
        "metadata",
        "admin",
        "sdk",
        "optionally",
        "sync",
        "forms",
        "presentation",
        "slides",
        "enable",
        "audit",
        "logging",
        "access",
        "control",
        "additionally",
        "discussion",
        "enforce",
    }

    words = _WORD_RE.findall(text.lower())
    seen_keywords = {k.lower() for k in keywords}
    for word in words:
        if word not in stop_words and word not in seen_keywords:
            keywords.append(word)
            seen_keywords.add(word)

    return keywords


def score_item(item_text: str, keywords: list[str]) -> float:
    """Score how relevant an item is to the keywords.

    Returns a float between 0.0 (irrelevant) and 1.0 (perfect match).
    Phrase matches score higher than individual word matches.
    """
    if not keywords or not item_text:
        return 0.0

    lowered = item_text.lower()
    total_score = 0.0
    max_possible = 0.0

    for keyword in keywords:
        weight = len(keyword.split()) + 1  # Phrases get higher weight
        max_possible += weight
        if keyword.lower() in lowered:
            total_score += weight

    return total_score / max_possible if max_possible > 0 else 0.0


def filter_drive_files(
    files: list[dict[str, Any]],
    keywords: list[str],
    min_score: float = 0.05,
) -> list[dict[str, Any]]:
    """Filter Drive files by relevance to the user's query keywords.

    Each file is scored based on its name and MIME type against the keywords.
    Files with a score below `min_score` are excluded.
    If filtering would remove ALL files, returns the original list unfiltered.
    """
    if not keywords or not files:
        return files

    scored: list[tuple[float, dict[str, Any]]] = []
    for f in files:
        text = " ".join(
            [
                str(f.get("name") or ""),
                str(f.get("mimeType") or ""),
            ]
        )
        s = score_item(text, keywords)
        scored.append((s, f))

    filtered = [f for s, f in scored if s >= min_score]

    # If nothing passes the filter, return original (API-level filter should
    # have been applied; don't lose all data silently).
    return filtered if filtered else files


def filter_gmail_messages(
    messages: list[dict[str, Any]],
    keywords: list[str],
    min_score: float = 0.05,
) -> list[dict[str, Any]]:
    """Filter Gmail messages by relevance.

    Each message is scored based on headers (subject, from) and snippet.
    """
    if not keywords or not messages:
        return messages

    scored: list[tuple[float, dict[str, Any]]] = []
    for msg in messages:
        parts: list[str] = [str(msg.get("snippet") or "")]
        p_obj = msg.get("payload")
        payload = p_obj if isinstance(p_obj, dict) else {}
        h_obj = payload.get("headers")
        headers = h_obj if isinstance(h_obj, list) else []
        for h in headers:
            if isinstance(h, dict) and h.get("name", "").lower() in ("subject", "from"):
                parts.append(str(h.get("value") or ""))
        text = " ".join(parts)
        s = score_item(text, keywords)
        scored.append((s, msg))

    filtered = [m for s, m in scored if s >= min_score]
    return filtered if filtered else messages
