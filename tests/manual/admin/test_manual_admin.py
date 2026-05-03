
from dotenv import load_dotenv

load_dotenv()  # Load .env at module level
import pytest

from tests.manual.shared import run_task


@pytest.mark.live_integration
def test_manual_1():
    # Read and email verification
    run_task(
        "List the last 5 login activities from the admin reports and email the list.",
        expected=["completed"],
        service="admin",
    )
