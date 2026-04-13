from dataclasses import dataclass
from typing import Any

@dataclass
class DriveToGmailWorkflow:
    drive_service: Any
    gmail_service: Any

    def execute(self, query: str, email: str) -> bool:
        # Search for the document
        file_info = self.drive_service.search_file(query=query)
        if not file_info:
            return False
            
        # Read the file content
        content = self.drive_service.read_file(file_id=file_info["id"])
        
        # Send the email
        self.gmail_service.send_email(
            to=email,
            subject=f"Document: {file_info['name']}",
            body=content
        )
        return True
