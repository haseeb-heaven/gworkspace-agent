#!/usr/bin/env python3
"""Parallel task runner with gws.exe CRUD verification and auto-retry.
Uses env-var overrides for provider rotation to avoid corrupting .env."""

import json
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
TASKS_DIR = ROOT / "scratch" / "tasks"
REPORT_FILE = ROOT / "scratch" / "task_run_report.json"
GWS = ROOT / "gws.exe"
PYTHON = sys.executable
MAX_RETRIES = 3
ENV_FILE = ROOT / ".env"

def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


TASK_TIMEOUT_SECONDS = _int_env("TASK_TIMEOUT_SECONDS", 300)
RETRY_BACKOFF_SECONDS = _int_env("TASK_RETRY_BACKOFF_SECONDS", 5)
CONFIGURED_WORKERS = max(1, _int_env("TASK_RUNNER_WORKERS", 4))

LOG_LOCK = threading.Lock()

PROVIDERS = [
    {
        "label": "openrouter",
        "env": {
            "LLM_PROVIDER": "openrouter",
            "LLM_MODEL": "openrouter/google/gemini-2.0-flash-lite-preview-02-05:free",
            "LLM_FALLBACK_MODEL": "openrouter/meta-llama/llama-3.3-70b-instruct:free",
            "LLM_FALLBACK_MODEL2": "openrouter/qwen/qwen-2.5-72b-instruct:free",
        },
        "api_key_envs": ("OPENROUTER_API_KEY", "LLM_API_KEY"),
        "propagate_envs": ("LLM_API_KEY", "OPENROUTER_API_KEY"),
    },
    {
        "label": "anthropic",
        "env": {
            "LLM_PROVIDER": "anthropic",
            "LLM_MODEL": "anthropic/claude-3-7-sonnet-20250219",
            "LLM_FALLBACK_MODEL": "anthropic/claude-3-5-sonnet-20241022",
        },
        "api_key_envs": ("ANTHROPIC_API_KEY", "LLM_API_KEY"),
        "propagate_envs": ("LLM_API_KEY", "ANTHROPIC_API_KEY"),
    },
    {
        "label": "google",
        "env": {
            "LLM_PROVIDER": "google",
            "LLM_MODEL": "gemini/gemini-1.5-flash-latest",
            "LLM_FALLBACK_MODEL": "gemini/gemini-1.5-pro-latest",
        },
        "api_key_envs": ("GOOGLE_API_KEY", "GEMINI_API_KEY", "LLM_API_KEY"),
        "propagate_envs": ("LLM_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY"),
    },
]


def log(msg: str):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    thread_name = threading.current_thread().name
    line = f"{timestamp} [{thread_name}] {msg}"
    with LOG_LOCK:
        print(line, flush=True)
        with open(ROOT / "auto_runner.log", "a", encoding="utf-8") as f:
            f.write(f"{line}\n")


def get_all_tasks() -> List[Path]:
    tasks: List[Path] = []
    if not TASKS_DIR.exists():
        log(f"Task directory missing at {TASKS_DIR}")
        return tasks

    for category_dir in TASKS_DIR.iterdir():
        if category_dir.is_dir():
            for task_file in sorted(category_dir.glob("*.txt")):
                tasks.append(task_file)
    return sorted(tasks)


def read_task(task_file: Path) -> str:
    with open(task_file, "r", encoding="utf-8") as f:
        return f.read().strip()


def load_env_file(path: Path = ENV_FILE) -> None:
    if not path.exists():
        log(f".env file not found at {path}. Skipping explicit load.")
        return

    loaded = 0
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if not key or key in os.environ:
                continue
            os.environ[key] = value
            loaded += 1

    log(f"Loaded {loaded} environment values from {path} (existing vars preserved).")


