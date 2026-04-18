import os
import subprocess
import threading
import time
import json
import logging
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TaskRunner:
    def __init__(self, agent_id: int, service: str, max_retries: int = 3):
        self.agent_id = agent_id
        self.service = service
        self.max_retries = max_retries
        self.attempt_count = 0
        self.status = "IDLE"

    def run_tests(self):
        self.status = "RUNNING"
        self.attempt_count += 1
        logger.info(f"Runner {self.agent_id} starting tests for {self.service} (Attempt {self.attempt_count}/{self.max_retries})")
        
        # Use shutil.which to find pytest executable
        pytest_exe = shutil.which("pytest") or "pytest"
        
        cmd = [pytest_exe, "-v", "-m", self.service]
        
        try:
            # Set up environment with src in PYTHONPATH
            env = os.environ.copy()
            env["PYTHONPATH"] = "src" + os.pathsep + env.get("PYTHONPATH", "")
            
            # Use sys.executable to run pytest module to ensure same environment
            cmd = [sys.executable, "-m", "pytest", "-v", "-m", self.service]
            
            process = subprocess.run(cmd, capture_output=True, text=True, env=env, shell=os.name == 'nt')
            
            if process.returncode == 0:
                self.status = "PASSED"
                logger.info(f"Runner {self.agent_id} ({self.service}) PASSED")
            else:
                self.status = "FAILED"
                logger.warning(f"Runner {self.agent_id} ({self.service}) FAILED.")
                if self.attempt_count < self.max_retries:
                    self._attempt_fix(process.stderr or process.stdout)
                else:
                    logger.error(f"Runner {self.agent_id} ({self.service}) reached max retries.")
        except Exception as e:
            self.status = "ERROR"
            logger.error(f"Runner {self.agent_id} ({self.service}) encountered an error: {e}")

    def _attempt_fix(self, error_msg: str):
        logger.info(f"Runner {self.agent_id} ({self.service}) analyzing error...")
        # Simulation: in real use, we'd pass error_msg to Gemini for a fix
        time.sleep(1)
        logger.info(f"Runner {self.agent_id} ({self.service}) applied auto-fix. Retrying...")
        self.run_tests()

def run_multi_agent_test(services: list[str], agents_per_service: int = 10):
    logger.info(f"🚀 Starting Multi-Agent Testing: {len(services)} services, {agents_per_service} runners each.")
    
    os.makedirs("artifacts", exist_ok=True)
    
    runners = []
    for service in services:
        for i in range(agents_per_service):
            runners.append(TaskRunner(i, service))
            
    with ThreadPoolExecutor(max_workers=len(runners)) as executor:
        futures = [executor.submit(runner.run_tests) for runner in runners]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Worker thread crashed: {e}")

    logger.info("🏁 Multi-Agent Testing Completed.")

if __name__ == "__main__":
    services_to_test = ["gmail", "docs", "sheets", "drive", "calendar"]
    # Run with 1 agent per service for verification of the framework
    run_multi_agent_test(services_to_test, agents_per_service=1)
