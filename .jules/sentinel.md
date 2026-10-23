## 2024-05-24 - Cross-platform path traversal bypass
**Vulnerability:** Path traversal validation using `os.path.isabs` and `os.path.normpath` can be bypassed by using Windows absolute paths on Linux environments.
**Learning:** These OS-specific functions fail to detect cross-platform attacks, enabling read/write outside sandboxes.
**Prevention:** Use cross-platform methods like `pathlib.PureWindowsPath` and `pathlib.PurePosixPath` to validate file paths safely.
## 2025-01-01 - Prevent Telegram Bot Token Leak in URLs
**Vulnerability:** Telegram Bot Token leaked in URL strings during URLErrors due to restrictive regex word boundaries (`\b`) failing to match tokens prefixed with `bot`.
**Learning:** Regular expression boundaries (`\b`) depend on non-word characters. Since the URL format is `.../bot<token>...`, the transition from `t` to the first digit of the token is not a word boundary, preventing the token from being redacted in URLs.
**Prevention:** Remove restrictive `\b` boundaries or correctly account for string prefixes (like `bot`) when writing redaction regexes for tokens that appear embedded in larger strings or URLs.
