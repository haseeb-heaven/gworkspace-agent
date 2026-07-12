## 2025-02-24 - Prevent Secret Leakage in Exception Messages
**Vulnerability:** Telegram API token could be leaked in stdout when a `urllib.error.URLError` or general `Exception` is caught and printed without redaction.
**Learning:** URLs embedded within exception objects (like HTTPError) can expose credentials when cast to strings.
**Prevention:** Always wrap exception objects with `redact_sensitive()` before printing or logging them.
