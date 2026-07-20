## 2024-07-20 - Exception Logging Exposes Sensitive Tokens
**Vulnerability:** URLError logging in Telegram notification tools did not pass exceptions through the `redact_sensitive()` function, potentially writing secret API tokens into plaintext console output if network requests failed.
**Learning:** URL exception types like `URLError` or `HTTPError` include the original requested URL in their `.reason` and `str()` representations. If the URL contains an embedded secret (e.g. `https://api.telegram.org/bot<TOKEN>/sendMessage`), printing the exception leaks the secret.
**Prevention:** Wrap exception objects with the `redact_sensitive()` string scrubbing function before passing them to loggers or `print()`.
