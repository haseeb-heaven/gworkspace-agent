
from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task


@pytest.mark.live_integration
def test_manual_1() -> None:
    """Execute a Fibonacci script and verify it runs, emails, and outputs 55."""
    run_task(
        # Prompt explicitly requests 1-indexed sequence [1,1,2,3,5,8,13,21,34,55]
        "Write a python script that prints the first 10 Fibonacci numbers "
        "starting from 1 (i.e. 1,1,2,3,5,8,13,21,34,55), execute it, and email the results.",
        expected=["Command succeeded", "Sent", "55"],  # F(10)=55 in the 1-indexed sequence
        service="code"
    )
