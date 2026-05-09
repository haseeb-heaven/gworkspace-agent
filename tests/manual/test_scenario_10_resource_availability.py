import pytest

from tests.manual.scenarios.scenarios_data import SCENARIOS
from tests.manual.shared import run_task


@pytest.mark.live_integration
@pytest.mark.manual
def test_scenario_10_resource_availability():
    """Manual test for scenario_10_resource_availability"""
    scenario = next(s for s in SCENARIOS if s["id"] == "scenario_10_resource_availability")

    # Identify primary service for verification
    # Note: run_task will use this for TripleVerifier and gws.exe verification
    primary_service = "calendar"

    run_task(
        scenario["task"],
        expected=["completed"],
        service=primary_service,
        skip_5step_verification=False,
        skip_gws_verification=False,
    )
