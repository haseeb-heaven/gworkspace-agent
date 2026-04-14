import subprocess
from pathlib import Path
from .logger import setup_framework_logger

logger = setup_framework_logger("cli_runner")

class GWSCLIRunner:
    def __init__(self, binary_path: str = "D:/henv/Scripts/python.exe"):
        self.binary_path = binary_path
        self.script_path = str(Path("gws_cli.py").resolve())

    def run_command(self, args: list[str]) -> subprocess.CompletedProcess:
        cmd = [self.binary_path, self.script_path] + args
        logger.debug(f"Running command: {' '.join(cmd)}")
        return subprocess.run(cmd, capture_output=True, text=True)

    def run_task(self, task: str) -> subprocess.CompletedProcess:
        logger.info(f"Executing task: {task}")
        return self.run_command(["--task", task])
