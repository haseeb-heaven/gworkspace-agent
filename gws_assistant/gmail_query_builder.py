"""Gmail search query sanitizer — Fix #8.

Gmail search syntax is different from Drive: it uses Gmail-specific operators
(from:, to:, subject:, has:, label:, in:, is:, after:, before:, newer_than:).
This module normalises LLM-generated Gmail query strings so they are always
accepted by the Gmail API.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Compiled regexes
# ---------------------------------------------------------------------------

# Known Gmail query operators.
_GMAIL_OPS_RE = re.compile(
    r"\b(from|to|cc|bcc|subject|has|label|in|is|after|before"
    r"|newer_than|older_than|filename|deliveredto|category"
    r"|larger|smaller|rfc822msgid|list)\s*:",
    re.IGNORECASE,
)

# Matches operator:"value" or operator:'value' (value in quotes) — already correct.
_QUOTED_OP_RE = re.compile(
    r"((?:from|to|cc|bcc|subject|has|label|in|is|filename)\s*:)" \
    r"\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)

# Matches operator=value (LLM sometimes uses = instead of :)
_EQ_OP_RE = re.compile(
    r"(from|to|cc|bcc|subject|has|label|in|filename)\s*=\s*"
    r"(?:'([^']+)'|\"([^\"]+)\"|([^'\"\s,)]+))",
    re.IGNORECASE,
)

# Bare double-quoted token at start/end of query (non-operator context).
_BARE_DQUOTE_RE = re.compile(r'^"([^"]+)"$')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _escape_gmail_value(value: str) -> str:
    """Strip characters that break Gmail query syntax."""
    return value.replace('"', "").strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sanitize_gmail_query(raw: str) -> str:
    """Normalise an LLM-generated Gmail search query.

    Handles:
      from=user@example.com           -> from:user@example.com
      subject='foo bar'               -> subject:foo bar
      "some topic"                    -> subject:\"some topic\" OR body:\"some topic\"
      foo bar (bare text, no op)      -> foo bar  (Gmail accepts bare text natively)

    Gmail's own query parser is lenient about bare text, so we only fix
    structural issues (= vs :, stray quote wrappers) and leave valid
    expressions untouched.
    """
    q = raw.strip()
    if not q:
        return q

    # Step 1 — fix operator=value -> operator:value
    def _fix_eq(m: re.Match) -> str:
        op = m.group(1).lower()
        val = next(g for g in m.groups()[1:] if g is not None)
        val = _escape_gmail_value(val)
        if " " in val:
            return f'{op}:"{val}"'
        return f"{op}:{val}"

    q = _EQ_OP_RE.sub(_fix_eq, q)

    # Step 2 — strip redundant quotes from operator:"value" -> operator:value
    # (Gmail handles unquoted values fine; quoted values with spaces are OK too)
    def _fix_quoted_op(m: re.Match) -> str:
        op = m.group(1)  # e.g. "subject:"
        val = m.group(2).strip()  # strip inner whitespace only
        # Keep quotes when value contains spaces (Gmail needs them).
        if " " in val:
            return f'{op}"{val}"'
        return f"{op}{val}"

    q = _QUOTED_OP_RE.sub(_fix_quoted_op, q)

    # Step 3 — if the entire query is a bare double-quoted string with no
    # Gmail operator, expand to subject OR body search.
    dq = _BARE_DQUOTE_RE.match(q)
    if dq and not _GMAIL_OPS_RE.search(q):
        inner = _escape_gmail_value(dq.group(1))
        q = f'subject:"{inner}" OR "{inner}"'

    return q
