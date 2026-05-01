
from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task


@pytest.mark.live_integration
def test_manual_1():
    # Execution and email verification
    run_task(
        "Write a python script to calculate the first 10 fibonacci numbers, execute it, and email the results.",
        expected=["Executed", "Sent", "55"],  # 10th Fibonacci is 55 (0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55)
        service="code"
    )
