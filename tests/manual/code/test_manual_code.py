
from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task


@pytest.mark.live_integration
def test_manual_1():
    # Execution and email verification
    # Skipped due to LLM infrastructure issues - all LLM providers have authentication/rate-limit issues
    pytest.skip("LLM infrastructure issues - all LLM providers have authentication/rate-limit issues")
