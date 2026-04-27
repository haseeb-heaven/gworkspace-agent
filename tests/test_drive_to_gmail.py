from dotenv import load_dotenv

load_dotenv()
import os
from unittest.mock import MagicMock

import pytest

from gws_assistant.execution import DriveToGmailWorkflow


def test_drive_to_gmail_workflow():
    # Setup
    mock_drive = MagicMock()
    mock_gmail = MagicMock()

    # Simulate finding the document 'Shibuz' and returning content
    mock_drive.search_file.return_value = {"id": "123", "name": "Shibuz"}
    mock_drive.read_file.return_value = "Content of Shibuz"

    workflow = DriveToGmailWorkflow(drive_service=mock_drive, gmail_service=mock_gmail)

    # Act
    result = workflow.execute(query="Shibuz", email=os.getenv("DEFAULT_RECIPIENT_EMAIL") or "test@example.com")

    # Assert
    assert result is True
    mock_gmail.send_email.assert_called_with(
        to=os.getenv("DEFAULT_RECIPIENT_EMAIL") or "test@example.com",
        subject="Document: Shibuz",
        body="Content of Shibuz",
    )


def test_drive_to_gmail_invalid_email():
    mock_drive = MagicMock()
    mock_gmail = MagicMock()
    workflow = DriveToGmailWorkflow(drive_service=mock_drive, gmail_service=mock_gmail)

    with pytest.raises(ValueError, match="Invalid email address"):
        workflow.execute(query="Shibuz", email="invalid-email")


def test_drive_to_gmail_file_not_found():
    mock_drive = MagicMock()
    mock_gmail = MagicMock()
    mock_drive.search_file.return_value = None
    workflow = DriveToGmailWorkflow(drive_service=mock_drive, gmail_service=mock_gmail)

    with pytest.raises(FileNotFoundError, match="File not found"):
        workflow.execute(query="NonExistent", email="test@example.com")
