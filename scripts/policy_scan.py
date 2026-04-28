from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCAN_PATHS = [
    ROOT / "run_live_scenarios.py",
    ROOT / "src",
    ROOT / "scripts",
    ROOT / "framework",
    ROOT / ".agent" / "skills" / "telegram-update" / "scripts",
]

EXCLUDED_NAMES = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
EXAMPLE_DOMAINS = ("example.com", "example.test", "company.com")

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
SECRET_RE = re.compile(r"\b(?:sk|or|m0)-[A-Za-z0-9._-]{16,}\b")
WINDOWS_PYTHON_RE = re.compile(r"[A-Za-z]:\\[^\"'\s]+\\python\.exe", re.IGNORECASE)
GWS_EXE_RE = re.compile(r"gws\.exe", re.IGNORECASE)
NON_FREE_MODEL_RE = re.compile(
    r"(?:gpt-4|gpt-5|openai/gpt|gpt-4o|claude-[A-Za-z0-9.-]+)(?![^\"'\s]*:free)", re.IGNORECASE
)

ALLOW_NON_FREE_MODEL_FILES = {
    "tests",
}


def _iter_files() -> list[Path]:
    files: list[Path] = []
    for path in SCAN_PATHS:
        if path.is_file():
            files.append(path)
            continue
        if not path.exists():
            continue
        for item in path.rglob("*"):
            if any(part in EXCLUDED_NAMES for part in item.parts):
                continue
            if item.is_file() and item.suffix in {".py", ".yml", ".yaml", ".toml", ".md", ".txt"}:
                files.append(item)
    return sorted(set(files))


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def scan() -> list[str]:
    findings: list[str] = []
    for path in _iter_files():
        rel = _relative(path)
        if rel == "scripts/policy_scan.py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in EMAIL_RE.finditer(line):
                if match.group(1).lower() not in EXAMPLE_DOMAINS:
                    findings.append(f"{rel}:{line_number}: hardcoded email address")
            if WINDOWS_PYTHON_RE.search(line):
                findings.append(f"{rel}:{line_number}: hardcoded Windows python.exe path")
            if GWS_EXE_RE.search(line):
                findings.append(f"{rel}:{line_number}: hardcoded gws.exe reference")
            if SECRET_RE.search(line):
                findings.append(f"{rel}:{line_number}: secret-like literal")
            if not any(rel.startswith(prefix) for prefix in ALLOW_NON_FREE_MODEL_FILES):
                if NON_FREE_MODEL_RE.search(line):
                    findings.append(f"{rel}:{line_number}: non-free model literal")
    return findings


def main() -> int:
    findings = scan()
    if findings:
        print("Policy scan failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("Policy scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
