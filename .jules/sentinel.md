## 2024-05-24 - Cross-platform path traversal bypass
**Vulnerability:** Path traversal validation using `os.path.isabs` and `os.path.normpath` can be bypassed by using Windows absolute paths on Linux environments.
**Learning:** These OS-specific functions fail to detect cross-platform attacks, enabling read/write outside sandboxes.
**Prevention:** Use cross-platform methods like `pathlib.PureWindowsPath` and `pathlib.PurePosixPath` to validate file paths safely.
## 2025-02-14 - Binding to All Interfaces
**Vulnerability:** Gradio server defaults to binding to all interfaces (0.0.0.0).
**Learning:** Defaulting to 0.0.0.0 exposes the development server to the local network and potentially the internet depending on firewall rules.
**Prevention:** Default to localhost (127.0.0.1) for internal servers and only bind to 0.0.0.0 if explicitly configured to do so for a production environment.
