import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')
logger = logging.getLogger("scenario_verifier")

# Add project root to sys.path
sys.path.append(os.getcwd())

try:
    from gws_assistant.config import AppConfig
    from gws_assistant.gws_runner import GWSRunner
    from gws_assistant.intent_parser import IntentParser
    from gws_assistant.planner import CommandPlanner
    from gws_assistant.verification_engine import VerificationEngine, VerificationError
    from tests.manual.scenarios.scenarios_data import SCENARIOS
except ImportError as e:
    logger.error(f"Import failed: {e}")
    sys.exit(1)

def execute_and_verify_scenario(scenario: Dict[str, Any]):
    scenario_id = scenario["id"]
    task_text = scenario["task"]

    logger.info(f"[{scenario_id}] STARTING SCENARIO")

    try:
        config = AppConfig.from_env()
        # Ensure sandbox and dangerous flags are set
        config.sandbox_enabled = True
        config.force_dangerous = True

        runner = GWSRunner(Path(config.gws_binary_path), logger, config)
        parser = IntentParser(config, logger)
        planner = CommandPlanner()

        # 1. Parse Intent (Simulation or real)
        logger.info(f"[{scenario_id}] Parsing intent...")
        intent = parser.parse(task_text)
        if intent.needs_clarification:
            logger.error(f"[{scenario_id}] Intent needs clarification: {intent.clarification_reason}")
            return {"id": scenario_id, "status": "FAILED", "reason": "intent_clarification"}

        # 2. Build Commands (Simplified for multi-step scenarios)
        # Note: Real agent uses a LangGraph workflow. Here we simulate the key steps.
        # For complex scenarios, we might need to handle placeholder resolution.

        # For this demonstration, we'll run a single core action if detected,
        # or use the planner to build a basic command.
        service = intent.service
        action = intent.action
        params = intent.parameters

        logger.info(f"[{scenario_id}] Planned: {service}.{action} with params {list(params.keys())}")

        # 3. Pre-execution Verification
        logger.info(f"[{scenario_id}] Verifying pre-execution...")
        try:
            VerificationEngine.verify_pre_execution(f"{service}_{action}", params)
        except VerificationError as e:
            logger.error(f"[{scenario_id}] Pre-execution verification FAILED: {e}")
            return {"id": scenario_id, "status": "FAILED", "reason": "pre_verification", "error": str(e)}

        # 4. Execute Command
        logger.info(f"[{scenario_id}] Executing command...")
        cmd_args = planner.build_command(service, action, params)
        # Add necessary flags
        if "--sandbox" not in cmd_args:
            cmd_args.append("--sandbox")
        if "--force-dangerous" not in cmd_args:
            cmd_args.append("--force-dangerous")

        execution_result = runner.run(cmd_args)

        if not execution_result.success:
            logger.error(f"[{scenario_id}] Execution FAILED: {execution_result.error}")
            return {"id": scenario_id, "status": "FAILED", "reason": "execution_failure", "error": execution_result.error}

        # 5. Post-execution Verification
        logger.info(f"[{scenario_id}] Verifying post-execution...")
        try:
            # We need the structured result from stdout if possible
            result_data = {}
            if execution_result.stdout:
                try:
                    result_data = json.loads(execution_result.stdout)
                except json.JSONDecodeError:
                    result_data = {"raw_output": execution_result.stdout}

            VerificationEngine.verify(f"{service}_{action}", params, result_data)
            logger.info(f"[{scenario_id}] SCENARIO PASSED")
            return {"id": scenario_id, "status": "SUCCESS"}

        except VerificationError as e:
            logger.error(f"[{scenario_id}] Post-execution verification FAILED: {e}")
            return {"id": scenario_id, "status": "FAILED", "reason": "post_verification", "error": str(e)}

    except Exception as e:
        logger.exception(f"[{scenario_id}] Unexpected error: {e}")
        return {"id": scenario_id, "status": "ERROR", "error": str(e)}

def main():
    # Run a selection of scenarios to demonstrate verification
    active_scenarios = SCENARIOS[:5]

    logger.info(f"Starting execution of {len(active_scenarios)} scenarios...")

    results = []
    # Use ThreadPoolExecutor to simulate "multiple agents"
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(execute_and_verify_scenario, active_scenarios))

    # Summary
    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    logger.info(f"Execution complete. Total: {len(results)}, Success: {success_count}, Failures: {len(results) - success_count}")

    report_path = "logs/verified_scenario_report.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Report saved to {report_path}")

if __name__ == "__main__":
    main()
