## 2025-05-18 - Fix sensitive token leak in URL exceptions
**Vulnerability:** When the Telegram API returns an error (e.g. `urllib.error.URLError`), the exception string might contain the requested URL, which embeds the `TELEGRAM_BOT_TOKEN`. Printing it raw leaks the secret to the console/logs.
**Learning:** Even built-in exception types can leak sensitive information if they contain the URL, requiring explicit redaction before logging.
**Prevention:** Always wrap exception variables with a redaction function (like `redact_sensitive(e)`) when catching errors that might contain URLs or other secrets, especially around network requests.
