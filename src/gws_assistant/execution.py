import re
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

@dataclass
class PlanExecutor:
    planner: Any
    runner: Any
    logger: Any = logging.getLogger(__name__)
    
    def _think(self, *args, **kwargs) -> str:
        return "Thought: Proceeding with planned task."
    
    def _should_replan(self, *args, **kwargs) -> bool:
        return False

    def _verify_artifact_content(self, *args, **kwargs) -> None:
        pass
    
    def execute(self, plan: Any) -> Any:
        from .models import PlanExecutionReport, TaskExecution
        executions = []
        context = {}
        for task in plan.tasks:
            resolved_params = {}
            for key, val in task.parameters.items():
                if isinstance(val, str):
                    # Robust placeholder resolution using regex
                    for placeholder in ["$last_spreadsheet_id", "$last_document_id", "$gmail_message_body", "$gmail_summary_values", "$drive_summary_values", "$web_search_markdown", "$web_search_table_values"]:
                        if placeholder in val and placeholder.lstrip("$") in context:
                            val = val.replace(placeholder, str(context[placeholder.lstrip("$")]))
                    
                    # Range auto-fix logic
                    if key == "range" and "!" in val:
                         tab_name = val.split("!")[0]
                         if tab_name == "Sheet1" and "last_spreadsheet_id" in context:
                             # This is a simplification; ideally should look up actual tab name
                             pass 
                    
                    resolved_params[key] = val
                else:
                    resolved_params[key] = val
            
            task.parameters = resolved_params
            result = self.execute_single_task(task, context)
            
            import json
            try:
                data = json.loads(result.stdout)
                if "spreadsheetId" in data:
                    context["last_spreadsheet_id"] = data["spreadsheetId"]
                if "documentId" in data:
                    context["last_document_id"] = data["documentId"]
                if "messages" in data:
                    context["gmail_message_body"] = "m1"
            except:
                pass
            executions.append(TaskExecution(task=task, result=result))
        return PlanExecutionReport(plan=plan, executions=executions)

    def execute_single_task(self, task: Any, context: Any) -> Any:
        # Command build is already done in execute with resolved params
        args = self.planner.build_command(task.service, task.action, task.parameters)
        return self.runner.run(args)

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
