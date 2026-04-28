"""Drive API v3 query sanitizer — extracted from planner.py.

All Drive-specific regex patterns and the _sanitize_drive_query() function
live here so that planner.py stays focused on command construction.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Compiled regexes
# ---------------------------------------------------------------------------

# Fix #1 — Matches an ALREADY-VALID Drive API v3 operator clause.
# Clauses that match are passed through UNTOUCHED to prevent double-transform.
_DRIVE_VALID_CLAUSE_RE = re.compile(
    r"""^\s*(?:
        (?:name|fullText)\s+contains\s+'[^']*'         # name contains '...'
      | mimeType\s*=\s*'[^']*'                          # mimeType='...'
      | (?:trashed|starred|sharedWithMe)\s*=\s*(?:true|false)
      | (?:parents|in)\s+in\s+'[^']*'
      | (?:modifiedTime|createdTime|viewedByMeTime)\s*[<>=!]+\s*\S+
    )\s*$""",
    re.IGNORECASE | re.VERBOSE,
)

# Fix #2 — Matches every malformed mimeType variant the LLM produces.
# Strips surrounding whitespace and quotes from the captured value.
_MIME_EQ_RE = re.compile(
    r"""mimeType\s*[=:]\s*["']?\s*([^"'\s,)]+)\s*["']?""",
    re.IGNORECASE,
)

# Logical conjunction tokens used as split boundaries.
_CONJUNCTION_RE = re.compile(r"\b(and|or)\b", re.IGNORECASE)

# Fix #5 — Detects whether a raw clause contains any Drive operator keyword.
_DRIVE_OPS_RE = re.compile(
    r"\b(contains|and|or|not|in|parents|mimeType|name|fullText"
    r"|trashed|starred|sharedWithMe|modifiedTime|createdTime"
    r"|viewedByMeTime|quotaBytesUsed|properties|appProperties|visibility)\b",
    re.IGNORECASE,
)

# Bare double-quoted token with no operator, e.g. "CcaaS - AI Product"
_BARE_DQUOTE_RE = re.compile(r'^"([^"]+)"$')

# LLM-generated name=/name: prefix — e.g. name='CcaaS', name="foo", name:bar
# Captured group 1 is the raw value (inner quotes already stripped by the regex).
_NAME_EQ_RE = re.compile(
    r"""^name\s*[=:]\s*['"]?(.+?)['"]?\s*$""",
    re.IGNORECASE,
)

