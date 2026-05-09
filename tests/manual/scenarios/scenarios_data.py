"""Complex GWorkspace scenarios for agentic testing."""
import os

# Base environment variables
RECIPIENT = os.getenv("SCENARIO_STAKEHOLDER_EMAIL", "")
PROJECT_NAME = os.getenv("SCENARIO_PROJECT_NAME", "Icarus Project Launch")
REPORT_NAME = os.getenv("SCENARIO_REPORT_NAME", "Weekly Activity Report")
FILE_NAME = os.getenv("TEST_FILE_NAME", "README.md")

SCENARIOS = [
    {
        "id": "scenario_1_onboarding",
        "service": "drive,docs,gmail",
        "task": (
            f"Create a Drive folder named '{PROJECT_NAME} - Onboarding'. "
            f"Inside, create a Google Doc 'Welcome Guide' with content 'Welcome to the team!'. "
            f"Also upload the file '{FILE_NAME}' to the same folder. "
            f"Finally, send an email to {RECIPIENT} with the folder's link."
        ),
        "tags": ["live", "manual", "live_integration"]
    },
    {
        "id": "scenario_2_expense_audit",
        "service": "gmail,sheets,code",
        "task": (
            f"Search for emails from 'Amazon' in the last 7 days. "
            f"If any are found, create a Google Sheet '{REPORT_NAME}' and append the sender, date, and snippet of each email. "
            f"If more than 3 emails are found, send a summary email to {RECIPIENT}."
        ),
        "tags": ["live", "manual", "live_integration"]
    },
    {
        "id": "scenario_3_meeting_prep",
        "service": "calendar,drive,gmail",
        "task": (
            f"Find a Calendar event with 'Kickoff' in the title. "
            f"Search Drive for any file with 'Kickoff' in the name. "
            f"Send an email to {RECIPIENT} with the link to that file and the meeting time."
        ),
        "tags": ["live", "manual", "live_integration"]
    },
    {
        "id": "scenario_4_task_sync",
        "service": "tasks,calendar",
        "task": (
            "List all tasks due today. For each task, create a corresponding 30-minute Google Calendar event "
            "starting at 10 AM (incrementing by 1 hour for each task)."
        ),
        "tags": ["live", "manual", "live_integration"]
    },
    {
        "id": "scenario_5_content_archive",
        "service": "drive",
        "task": (
            "Find all Google Docs in the root folder that haven't been modified in the last 3 months. "
            "Create an 'Archive' folder and move those files into it."
        ),
        "tags": ["live", "manual", "live_integration"]
    },
    {
        "id": "scenario_6_daily_digest",
        "service": "calendar,chat",
        "task": (
            "Get today's calendar events, summarize them into a short paragraph, and post it to a Google Chat space."
        ),
        "tags": ["live", "manual", "live_integration"]
    },
    {
        "id": "scenario_7_file_audit",
        "service": "drive,gmail",
        "task": (
            f"List files on Drive that are shared with any external email (not @gmail.com). "
            f"Send a report of these files to {RECIPIENT}."
        ),
        "tags": ["live", "manual", "live_integration"]
    },
    {
        "id": "scenario_8_note_consolidation",
        "service": "keep,docs",
        "task": (
            "Find all Google Keep notes with the title containing 'Draft'. "
            "Consolidate their content into a single Google Doc titled 'Consolidated Drafts'."
        ),
        "tags": ["live", "manual", "live_integration"]
    },
    {
        "id": "scenario_9_newsletter",
        "service": "gmail,docs,gmail",
        "task": (
            f"Search for the latest 3 emails with subject 'Weekly Update'. "
            f"Summarize them and create a Google Doc 'Newsletter - Today'. "
            f"Email the link of this Doc to {RECIPIENT}."
        ),
        "tags": ["live", "manual", "live_integration"]
    },
    {
        "id": "scenario_10_resource_availability",
        "service": "calendar,gmail",
        "task": (
            f"Check my primary calendar for any 2-hour free slots tomorrow between 9 AM and 5 PM. "
            f"Email the list of these slots to {RECIPIENT}."
        ),
        "tags": ["live", "manual", "live_integration"]
    },
    {
        "id": "scenario_11_onboarding_batch",
        "service": "drive,gmail,docs",
        "task": (
            f"Create 3 separate Drive folders for 'Engineering', 'Marketing', and 'Sales' under a parent folder '{PROJECT_NAME}'. "
            f"Create a 'Getting Started' Doc in each. "
            f"Email the links of all 3 folders to {RECIPIENT}."
        ),
        "tags": ["live", "manual", "live_integration"]
    },
    {
        "id": "scenario_12_sheet_to_slides",
        "service": "sheets,slides",
        "task": (
            "Read data from a Sheet named 'Monthly Stats'. "
            "Create a Slide presentation where each slide represents a row of data from that sheet."
        ),
        "tags": ["live", "manual", "live_integration"]
    },
    {
        "id": "scenario_13_contact_sync",
        "service": "contacts,sheets",
        "task": (
            "Export all contacts with the group 'Work' to a Google Sheet named 'Work Contacts List'."
        ),
        "tags": ["live", "manual", "live_integration"]
    },
    {
        "id": "scenario_14_event_feedback",
        "service": "calendar,gmail",
        "task": (
            "Find the most recent past calendar event with 'Training' in the title. "
            "Send a follow-up email to all its attendees asking for feedback."
        ),
        "tags": ["live", "manual", "live_integration"]
    },
    {
        "id": "scenario_15_drive_cleanup_by_type",
        "service": "drive",
        "task": (
            "Find all .tmp and .log files on Drive and move them to a folder named 'Cleanup Queue'."
        ),
        "tags": ["live", "manual", "live_integration"]
    },
    {
        "id": "scenario_16_urgent_chat_alert",
        "service": "gmail,chat",
        "task": (
            f"Search Gmail for unread emails from {RECIPIENT}. "
            f"For each email, post the subject and a short snippet to a Google Chat space."
        ),
        "tags": ["live", "manual", "live_integration"]
    },
    {
        "id": "scenario_17_doc_template_generator",
        "service": "docs,drive",
        "task": (
            "Create 5 copies of the file 'Template.docx' (if it exists, otherwise use a new Doc) "
            "named 'Client_A', 'Client_B', etc., and store them in a 'Client Documents' folder."
        ),
        "tags": ["live", "manual", "live_integration"]
    },
    {
        "id": "scenario_18_sheet_data_validation",
        "service": "sheets,code,gmail",
        "task": (
            f"Read the 'Inventory' sheet. Use code to find any items where the 'Stock' is less than 10. "
            f"Email a list of these items to {RECIPIENT}."
        ),
        "tags": ["live", "manual", "live_integration"]
    },
    {
        "id": "scenario_19_meeting_scheduler",
        "service": "calendar,gmail",
        "task": (
            f"Find a common free 30-minute slot for tomorrow afternoon between me and {RECIPIENT} "
            f"and send a calendar invitation for 'Project Sync'."
        ),
        "tags": ["live", "manual", "live_integration"]
    },
    {
        "id": "scenario_20_workspace_health_report",
        "service": "gmail,drive,calendar,sheets",
        "task": (
            f"Create a summary report in a Google Doc that includes: "
            f"1. Count of unread emails today. 2. Count of files modified today. 3. Number of meetings today. "
            f"Email the report link to {RECIPIENT}."
        ),
        "tags": ["live", "manual", "live_integration"]
    }
]
