import pytest
from unittest.mock import MagicMock
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
    result = workflow.execute(query="Shibuz", email="haseebmir.hm@gmail.com")
    
    # Assert
    assert result is True
    mock_gmail.send_email.assert_called_with(
        to="haseebmir.hm@gmail.com",
        subject="Document: Shibuz",
        body="Content of Shibuz"
    )
