import pytest

from tests.manual.scenarios.scenarios_data import SCENARIOS
from tests.manual.shared import run_task


@pytest.mark.live_integration
@pytest.mark.manual
def test_scenario_18_sheet_data_validation():
    """Manual test for scenario_18_sheet_data_validation"""
    scenario = next(s for s in SCENARIOS if s["id"] == "scenario_18_sheet_data_validation")

    # Identify primary service for verification
    # Note: run_task will use this for TripleVerifier and gws.exe verification
    primary_service = "sheets"

    run_task(
        scenario["task"],
        expected=["completed"],
        service=primary_service,
        skip_5step_verification=False,
        skip_gws_verification=False,
    )
