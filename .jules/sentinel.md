## 2024-11-20 - Token Leakage in Exception Logs
**Vulnerability:** The Telegram bot token is embedded in the URL. If the API request fails, printing the exception (e.g. `urllib.error.URLError`) exposes the full URL, leaking the bot token in plain text in the system logs.
**Learning:** The URL-based authentication mechanisms inherently embed secrets into request metadata. Default exception string representations for network libraries often include the attempted URL.
**Prevention:** Always wrap exception objects with a secret redaction function (like `redact_sensitive()`) before printing or logging them when the request involves URLs with embedded tokens.
