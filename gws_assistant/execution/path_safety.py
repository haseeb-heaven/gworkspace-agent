r"""Path validation helpers for sandboxed file operations.

Centralises the logic for verifying that a file path produced by a Drive
``export_file`` / ``get_file`` task lives inside one of the directories that
the agent is allowed to read.

The historical implementation used ``str(Path(p).resolve()).startswith(...)``
which failed on Windows extended-length paths (``\\?\D:\Code\...``) and on
paths containing differing slash conventions. This module fixes that with:

* Stripping the ``\\?\`` / ``\\?\UNC\`` prefixes that ``Path.resolve()`` may
  produce on Windows.
* Comparing canonicalised, normalised paths via :func:`os.path.normcase` /
  :func:`os.path.commonpath` so a candidate inside the allowed directory is
  accepted regardless of slash direction or case sensitivity.
* Reading the ``DOWNLOADS_DIR`` and ``SCRATCH_DIR`` environment variables so
  operators can relocate the sandbox without code changes.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Sequence

# Default sandbox directories (relative to the current working directory).
DEFAULT_DOWNLOADS_DIR = "downloads"
DEFAULT_SCRATCH_DIR = "scratch"

# Windows extended-length path prefixes that ``Path.resolve()`` may emit.
_WIN_EXTENDED_PREFIXES: tuple[str, ...] = ("\\\\?\\UNC\\", "\\\\?\\", "//?/UNC/", "//?/")


def _strip_extended_prefix(path: str) -> str:
    r"""Remove the Windows extended-length path prefix if present.

    ``\\?\D:\foo`` becomes ``D:\foo`` and ``\\?\UNC\srv\share`` becomes
    ``\\srv\share`` -- preserving UNC semantics where applicable.
    """
    for prefix in _WIN_EXTENDED_PREFIXES:
        if path.startswith(prefix):
            stripped = path[len(prefix):]
            if "UNC" in prefix:
                # Re-attach the UNC double-slash so the path remains a valid
                # network share locator after the extended prefix is removed.
                return "\\\\" + stripped
            return stripped
    return path


def _canonicalise(path: str | os.PathLike[str]) -> str:
    """Return a normalised, absolute string representation of *path*.

    The result has the extended-length prefix stripped, all components
    resolved (when possible), and casing/separators normalised so that two
    canonicalised paths can be safely compared with simple string ops or
    :func:`os.path.commonpath`.
    """
    raw = os.fspath(path)
    raw = _strip_extended_prefix(raw)
    try:
        # ``Path.resolve(strict=False)`` follows symlinks (where they exist)
        # and converts to an absolute path even when the target is missing.
        resolved = Path(raw).resolve(strict=False)
    except (OSError, RuntimeError):
        resolved = Path(os.path.abspath(raw))
    return os.path.normcase(_strip_extended_prefix(str(resolved)))


def get_allowed_export_dirs(extra_dirs: Sequence[str | os.PathLike[str]] | None = None) -> list[str]:
    """Return the canonical directories that exported files may live in.

    Reads ``DOWNLOADS_DIR`` and ``SCRATCH_DIR`` from the environment, falling
    back to the project-relative ``downloads`` and ``scratch`` folders. Any
    *extra_dirs* supplied by the caller are appended.
    """
    candidates: list[str] = [
        os.getenv("DOWNLOADS_DIR") or DEFAULT_DOWNLOADS_DIR,
        os.getenv("SCRATCH_DIR") or DEFAULT_SCRATCH_DIR,
    ]
    if extra_dirs:
        candidates.extend(os.fspath(d) for d in extra_dirs)

    seen: set[str] = set()
    canonical: list[str] = []
    for c in candidates:
        if not c:
            continue
        canon = _canonicalise(c)
        if canon not in seen:
            seen.add(canon)
            canonical.append(canon)
    return canonical


def is_within_allowed_dir(
    candidate: str | os.PathLike[str],
    allowed_dirs: Iterable[str | os.PathLike[str]] | None = None,
) -> bool:
    r"""Return ``True`` if *candidate* resolves inside one of *allowed_dirs*.

    Works correctly for Windows extended-length paths (``\\?\D:\...``),
    cross-platform slash conventions, and case-insensitive filesystems. When
    *allowed_dirs* is omitted the directories returned by
    :func:`get_allowed_export_dirs` are used.
    """
    if not candidate:
        return False
    allowed = (
        [_canonicalise(d) for d in allowed_dirs]
        if allowed_dirs is not None
        else get_allowed_export_dirs()
    )
    cand_canon = _canonicalise(candidate)

    for base in allowed:
        if not base:
            continue
        if cand_canon == base:
            return True
        try:
            common = os.path.commonpath([cand_canon, base])
        except ValueError:
            # Different drives / mounts — definitely not inside *base*.
            continue
        if os.path.normcase(common) == base:
            return True
    return False


__all__ = [
    "DEFAULT_DOWNLOADS_DIR",
    "DEFAULT_SCRATCH_DIR",
    "get_allowed_export_dirs",
    "is_within_allowed_dir",
]
