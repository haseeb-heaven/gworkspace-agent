from tests.manual.shared import run_task


def test_job_application_tracker_cross_verify() -> None:
    """Test job application tracker extraction and cross verify with gws.exe."""
    task_string = (
        "Search my emails for any job applications from my inbox 3 days, "
        "list them in a Sheets tracker with company name, role, and date, "
        "then create a weekly Calendar reminder to follow up"
    )

    # We expect the agent to list messages, get messages, create a spreadsheet, append values, and create an event
    expected = [
        "completed",
    ]

    unexpected = [
        "The requested identifier already exists",
    ]

    run_task(
        task_string=task_string,
        expected=expected,
        unexpected=unexpected,
        service="sheets",
        skip_verification=True,
    )
