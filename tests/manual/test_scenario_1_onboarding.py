import pytest

from tests.manual.scenarios.scenarios_data import SCENARIOS
from tests.manual.shared import run_task


@pytest.mark.live_integration
@pytest.mark.manual
def test_scenario_1_onboarding():
    """Manual test for scenario_1_onboarding"""
    scenario = next(s for s in SCENARIOS if s["id"] == "scenario_1_onboarding")

    # Identify primary service for verification
    # Note: run_task will use this for TripleVerifier and gws.exe verification
    primary_service = "drive"

    run_task(
        scenario["task"],
        expected=["completed"],
        service=primary_service,
        skip_5step_verification=False,
        skip_gws_verification=False,
    )
