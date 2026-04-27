import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SearchToSheetsWorkflow:
    """Search the web and save results to a Google Sheet."""

    web_search: Any
    sheets: Any

    def execute(self, query: str, title: str = "Search Results") -> bool:
        if not query or not isinstance(query, str):
            logger.error("Invalid query provided: %s", query)
            raise ValueError("Query must be a non-empty string.")

        logger.info("Starting SearchToSheetsWorkflow for query: %s", query)
        try:
            result_data = self.web_search.web_search(query)
            results = result_data.get("results") or result_data.get("rows") or []

            if not results:
                logger.warning("No results found for query: %s", query)
                return False

            rows = []
            for r in results:
                if isinstance(r, dict):
                    rows.append([r.get("title", ""), r.get("content", ""), r.get("link", "")])
                elif isinstance(r, list):
                    rows.append(r)

            spreadsheet = self.sheets.create_spreadsheet(title)
            spreadsheet_id = spreadsheet["spreadsheetId"]

            values = [["Title", "Description", "Link"]] + rows
            self.sheets.append_values(spreadsheet_id, "Sheet1!A1", values)

            logger.info("Successfully created spreadsheet '%s' with %d rows.", title, len(rows))
            return True
        except Exception as exc:
            logger.error(
                "SearchToSheetsWorkflow failed for query '%s': %s",
                query,
                str(exc),
                exc_info=True,
            )
            raise


@dataclass
class DriveToGmailWorkflow:
    """Search Google Drive for a file and send its content via Gmail."""

    drive_service: Any
    gmail_service: Any

    def execute(self, query: str, email: str) -> bool:
        logger.info("Starting DriveToGmailWorkflow for query: %s, email: %s", query, email)
        try:
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                raise ValueError("Invalid email address")

            file_info = self.drive_service.search_file(query)
            if not file_info:
                raise FileNotFoundError("File not found")

            file_id = file_info["id"]
            file_name = file_info.get("name", "Document")
            content = self.drive_service.read_file(file_id)

            self.gmail_service.send_email(to=email, subject=f"Document: {file_name}", body=content)

            logger.info("Successfully sent document '%s' to %s", file_name, email)
            return True
        except Exception as exc:
            logger.error("DriveToGmailWorkflow failed for query '%s': %s", query, str(exc))
            raise
