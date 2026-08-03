from pathlib import Path

# The scenarios are in tests/manual/scenarios/scenarios_data.py
# We want to create tests/manual/test_scenario_1.py etc.

scenarios_file = Path("tests/manual/scenarios/scenarios_data.py")
output_dir = Path("tests/manual")

# Simplified mock of SCENARIOS for the generator
SCENARIOS = [
    {"id": "scenario_1_onboarding", "service": "drive,docs,gmail"},
    {"id": "scenario_2_expense_audit", "service": "gmail,sheets,code"},
    {"id": "scenario_3_meeting_prep", "service": "calendar,drive,gmail"},
    {"id": "scenario_4_task_sync", "service": "tasks,calendar"},
    {"id": "scenario_5_content_archive", "service": "drive"},
    {"id": "scenario_6_daily_digest", "service": "calendar,chat"},
    {"id": "scenario_7_file_audit", "service": "drive,gmail"},
    {"id": "scenario_8_note_consolidation", "service": "keep,docs"},
    {"id": "scenario_9_newsletter", "service": "gmail,docs,gmail"},
    {"id": "scenario_10_resource_availability", "service": "calendar,gmail"},
    {"id": "scenario_11_onboarding_batch", "service": "drive,gmail,docs"},
    {"id": "scenario_12_sheet_to_slides", "service": "sheets,slides"},
    {"id": "scenario_13_contact_sync", "service": "contacts,sheets"},
    {"id": "scenario_14_event_feedback", "service": "calendar,gmail"},
    {"id": "scenario_15_drive_cleanup_by_type", "service": "drive"},
    {"id": "scenario_16_urgent_chat_alert", "service": "gmail,chat"},
    {"id": "scenario_17_doc_template_generator", "service": "docs,drive"},
    {"id": "scenario_18_sheet_data_validation", "service": "sheets,code,gmail"},
    {"id": "scenario_19_meeting_scheduler", "service": "calendar,gmail"},
    {"id": "scenario_20_workspace_health_report", "service": "gmail,drive,calendar,sheets"},
]

template = """import pytest
from tests.manual.shared import run_task
from tests.manual.scenarios.scenarios_data import SCENARIOS

@pytest.mark.live_integration
@pytest.mark.manual
def test_{scenario_id}():
    \"\"\"Manual test for {scenario_id}\"\"\"
    scenario = next(s for s in SCENARIOS if s["id"] == "{scenario_id}")

    # Identify primary service for verification
    # Note: run_task will use this for TripleVerifier and gws.exe verification
    primary_service = "{primary_service}"

    run_task(
        scenario["task"],
        expected=["completed"],
        service=primary_service,
        skip_5step_verification=False,
        skip_gws_verification=False,
    )
"""

for i, scenario in enumerate(SCENARIOS):
    scenario_id = scenario["id"]
    primary_service = scenario["service"].split(",")[0]
    content = template.format(scenario_id=scenario_id, primary_service=primary_service)
    file_path = output_dir / f"test_{scenario_id}.py"
    with open(file_path, "w") as f:
        f.write(content)
    print(f"Created {file_path}")
