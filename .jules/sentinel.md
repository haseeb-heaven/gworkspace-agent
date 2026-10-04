## 2024-10-02 - Sentinel: [CRITICAL] Prevent Telegram Token Leakage in Error Logs
**Vulnerability:** The Telegram API key was embedded in the URL and leaked in error logs during `urllib.error.URLError` exceptions because the exception was printed directly.
**Learning:** Hardcoded/templated API keys in request URLs can be exposed by default exception string representations if HTTP clients include the requested URL in the error message.
**Prevention:** Always use the application's `redact_sensitive()` function to sanitize all URL-related exception strings and logs before they are printed or sent anywhere.
