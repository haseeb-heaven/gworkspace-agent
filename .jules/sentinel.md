## 2024-07-23 - Prevent sensitive data leakage in urllib exception handling
**Vulnerability:** Unhandled `urllib.error.URLError` and generic `Exception` blocks in `gws_assistant/tools/telegram.py` cast the exception object to a string when printing it. If an HTTP error occurs (e.g., HTTP 404 with a token in the URL path, or HTTP 401 with a sensitive URL), the string representation of the exception can leak the requested URL (and the token within it) to logs.
**Learning:** Implicit string conversions of network exceptions can leak request URLs containing tokens.
**Prevention:** Always wrap the exception object with `redact_sensitive(e)` before printing/logging it to ensure any embedded tokens are redacted.
