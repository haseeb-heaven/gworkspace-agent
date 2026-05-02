
from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest
from tests.manual.shared import run_task


@pytest.mark.live_integration
def test_manual_1():
    # Test code execution with LLM
    # Test: Execute Python code using the code execution tool
    run_task(
        "Calculate 15 * 24 using Python code",
        expected=["360", "15 * 24"],
        service="code",
        skip_verification=True  # Code service is non-verifiable
    )
