import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

# Ensure we can import scenarios_data
sys.path.append(os.path.join(os.getcwd(), "tests", "scenarios"))
try:
    from scenarios_data import SCENARIOS
except ImportError:
    print("Error: Could not import scenarios_data.py. Make sure you are in the project root.")
    sys.exit(1)

PYTHON_EXE = os.path.join("D:\\henv", "Scripts", "python.exe")
GWS_CLI = "gws_cli.py"

def run_scenario(scenario: Dict[str, Any]):
    scenario_id = scenario["id"]
    task = scenario["task"]
    print(f"[{scenario_id}] Starting task...")

    cmd = [
        PYTHON_EXE, GWS_CLI,
        "--task", task,
        "--sandbox",
        "--force-dangerous"
    ]

    start_time = time.time()
    try:
        # Run the command and capture output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        duration = time.time() - start_time

        status = "SUCCESS" if process.returncode == 0 else "FAILED"
        print(f"[{scenario_id}] Completed in {duration:.2f}s with status: {status}")

        return {
            "id": scenario_id,
            "status": status,
            "duration": duration,
            "stdout": stdout,
            "stderr": stderr
        }
    except Exception as e:
        print(f"[{scenario_id}] Exception occurred: {str(e)}")
        return {
            "id": scenario_id,
            "status": "ERROR",
            "error": str(e)
        }

def main():
    # We'll run 5 scenarios at a time to avoid heavy load or rate limits
    max_workers = 3
    results = []

    # Selecting the first 5 scenarios for this run to demonstrate the workflow
    active_scenarios = SCENARIOS[:5]

    print(f"Running {len(active_scenarios)} scenarios with {max_workers} workers...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(run_scenario, active_scenarios))

    # Save results to a report
    report_path = os.path.join("logs", "scenario_report.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nScenario run complete. Report saved to {report_path}")

    # Check for failures
    failures = [r for r in results if r["status"] != "SUCCESS"]
    if failures:
        print(f"\nFound {len(failures)} failures. Please review the logs.")
        for f in failures:
            print(f"  - {f['id']}: {f.get('error', 'Check stdout/stderr')}")
    else:
        print("\nAll scenarios passed!")

if __name__ == "__main__":
    main()
