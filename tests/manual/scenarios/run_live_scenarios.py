import json
import logging
import os
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List

# Add project root to sys.path
sys.path.append(os.getcwd())

try:
    from gws_assistant.config import AppConfig
    from gws_assistant.gws_runner import GWSRunner
    from gws_assistant.planner import CommandPlanner
    from gws_assistant.verification_engine import VerificationEngine, VerificationError
    from tests.manual.scenarios.scenarios_data import SCENARIOS
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')
logger = logging.getLogger("live_scenario_runner")

def extract_ids(text: str) -> Dict[str, List[str]]:
    """Extract common Google Workspace IDs from text with strict filtering."""
    # Stricter Drive/Doc/Sheet ID: 33-44 chars, alphanumeric and _-
    # Google IDs usually start with 1 (or 0)
    potential_drive_ids = re.findall(r"\b([10][a-zA-Z0-9_\-]{32,43})\b", text)
    potential_gmail_ids = re.findall(r"\b([a-fA-F0-9]{16})\b", text)

    def is_valid_id(s):
        s_lower = s.lower()
        # Filter out known log noise and model names
        noise = ["llama", "groq", "gpt", "openai", "meta", "scout", "instruct", "config", "key", "litellm", "http", "view"]
        if any(p in s_lower for p in noise):
            return False
        # Google IDs usually have at least one digit and one letter
        if not (any(c.isdigit() for c in s) and any(c.isalpha() for c in s)):
            return False
        # Avoid base64-like strings that are just uppercase/lowercase without enough variety
        if len(s) > 40 and (s.isupper() or s.islower()):
            return False
        return True

    ids = {
        "file_id": [i for i in potential_drive_ids if is_valid_id(i)],
        "message_id": potential_gmail_ids,
        "event_id": re.findall(r"\b([a-z0-9]{20,})\b", text), # Calendar IDs are usually long lowercase alphanumeric
    }
    return ids


def verify_with_gws_binary(scenario_id: str, output_text: str, config: Any) -> Dict[str, Any]:
    """Use gws.exe to verify the state change from the task output."""
    logger.info(f"[{scenario_id}] VERIFYING WITH GWS.EXE")

    runner = GWSRunner(Path(config.gws_binary_path), logger, config)
    planner = CommandPlanner()
    found_ids = extract_ids(output_text)

    verification_results = []

    # Verify Files/Docs/Sheets (Drive)
    for file_id in set(found_ids["file_id"]):
        # Skip common non-ID matches
        if len(file_id) < 25: continue

        logger.info(f"[{scenario_id}] Verifying Drive resource: {file_id}")
        cmd = planner.build_command("drive", "get_file", {"file_id": file_id})
        res = runner.run(cmd)
        if res.success:
            try:
                data = json.loads(res.stdout)
                VerificationEngine.verify("drive_get_file", {"file_id": file_id}, data)
                verification_results.append({"resource": "drive", "id": file_id, "status": "VERIFIED"})
            except Exception as e:
                verification_results.append({"resource": "drive", "id": file_id, "status": "FAILED", "reason": str(e)})
        else:
             verification_results.append({"resource": "drive", "id": file_id, "status": "NOT_FOUND"})

    # Verify Gmail
    for msg_id in set(found_ids["message_id"]):
        if len(msg_id) != 16: continue
        logger.info(f"[{scenario_id}] Verifying Gmail message: {msg_id}")
        cmd = planner.build_command("gmail", "get_message", {"message_id": msg_id})
        res = runner.run(cmd)
        if res.success:
            verification_results.append({"resource": "gmail", "id": msg_id, "status": "VERIFIED"})
        else:
            verification_results.append({"resource": "gmail", "id": msg_id, "status": "NOT_FOUND"})

    return {"scenario_id": scenario_id, "verifications": verification_results}

def run_task_live(scenario: Dict[str, Any]) -> Dict[str, Any]:
    scenario_id = scenario["id"]
    task_text = scenario["task"]

    logger.info(f"[{scenario_id}] STARTING LIVE TASK")

    cmd = [
        "python", "gws_cli.py",
        "--task", task_text,
        "--sandbox",
        "--force-dangerous",
        "--no-confirm"
    ]

    try:
        config = AppConfig.from_env()
        # Ensure sandbox and dangerous flags are set
        config.sandbox_enabled = True
        config.force_dangerous = True

        # Run the command and capture output
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=300
        )

        status = "SUCCESS" if process.returncode == 0 else "FAILED"

        # Save logs for this scenario
        log_dir = Path("logs/scenarios")
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / f"{scenario_id}.log", "w", encoding='utf-8') as f:
            f.write(f"STDOUT:\n{process.stdout}\n")
            f.write(f"STDERR:\n{process.stderr}\n")

        v_report = {}
        if status == "SUCCESS":
            logger.info(f"[{scenario_id}] TASK PASSED, INITIATING BINARY VERIFICATION")
            v_report = verify_with_gws_binary(scenario_id, process.stdout, config)
        else:
            logger.error(f"[{scenario_id}] FAILED with exit code {process.returncode}")

        return {
            "id": scenario_id,
            "status": status,
            "exit_code": process.returncode,
            "verification": v_report,
            "stdout_preview": process.stdout[-500:] if process.stdout else "",
            "stderr_preview": process.stderr[-500:] if process.stderr else ""
        }

    except subprocess.TimeoutExpired:
        logger.error(f"[{scenario_id}] TIMED OUT")
        return {"id": scenario_id, "status": "TIMEOUT"}
    except Exception as e:
        logger.exception(f"[{scenario_id}] Unexpected error: {e}")
        return {"id": scenario_id, "status": "ERROR", "error": str(e)}

def main():
    active_scenarios = SCENARIOS # Run ALL scenarios

    max_workers = 8 # Parallel execution with 8 workers
    logger.info(f"Launching {len(active_scenarios)} verified live scenarios with {max_workers} workers...")

    results = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_task_live, s): s for s in active_scenarios}
        for future in as_completed(futures):
            results.append(future.result())

    # Summary
    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    verified_count = sum(1 for r in results if r.get("verification", {}).get("verifications") and all(v["status"] == "VERIFIED" for v in r["verification"]["verifications"]))

    logger.info("Verified Live Scenario Run Complete.")
    logger.info(f"Total: {len(results)}, Task Success: {success_count}, Fully Verified: {verified_count}")

    report_path = "logs/verified_live_scenario_report.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Verified report saved to {report_path}")

if __name__ == "__main__":
    main()
