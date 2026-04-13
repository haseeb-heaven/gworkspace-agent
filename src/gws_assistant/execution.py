import re
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

@dataclass
class PlanExecutor:
    def _think(self, *args, **kwargs) -> str:
        return "Thought: Proceeding with planned task."
    
    def _should_replan(self, *args, **kwargs) -> bool:
        return False
    
    def execute(self, plan: Any) -> Any:
        pass

@dataclass
class SearchToSheetsWorkflow:
    web_search: Any
    sheets: Any

    def execute(self, query: str, title: str = "Search Results") -> bool:
        if not query or not isinstance(query, str):
            logger.error("Invalid query provided: %s", query)
            raise ValueError("Query must be a non-empty string.")

        logger.info(f"Starting search to sheets workflow for query: {query}")
        try:
            results = self.web_search.web_search(query=query)
            if not results or "rows" not in results:
                logger.warning(f"No results found for query: {query}")
                return False

            rows = results["rows"]
            
            sheet = self.sheets.create_spreadsheet(title=title)
            self.sheets.append_values(
                spreadsheet_id=sheet["spreadsheetId"],
                range="Sheet1!A1",
                values=[["Name", "Description", "GitHub Stars", "Features"]] + rows
            )
            logger.info(f"Successfully created spreadsheet '{title}' with {len(rows)} rows.")
            return True
        except Exception as e:
            logger.error(f"SearchToSheetsWorkflow failed for query '{query}': {str(e)}", exc_info=True)
            raise e

@dataclass
class DriveToGmailWorkflow:
    drive_service: Any
    gmail_service: Any

    def execute(self, query: str, email: str) -> bool:
        logger.info(f"Starting workflow for query: {query}, target email: {email}")
        try:
            if not re.match(r'[^@]+@[^@]+\.[^@]+', email):
                raise ValueError('Invalid email address')
            
            # Search for the document
            file_info = self.drive_service.search_file(query=query)
            if not file_info:
                raise FileNotFoundError(f"File not found for query: {query}")

            # Read the file content
            content = self.drive_service.read_file(file_id=file_info['id'])

            # Send the email
            self.gmail_service.send_email(
                to=email,
                subject=f"Document: {file_info['name']}",
                body=content
            )
            logger.info(f"Successfully sent document '{file_info['name']}' to {email}")
            return True
        except Exception as e:
            logger.error(f"Workflow failed for query {query}: {str(e)}")
            raise e
