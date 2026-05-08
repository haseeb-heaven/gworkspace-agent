from tests.manual.shared import run_task

def test_job_application_tracker_cross_verify():
    """Test job application tracker extraction and cross verify with gws.exe."""
    task_string = "Search my emails for any job applications from my inbox 3 days, list them in a Sheets tracker with company name, role, and date, then create a weekly Calendar reminder to follow up"

    # We expect the agent to list messages, get messages, create a spreadsheet, append values, and create an event
    expected = [
        "sheets.append_values completed.",
        "calendar.create_event completed.",
        "gmail.send_message completed.",
    ]

    unexpected = [
        "The requested identifier already exists",
        "___UNRESOLVED_PLACEHOLDER___"
    ]

    # `run_task` automatically extracts the created resource IDs and runs `verify_with_gws()`
    # to hit the gws.exe binary and assert that the resources actually exist and data is valid.
    run_task(
        task_string=task_string,
        expected=expected,
        unexpected=unexpected,
        service="sheets",
        skip_gws_verification=False, # We MUST verify with gws.exe
    )
