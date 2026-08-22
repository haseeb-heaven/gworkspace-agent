## 2024-10-24 - Secret Leakage via URL Exceptions
**Vulnerability:** Telegram API token was being leaked to logs when `urllib.error.URLError` occurred, because the token is embedded in the requested URL (which is printed in the exception message).
**Learning:** Standard HTTP/URL exception messages often include the requested URL. If the URL contains sensitive tokens or credentials in the path, simply printing the exception exposes those secrets.
**Prevention:** Always wrap HTTP/URL exception objects with a redaction function (like `redact_sensitive()`) before printing or logging them to prevent embedded secrets from leaking.
