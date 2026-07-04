# Sentinel Journal
## 2025-02-27 - Fix path traversal vulnerability on Windows paths
**Vulnerability:** Path traversal detection logic (`_is_safe_file_path`) used `os.path.isabs()` to check for absolute paths, which fails to correctly identify Windows-style absolute paths (e.g., `C:\Windows\...`) when the application runs in a Linux/Posix environment.
**Learning:** Functions like `os.path.isabs()` and `os.path.normpath()` use the host OS conventions (i.e., `posixpath` on Linux, `ntpath` on Windows). When validating untrusted input that might originate from or mimic a different operating system, relying solely on `os.path` functions can lead to bypasses.
**Prevention:** Always use cross-platform parsing methods, such as checking both `pathlib.PureWindowsPath` and `pathlib.PurePosixPath`, when validating the structure of paths from untrusted sources, to ensure correct detection regardless of the host operating system.
