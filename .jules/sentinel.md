## 2024-07-17 - [URL Exception Token Leakage]
**Vulnerability:** Telegram API bot token leaked in urllib.error.URLError string representation.
**Learning:** Exception objects containing HTTP/URL errors can embed sensitive tokens within the URL string they hold.
**Prevention:** Always wrap HTTP/URL exception objects with `redact_sensitive()` before printing or logging.
