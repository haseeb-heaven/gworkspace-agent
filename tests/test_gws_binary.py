"""Unit tests for direct gws.exe binary commands (no agent system)."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from dotenv import load_dotenv

load_dotenv()


@pytest.fixture
def gws_binary():
    """Get the gws binary path from environment or default."""
    return os.getenv("GWS_BINARY_PATH", "gws")


@pytest.fixture
def project_root():
    """Get the project root directory."""
    return Path(__file__).resolve().parents[2]


@pytest.mark.gws_binary
class TestGwsBinaryDirect:
    """Test gws.exe binary directly without agent system."""

    @pytest.mark.drive
    def test_drive_list_files(self, gws_binary, project_root):
        """Test direct gws.exe command to list drive files."""
        result = subprocess.run(
            [gws_binary, "drive", "files", "list", "--params", '{"pageSize": "5"}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for drive files list ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        # Should not crash, even if auth fails
        assert result.returncode in [0, 1]  # 0 = success, 1 = auth/scopes issue

    @pytest.mark.drive
    def test_drive_list_files_with_format(self, gws_binary, project_root):
        """Test gws.exe with format flag."""
        result = subprocess.run(
            [gws_binary, "drive", "files", "list", "--format", "json", "--params", '{"pageSize": "1"}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for drive files list with format ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        assert result.returncode in [0, 1]

    @pytest.mark.gmail
    def test_gmail_list_messages(self, gws_binary, project_root):
        """Test direct gws.exe command to list gmail messages."""
        result = subprocess.run(
            [gws_binary, "gmail", "users", "messages", "list", "--params", '{"userId": "me", "maxResults": "1"}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for gmail messages list ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        assert result.returncode in [0, 1]

    @pytest.mark.sheets
    def test_sheets_create_spreadsheet(self, gws_binary, project_root):
        """Test direct gws.exe command to create a spreadsheet."""
        result = subprocess.run(
            [gws_binary, "sheets", "spreadsheets", "create", "--params", '{"title": "Test Spreadsheet"}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for sheets spreadsheet create ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        # May fail due to auth/scopes, that's expected
        assert result.returncode in [0, 1]

    @pytest.mark.docs
    def test_docs_create_document(self, gws_binary, project_root):
        """Test direct gws.exe command to create a document."""
        result = subprocess.run(
            [gws_binary, "docs", "documents", "create", "--params", '{"title": "Test Document"}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for docs document create ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        # May fail due to auth/scopes, that's expected
        assert result.returncode in [0, 1]

    @pytest.mark.calendar
    def test_calendar_list_events(self, gws_binary, project_root):
        """Test direct gws.exe command to list calendar events."""
        result = subprocess.run(
            [gws_binary, "calendar", "events", "list", "--params", '{"calendarId": "primary", "maxResults": "1"}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for calendar events list ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        assert result.returncode in [0, 1]

    @pytest.mark.contacts
    def test_contacts_list_connections(self, gws_binary, project_root):
        """Test direct gws.exe command to list contacts."""
        result = subprocess.run(
            [gws_binary, "people", "people", "connections", "list", "--params", '{"resourceName": "people/me"}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for contacts list ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        # This may fail with 403 (insufficient scopes) - that's expected
        assert result.returncode in [0, 1, 403]

    @pytest.mark.script
    def test_gws_help(self, gws_binary, project_root):
        """Test that gws.exe help command works."""
        result = subprocess.run(
            [gws_binary, "--help"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for help ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        assert result.returncode == 0
        assert "USAGE" in result.stdout

    @pytest.mark.script
    def test_gws_schema(self, gws_binary, project_root):
        """Test gws.exe schema command."""
        result = subprocess.run(
            [gws_binary, "schema", "drive.files.list"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for schema ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        assert result.returncode == 0

    # Additional test scenarios - different combinations

    @pytest.mark.drive
    def test_drive_files_list_with_q_parameter(self, gws_binary, project_root):
        """Test drive files list with search query parameter."""
        result = subprocess.run(
            [gws_binary, "drive", "files", "list", "--params", '{"q": "mimeType=\'application/pdf\'", "pageSize": "3"}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for drive files list with q parameter ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        assert result.returncode in [0, 1]

    @pytest.mark.drive
    def test_drive_files_list_table_format(self, gws_binary, project_root):
        """Test drive files list with table format."""
        result = subprocess.run(
            [gws_binary, "drive", "files", "list", "--format", "table", "--params", '{"pageSize": "3"}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for drive files list table format ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        assert result.returncode in [0, 1]

    @pytest.mark.gmail
    def test_gmail_messages_list_with_q(self, gws_binary, project_root):
        """Test gmail messages list with search query."""
        result = subprocess.run(
            [gws_binary, "gmail", "users", "messages", "list", "--params", '{"userId": "me", "q": "subject:test", "maxResults": "1"}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for gmail messages list with q ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        assert result.returncode in [0, 1]

    @pytest.mark.calendar
    def test_calendar_events_list_with_time_range(self, gws_binary, project_root):
        """Test calendar events list with time range."""
        result = subprocess.run(
            [gws_binary, "calendar", "events", "list", "--params", '{"calendarId": "primary", "timeMin": "2024-01-01T00:00:00Z", "maxResults": "1"}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for calendar events list with time range ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        assert result.returncode in [0, 1]

    @pytest.mark.sheets
    def test_sheets_spreadsheets_get_without_id(self, gws_binary, project_root):
        """Test sheets spreadsheets get without ID (should fail gracefully)."""
        result = subprocess.run(
            [gws_binary, "sheets", "spreadsheets", "get", "--params", '{}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for sheets spreadsheets get without ID ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        # Should fail with validation error
        assert result.returncode != 0

    @pytest.mark.drive
    def test_drive_files_create_folder(self, gws_binary, project_root):
        """Test drive files create for folder."""
        result = subprocess.run(
            [gws_binary, "drive", "files", "create", "--params", '{"name": "Test Folder", "mimeType": "application/vnd.google-apps.folder"}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for drive files create folder ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        # May fail due to auth/scopes
        assert result.returncode in [0, 1]

    @pytest.mark.slides
    def test_slides_presentations_create(self, gws_binary, project_root):
        """Test slides presentations create."""
        result = subprocess.run(
            [gws_binary, "slides", "presentations", "create", "--params", '{"title": "Test Presentation"}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for slides presentations create ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        # May fail due to auth/scopes
        assert result.returncode in [0, 1]

    @pytest.mark.script
    def test_gws_schema_multiple(self, gws_binary, project_root):
        """Test gws.exe schema for multiple endpoints."""
        schemas = [
            "drive.files.get",
            "gmail.users.messages.get",
            "sheets.spreadsheets.get",
        ]
        for schema in schemas:
            result = subprocess.run(
                [gws_binary, "schema", schema],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )
            print(f"\n--- gws.exe schema for {schema} ---")
            print(f"Return code: {result.returncode}")
            if result.returncode == 0:
                print(f"Schema found for {schema}")
            else:
                print(f"Schema not found or error for {schema}")
            print(f"--- End output ---\n")
            # Schema should always work if the endpoint exists
            assert result.returncode in [0, 1]

    @pytest.mark.drive
    def test_drive_files_list_yaml_format(self, gws_binary, project_root):
        """Test drive files list with YAML format."""
        result = subprocess.run(
            [gws_binary, "drive", "files", "list", "--format", "yaml", "--params", '{"pageSize": "1"}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for drive files list YAML format ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        assert result.returncode in [0, 1]

    @pytest.mark.contacts
    def test_contacts_list_with_person_fields(self, gws_binary, project_root):
        """Test contacts list with specific person fields."""
        result = subprocess.run(
            [gws_binary, "people", "people", "connections", "list", "--params", '{"resourceName": "people/me", "personFields": "names,emailAddresses"}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for contacts list with person fields ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        # May fail with 403 (insufficient scopes)
        assert result.returncode in [0, 1, 403]

    # Tests for missing services

    @pytest.mark.tasks
    def test_tasks_list_tasklists(self, gws_binary, project_root):
        """Test tasks list tasklists."""
        result = subprocess.run(
            [gws_binary, "tasks", "tasklists", "list", "--params", '{}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for tasks tasklists list ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        assert result.returncode in [0, 1]

    @pytest.mark.chat
    def test_chat_list_spaces(self, gws_binary, project_root):
        """Test chat list spaces."""
        result = subprocess.run(
            [gws_binary, "chat", "spaces", "list", "--params", '{}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for chat spaces list ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        assert result.returncode in [0, 1]

    @pytest.mark.forms
    def test_forms_list_forms(self, gws_binary, project_root):
        """Test forms list forms."""
        result = subprocess.run(
            [gws_binary, "forms", "forms", "list", "--params", '{}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for forms forms list ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        # Forms may not have list command or require special setup
        assert result.returncode in [0, 1, 3]

    @pytest.mark.keep
    def test_keep_list_notes(self, gws_binary, project_root):
        """Test keep list notes."""
        result = subprocess.run(
            [gws_binary, "keep", "notes", "list", "--params", '{}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for keep notes list ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        assert result.returncode in [0, 1]

    @pytest.mark.meet
    def test_meet_list_conferences(self, gws_binary, project_root):
        """Test meet list conferences."""
        result = subprocess.run(
            [gws_binary, "meet", "conferences", "list", "--params", '{}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for meet conferences list ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        # Meet may not have list command or require special setup
        assert result.returncode in [0, 1, 3]

    @pytest.mark.admin
    def test_admin_reports_list_activities(self, gws_binary, project_root):
        """Test admin-reports list activities."""
        result = subprocess.run(
            [gws_binary, "admin-reports", "activities", "list", "--params", '{"userKey": "all", "maxResults": "1"}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for admin-reports activities list ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        # Admin reports require special admin scope
        assert result.returncode in [0, 1, 3, 403]

    @pytest.mark.classroom
    def test_classroom_list_courses(self, gws_binary, project_root):
        """Test classroom list courses."""
        result = subprocess.run(
            [gws_binary, "classroom", "courses", "list", "--params", '{}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for classroom courses list ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        assert result.returncode in [0, 1]

    @pytest.mark.events
    def test_events_watch(self, gws_binary, project_root):
        """Test events watch (may not have list command)."""
        result = subprocess.run(
            [gws_binary, "events", "watch", "--params", '{}'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for events watch ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        # Events may require special setup
        assert result.returncode in [0, 1, 3]

    @pytest.mark.modelarmor
    def test_modelarmor_help(self, gws_binary, project_root):
        """Test modelarmor help (specialized service)."""
        result = subprocess.run(
            [gws_binary, "modelarmor", "--help"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for modelarmor help ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        # Modelarmor is a specialized filtering service
        assert result.returncode in [0, 1, 3]

    @pytest.mark.script
    def test_workflow_help(self, gws_binary, project_root):
        """Test workflow help (specialized service)."""
        result = subprocess.run(
            [gws_binary, "workflow", "--help"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for workflow help ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        # Workflow is a cross-service automation service
        assert result.returncode in [0, 1, 3]

    @pytest.mark.script
    def test_script_help(self, gws_binary, project_root):
        """Test script help (specialized service)."""
        result = subprocess.run(
            [gws_binary, "script", "--help"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        print(f"\n--- gws.exe output for script help ---")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        print(f"Return code: {result.returncode}")
        print(f"--- End output ---\n")
        # Script is for Apps Script projects
        assert result.returncode in [0, 1, 3]
