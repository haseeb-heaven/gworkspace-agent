
from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest
import subprocess
import os


@pytest.mark.live_integration
def test_manual_1():
    # Test code execution with LLM
    # Test: Execute Python code using the code execution tool
    result = subprocess.run(
        ["python", "gws_cli.py", "--task", "Calculate 15 * 24 using Python code"],
        capture_output=True,
        text=True,
        cwd=os.getcwd()
    )
    
    # Check that the command executed successfully
    assert result.returncode == 0, f"Command failed with error: {result.stderr}"
    
    # Check that the result contains the expected calculation
    assert "360" in result.stdout or "15 * 24" in result.stdout, f"Expected calculation result not found in output: {result.stdout}"
