## 2024-05-24 - Exception Logging Secret Leak
**Vulnerability:** Telegram bot token was potentially leaked when `urllib.error.URLError` and other exceptions were printed directly, as HTTP error messages can contain the requested URL (which includes the token).
**Learning:** Exceptions raised by network libraries (like `urllib` or `requests`) often include the full URL or request details in their string representation, bypassing normal application-level logging redaction if not explicitly handled.
**Prevention:** Always wrap exception objects with `redact_sensitive()` before printing or logging them when dealing with URLs that contain embedded credentials.