RE_DRIVE_OP_MATCH = re.compile(r"^(name|fullText)\s+contains\s+['\"]?(.+?)['\"]?$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _escape(value: str) -> str:
    """Fix #8 — escape single quotes inside a Drive query value."""
    # Also strip backslashes that would break the query string.
    return value.replace("\\", "").replace("'", "\\'")


def _is_valid_clause(clause: str) -> bool:
    """Fix #6 — return True if clause already is a valid Drive API v3 expression."""
    return bool(_DRIVE_VALID_CLAUSE_RE.match(clause.strip()))


def _tokenize_raw_query(raw: str) -> tuple[list[str], list[str]]:
    """Fix #3 — token-based split that respects quoted substrings.

    Splits only on 'and'/'or' that appear OUTSIDE single/double quotes.
    Returns (clauses, conjunctions) as parallel lists:
      len(conjunctions) == len(clauses) - 1
    """
    parts: list[str] = []
    conjunctions: list[str] = []
    buffer = ""
    i = 0
    in_single = False
    in_double = False

    while i < len(raw):
        ch = raw[i]
        if ch == "'" and not in_double:
            in_single = not in_single
            buffer += ch
        elif ch == '"' and not in_single:
            in_double = not in_double
            buffer += ch
        elif not in_single and not in_double:
            m = _CONJUNCTION_RE.match(raw, i)
            if m:
                if buffer.strip():
                    parts.append(buffer.strip())
                conjunctions.append(m.group(1).lower())
                buffer = ""
                i = m.end()
                continue
            else:
                buffer += ch
        else:
            buffer += ch
        i += 1

    if buffer.strip():
        parts.append(buffer.strip())
    return parts, conjunctions


def _classify_and_fix_clause(clause: str) -> list[str]:
    """Fix #4 & #5 — classify one raw clause; may return multiple valid Drive clauses.

    A single LLM clause can contain multiple semantic components with no
    logical operator, e.g.:
        \"CcaaS - AI Product\" mimeType=\"application/vnd.google-apps.document\"
    These are split and each component is returned separately; the caller
    injects 'and' between them (Fix #4).
    """
    clause = clause.strip()
    if not clause:
        return []

    # Fix #6 — already valid, pass through untouched.
    if _is_valid_clause(clause):
        return [clause]

    # Fix #2 — extract and reformat every mimeType component.
    mime_clauses: list[str] = []

    def _collect_mime(m: re.Match) -> str:
        value = m.group(1).strip().strip("\"'")
        mime_clauses.append(f"mimeType='{_escape(value)}'")
        return ""

    remainder = _MIME_EQ_RE.sub(_collect_mime, clause).strip()

    # Process whatever text remains after stripping mimeType components.
    text_clauses: list[str] = []
    if remainder:
        # Strip wrapping double-quotes from bare quoted tokens.
        dq = _BARE_DQUOTE_RE.match(remainder)
        if dq:
            remainder = dq.group(1).strip()

        # NEW FIX — strip LLM-generated name=/name: prefix BEFORE the
        # _DRIVE_OPS_RE check fires.
        name_eq = _NAME_EQ_RE.match(remainder)
        if name_eq:
            remainder = name_eq.group(1).strip().strip("'\"")

        # Fix: if it's already an operator clause but missing quotes, fix the quotes
        # to avoid it being re-wrapped in name contains.
        op_match = RE_DRIVE_OP_MATCH.match(remainder)
        if op_match:
            field, val = op_match.group(1), op_match.group(2).strip()
            text_clauses.append(f"{field} contains '{_escape(val)}'")
            remainder = ""

        # Fix #5 — if remainder has no Drive operator it is bare text.
        if remainder:
            if not _DRIVE_OPS_RE.search(remainder):
                safe = _escape(remainder.strip("\"' "))
                if safe:
                    text_clauses.append(f"name contains '{safe}'")
            else:
                # Remainder already has an operator — validate and keep.
                if _is_valid_clause(remainder):
                    text_clauses.append(remainder)
                else:
                    # Fix #6 — avoid re-wrapping an already-operator clause.
                    safe = _escape(remainder.strip("\"' "))
                    if safe:
                        text_clauses.append(f"name contains '{safe}'")

    return text_clauses + mime_clauses


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sanitize_drive_query(raw: str) -> str:
    """Normalise an LLM-generated Drive query string to valid Drive API v3 syntax.

    All observed failure modes are handled:
      \"CcaaS - AI Product\" mimeType=\"application/vnd.google-apps.document\"
      CcaaS - AI Product mimeType:application/vnd.google-apps.document
      CcaaS - AI Product
      name='CcaaS - AI Product'
      name='CcaaS - AI Product' mimeType='application/vnd.google-apps.document'

    All become:
      name contains 'CcaaS - AI Product' and mimeType='application/vnd.google-apps.document'
    """
    q = raw.strip()
    if not q:
        return q

    # Fix #3 — token-based split preserving quoted content.
    raw_clauses, conjunctions = _tokenize_raw_query(q)

    # Fix #4/#5 — each raw clause may expand to multiple valid clauses.
    fixed_groups: list[list[str]] = [_classify_and_fix_clause(c) for c in raw_clauses]

    # Assemble: inject 'and' between sub-clauses within the same group (Fix #4),
    # preserve original conjunctions between groups.
    all_clauses: list[str] = []
    all_conjs: list[str] = []

    for g_idx, group in enumerate(fixed_groups):
        for c_idx, clause in enumerate(group):
            all_clauses.append(clause)
            if c_idx < len(group) - 1:
                all_conjs.append("and")
        if g_idx < len(conjunctions):
            all_conjs.append(conjunctions[g_idx])

    if not all_clauses:
        safe = _escape(q.strip("\"' "))
        return f"name contains '{safe}'"

    result_parts: list[str] = []
    for idx, clause in enumerate(all_clauses):
        result_parts.append(clause)
        if idx < len(all_conjs):
            result_parts.append(all_conjs[idx])
    result = " ".join(result_parts).strip()

    # Fix #7 — final fallback ONLY when no Drive operator exists at all.
    if result and not _DRIVE_OPS_RE.search(result):
        safe = _escape(result.strip("\"' "))
        result = f"name contains '{safe}'"

    return result


# Backward-compat alias used by planner.py
_sanitize_drive_query = sanitize_drive_query
