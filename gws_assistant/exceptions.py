"""Custom exceptions and API error taxonomy for gws_assistant.

Fix #9 — centralised APIErrorType enum + classify_api_error() so that the
reflection loop can branch on error class instead of string-matching.
"""

from __future__ import annotations

import re
from enum import Enum

from .models import ValidationError


class APIErrorType(Enum):
    """Typed taxonomy of Google API errors seen in the wild."""

    INVALID_QUERY = "invalid_query"  # HTTP 400 — malformed q / field value
    AUTH = "auth"  # HTTP 401 / 403 — credential problem
    RATE_LIMIT = "rate_limit"  # HTTP 429 — quota / rate limit
    SERVER = "server"  # HTTP 5xx — transient server error
    NOT_FOUND = "not_found"  # HTTP 404 — resource missing
    UNKNOWN = "unknown"  # Anything else


# Patterns mapped to error types.  Each tuple is (compiled_re, APIErrorType).
_ERROR_PATTERNS: list[tuple[re.Pattern, APIErrorType]] = [
    (re.compile(r"Invalid Value|invalid|bad request|malformed", re.IGNORECASE), APIErrorType.INVALID_QUERY),
    (re.compile(r"401|403|unauthorized|forbidden|invalid_grant|authError", re.IGNORECASE), APIErrorType.AUTH),
    (re.compile(r"429|rateLimitExceeded|userRateLimitExceeded|quota", re.IGNORECASE), APIErrorType.RATE_LIMIT),
    (re.compile(r"5\d\d|backendError|internalError|Service Unavailable", re.IGNORECASE), APIErrorType.SERVER),
    (re.compile(r"404|410|notFound|not found|deleted", re.IGNORECASE), APIErrorType.NOT_FOUND),
]


def classify_api_error(stderr: str, stdout: str) -> APIErrorType:
    """Classify a failed API call into an APIErrorType.

    Checks stderr first (where the Workspace CLI writes error messages), then stdout
    (where the raw JSON error body is printed).
    """
    combined = f"{stderr or ''}\n{stdout or ''}"
    for pattern, error_type in _ERROR_PATTERNS:
        if pattern.search(combined):
            return error_type
    return APIErrorType.UNKNOWN


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class UnsupportedServiceError(ValidationError):
    """Raised when a service has no CLI backing — must be skipped without retry."""


class SafetyBlockedError(Exception):
    """Raised when a destructive action is blocked by the SafetyGuard."""


class SafetyConfirmationRequired(Exception):
    """Raised when a destructive action requires user confirmation (e.g. over Telegram)."""

    def __init__(self, message: str, action_name: str = "", details: str = ""):
        super().__init__(message)
        self.action_name = action_name
        self.details = details


class ToolExecutionError(Exception):
    """Fix #5 — raised when a tool call fails and success=False is returned.

    Carries the APIErrorType so callers can decide retry vs. skip vs. reauth.
    """

    def __init__(self, message: str, error_type: APIErrorType = APIErrorType.UNKNOWN) -> None:
        super().__init__(message)
        self.error_type = error_type


class VerificationError(Exception):
    """Raised when artifact content verification fails after a successful API call."""
