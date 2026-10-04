## 2024-05-24 - Cross-platform path traversal bypass
**Vulnerability:** Path traversal validation using `os.path.isabs` and `os.path.normpath` can be bypassed by using Windows absolute paths on Linux environments.
**Learning:** These OS-specific functions fail to detect cross-platform attacks, enabling read/write outside sandboxes.
**Prevention:** Use cross-platform methods like `pathlib.PureWindowsPath` and `pathlib.PurePosixPath` to validate file paths safely.