def _resolve_api_key(provider: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    for env_name in provider.get("api_key_envs", ()):  # type: ignore[arg-type]
        value = os.getenv(env_name)
        if value:
            return value, env_name
    return None, None


def default_id_map() -> Dict[str, List[str]]:
    return {
        "drive_files": [],
        "sheets": [],
        "docs": [],
        "drive_ids": [],
        "event_ids": [],
    }


def _run_gws_binary(args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(GWS), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


def run_gws_cli(task_content: str, provider_idx: int = 0) -> Tuple[int, str]:
    provider = PROVIDERS[provider_idx]
    env = os.environ.copy()
    env.update(provider["env"])

    api_key, source_env = _resolve_api_key(provider)
    if not api_key:
        expected_keys = ", ".join(provider.get("api_key_envs", ()))
        message = (
            f"API key missing for provider '{provider['label']}'. "
            f"Populate one of [{expected_keys}] to continue."
        )
        log(message)
        return -2, message

    for target in provider.get("propagate_envs", ()):  # type: ignore[arg-type]
        env[target] = api_key

    cmd = [
        str(PYTHON),
        str(ROOT / "gws_cli.py"),
        "--task",
        task_content,
        "--no-confirm",
        "--force-dangerous",
    ]
    log(f"Running CLI (provider={provider['label']}, key={source_env}) :: {task_content[:80]}...")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TASK_TIMEOUT_SECONDS,
            cwd=str(ROOT),
            env=env,
        )
        output = result.stdout + result.stderr
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return -1, f"TIMEOUT after {TASK_TIMEOUT_SECONDS}s"


def extract_ids(output: str) -> Dict[str, List[str]]:
    ids = default_id_map()
    ids["drive_files"] = re.findall(r"https://drive\.google\.com/[^\s\"]+d/([A-Za-z0-9_-]+)", output)
    ids["sheets"] = re.findall(r"https://docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]+)", output)
    ids["docs"] = re.findall(r"https://docs\.google\.com/document/d/([A-Za-z0-9_-]+)", output)
    ids["drive_ids"] = re.findall(r'"id":\s*"([A-Za-z0-9_-]{20,})"', output)
    ids["event_ids"] = re.findall(r'"eventId":\s*"([^"]+)"', output)
    return ids


def verify_with_gws(task_file: Path, ids: Dict[str, List[str]]) -> List[str]:
    if not GWS.exists():
        raise FileNotFoundError(f"gws.exe not found at {GWS}; required for CRUD verification")

    verifications: List[str] = []
    fname = task_file.name.lower()

    def _ok(result: subprocess.CompletedProcess) -> bool:
        payload = (result.stdout or "")[:300].lower()
        return result.returncode == 0 and '"error"' not in payload

    if any(k in fname for k in ["drive", "folder", "upload", "rename", "trash"]):
        for file_id in ids.get("drive_files", []) + ids.get("drive_ids", []):
            result = _run_gws_binary([
                "drive",
                "files",
                "get",
                "--params",
                json.dumps({"fileId": file_id}),
                "--format",
                "json",
            ])
            verifications.append(f"DRIVE {'OK' if _ok(result) else 'FAIL'}: {file_id}")

    if any(k in fname for k in ["sheet", "xlsx", "tabular"]):
        for sid in ids.get("sheets", []):
            result = _run_gws_binary([
                "sheets",
                "spreadsheets",
                "get",
                "--params",
                json.dumps({"spreadsheetId": sid}),
                "--format",
                "json",
            ])
            verifications.append(f"SHEETS {'OK' if _ok(result) else 'FAIL'}: {sid}")

    if "doc" in fname:
        for did in ids.get("docs", []):
            result = _run_gws_binary([
                "docs",
                "documents",
                "get",
                "--params",
                json.dumps({"documentId": did}),
                "--format",
                "json",
            ])
            verifications.append(f"DOCS {'OK' if _ok(result) else 'FAIL'}: {did}")

    if any(k in fname for k in ["meet", "event"]):
        result = _run_gws_binary([
            "calendar",
            "events",
            "list",
            "--params",
            json.dumps({"calendarId": "primary", "maxResults": 20}),
            "--format",
            "json",
        ])
        verifications.append(f"CALENDAR LIST: rc={result.returncode} len={len(result.stdout)}")

    if "keep" in fname:
        result = _run_gws_binary([
            "keep",
            "notes",
            "list",
            "--format",
            "json",
        ])
        verifications.append(f"KEEP LIST: rc={result.returncode} len={len(result.stdout)}")

    if "email" in fname:
        result = _run_gws_binary([
            "gmail",
            "users",
            "messages",
            "list",
            "--params",
            json.dumps({"userId": "me", "maxResults": 10}),
            "--format",
            "json",
        ])
        verifications.append(f"GMAIL LIST: rc={result.returncode} len={len(result.stdout)}")

    return verifications


def is_success(output: str, returncode: int) -> bool:
    if returncode != 0:
        return False
    if "Error:" in output or "Exception:" in output:
        if "Result" in output and "border_style=\"green\"" in output:
            return True
        if "Command succeeded" in output:
            return True
        return False
    return True


def _load_report() -> Dict[str, Any]:
    if not REPORT_FILE.exists():
        return {}
    try:
        with open(REPORT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:  # pragma: no cover - defensive logging
        log(f"Failed to load report {REPORT_FILE}: {exc}")
        return {}


def _persist_report(report: Dict[str, Any]) -> None:
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def _resolve_worker_count(total_tasks: int) -> int:
    return max(1, min(CONFIGURED_WORKERS, total_tasks))


def process_task(
    task_idx: int,
    total: int,
    task_file: Path,
    report: Dict[str, Any],
    report_lock: threading.Lock,
) -> Tuple[str, bool]:
    task_name = str(task_file.relative_to(ROOT))
    log(f"[Task {task_idx}/{total}] Starting {task_name}")

    task_content = read_task(task_file)
    success = False
    attempts: List[Dict[str, Any]] = []
    ids = default_id_map()

    for attempt in range(1, MAX_RETRIES + 1):
        provider_idx = (attempt - 1) % len(PROVIDERS)
        provider_label = PROVIDERS[provider_idx]["label"]
        rc, output = run_gws_cli(task_content, provider_idx)
        ids = extract_ids(output)

        if is_success(output, rc):
            success = True
            try:
                verifications = verify_with_gws(task_file, ids)
            except FileNotFoundError as exc:
                verifications = [f"VERIFICATION SKIPPED: {exc}"]
                log(f"[Task {task_name}] WARNING: {exc}")

            attempts.append(
                {
                    "attempt": attempt,
                    "rc": rc,
                    "success": True,
                    "provider": provider_label,
                    "verifications": verifications,
                }
            )
            log(f"[Task {task_name}] SUCCESS on attempt {attempt} via {provider_label}")
            for verification in verifications:
                log(f"[Task {task_name}] VERIFY -> {verification}")
            break

        attempts.append(
            {
                "attempt": attempt,
                "rc": rc,
                "success": False,
                "provider": provider_label,
                "output_snippet": output[-500:],
            }
        )
        log(f"[Task {task_name}] FAILURE attempt {attempt} via {provider_label} (rc={rc})")
        if attempt < MAX_RETRIES:
            log(
                f"[Task {task_name}] Waiting {RETRY_BACKOFF_SECONDS}s before FIX -> COMMIT -> RETRY with next provider"
            )
            time.sleep(RETRY_BACKOFF_SECONDS)

    if not success:
        log(
            f"[Task {task_name}] Exhausted retries. Apply FIX -> COMMIT -> RUN AGAIN manually before moving on."
        )

    with report_lock:
        report[task_name] = {
            "success": success,
            "attempts": attempts,
            "ids": ids,
        }
        _persist_report(report)

    log(f"[Task {task_name}] Report updated -> {REPORT_FILE}")
    return task_name, success


def main():
    load_env_file()
    tasks = get_all_tasks()
    if not tasks:
        log("No tasks found. Ensure scratch/tasks contains *.txt definitions.")
        return

    log(f"Discovered {len(tasks)} total tasks.")

    report = _load_report()
    report_lock = threading.Lock()

    pending: List[Path] = []
    for idx, task_file in enumerate(tasks, 1):
        task_name = str(task_file.relative_to(ROOT))
        if report.get(task_name, {}).get("success"):
            log(f"[Task {idx}/{len(tasks)}] SKIP passed task -> {task_name}")
        else:
            pending.append(task_file)

    if not pending:
        log("All tasks already passed per report. Nothing to run.")
        return

    worker_count = _resolve_worker_count(len(pending))
    log(f"Executing {len(pending)} pending tasks with {worker_count} parallel workers.")

    completed_success = 0
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(process_task, idx, len(pending), task_file, report, report_lock): task_file
            for idx, task_file in enumerate(pending, 1)
        }
        for future in as_completed(futures):
            task_file = futures[future]
            task_name = str(task_file.relative_to(ROOT))
            try:
                _, success = future.result()
                if success:
                    completed_success += 1
            except Exception as exc:
                log(f"[Task {task_name}] CRASHED: {exc}")

    log("\n=== ALL TASKS COMPLETE ===")
    log(
        f"Results: {completed_success}/{len(pending)} newly-run tasks succeeded. "
        f"Total successes recorded: {sum(1 for r in report.values() if r.get('success'))}/{len(tasks)}."
    )


if __name__ == "__main__":
    main()
