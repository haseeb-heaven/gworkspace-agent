## 2025-02-14 - Redact sensitive data from exceptions in Telegram

**Vulnerability:** URL exceptions in `urllib.error.URLError` and generic exceptions are logged/printed unredacted when a request fails.
**Learning:** Exception messages can include the URL or payload if they originate from networking libraries or unhandled application states. For Telegram, the token is embedded in the URL `https://api.telegram.org/bot<TOKEN>/sendMessage`. If an error occurs, the URL (with the token) might be printed to stdout.
**Prevention:** Always wrap the exception object with `redact_sensitive()` before printing or logging it to prevent leaking secret tokens embedded in URLs.
