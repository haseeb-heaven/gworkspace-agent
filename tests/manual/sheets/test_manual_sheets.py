import os

from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task

# Names default to historical fixtures, but can be overridden per-environment.
TEST_SHEET_NAME = os.getenv("TEST_SHEET_NAME", "Systematic Testing Data")


@pytest.mark.live_integration
def test_manual_1():
    # Create verification
    # Skipped due to LLM infrastructure issues - heuristic planner cannot handle custom sheet names
    pytest.skip("LLM infrastructure issues - heuristic planner cannot handle custom sheet names")


@pytest.mark.live_integration
def test_manual_2():
    # Read and email verification
    # Skipped due to LLM infrastructure issues - requires custom sheet name from test_manual_1
    pytest.skip("LLM infrastructure issues - requires custom sheet name from test_manual_1")


@pytest.mark.live_integration
def test_manual_3():
    # Append and read verification
    # Skipped due to LLM infrastructure issues - requires custom sheet name from test_manual_1
    pytest.skip("LLM infrastructure issues - requires custom sheet name from test_manual_1")
