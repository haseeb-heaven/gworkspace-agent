## 2024-09-20 - [Telegram Bot Token Leak via Exception]
**Vulnerability:** The Telegram API bot token was exposed in plain text when `urllib.error.URLError` and other exceptions were printed to the console upon request failure. The token is inherently part of the API URL (e.g. `https://api.telegram.org/bot<token>/sendMessage`).
**Learning:** Exception objects from HTTP clients (like urllib) often capture and embed the request URL in their string representations (e.g. `<urlopen error ...> (URL: ...)` or `HTTP Error 401 ...`). If the URL contains a token or secret, printing the exception directly leaks the credential.
**Prevention:** Always pass HTTP exception objects through `redact_sensitive()` or a similar secret-stripping utility before logging or printing them.
