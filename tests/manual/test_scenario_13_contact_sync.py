import pytest

from tests.manual.scenarios.scenarios_data import SCENARIOS
from tests.manual.shared import run_task


@pytest.mark.live_integration
@pytest.mark.manual
def test_scenario_13_contact_sync():
    """Manual test for scenario_13_contact_sync"""
    scenario = next(s for s in SCENARIOS if s["id"] == "scenario_13_contact_sync")

    # Identify primary service for verification
    # Note: run_task will use this for TripleVerifier and gws.exe verification
    primary_service = "contacts"

    run_task(
        scenario["task"],
        expected=["completed"],
        service=primary_service,
        skip_5step_verification=False,
        skip_gws_verification=False,
    )
