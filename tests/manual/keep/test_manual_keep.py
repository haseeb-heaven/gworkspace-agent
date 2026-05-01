
from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task


@pytest.mark.live_integration
def test_manual_1():
    # Create verification
    run_task(
        "Create a Keep note titled 'Manual Test Validation: Phase 4 Keep' with the body 'Hello from GWS Agent testing phase. This is the manual test validation for Keep.'",
        expected=["Created", "Manual Test Validation"],
        service="keep"
    )
