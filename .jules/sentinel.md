## 2024-06-25 - Prevent Secret Leakage in URL Exception Logging
**Vulnerability:** URL exceptions (`urllib.error.URLError` and general `Exception`) during Telegram API requests were printed directly to the console without redaction, exposing the Telegram bot token embedded in the API URL.
**Learning:** When logging errors related to HTTP/URL requests, the exception object can contain the raw URL, which might embed authentication tokens in its path (e.g., `https://api.telegram.org/bot<TOKEN>/sendMessage`). Always redact exception output before logging.
**Prevention:** Wrap all exception logging with a redaction utility (like `redact_sensitive()`) to prevent exposing embedded secrets in stack traces or console output.
