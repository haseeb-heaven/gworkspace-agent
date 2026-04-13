import re
import json
import base64
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class PlanExecutor:
    planner: Any
    runner: Any
    logger: Any = field(default_factory=lambda: logging.getLogger(__name__))
    config: Optional[Any] = None

    def _think(self, *args, **kwargs) -> str:
        return "Thought: Proceeding with planned task."

    def _should_replan(self, *args, **kwargs) -> bool:
        return False

    def _verify_artifact_content(self, *args, **kwargs) -> None:
        pass

    def _resolve_placeholders(self, val: Any, context: dict) -> Any:
        """Recursively resolve $placeholder tokens from context."""
        if isinstance(val, str):
            for placeholder, ctx_key in {
                "$last_spreadsheet_id":     "last_spreadsheet_id",
                "$last_spreadsheet_url":    "last_spreadsheet_url",
                "$last_document_id":        "last_document_id",
                "$last_document_url":       "last_document_url",
                "$gmail_message_body":      "gmail_message_body",
                "$gmail_summary_values":    "gmail_summary_values",
                "$drive_summary_values":    "drive_summary_values",
                "$web_search_markdown":     "web_search_markdown",
                "$web_search_table_values": "web_search_table_values",
                "$sheet_email_body":        "sheet_email_body",
            }.items():
                if placeholder in val and ctx_key in context:
                    val = val.replace(placeholder, str(context[ctx_key]))
            return val
        elif isinstance(val, list):
            return [self._resolve_placeholders(item, context) for item in val]
        elif isinstance(val, dict):
            return {k: self._resolve_placeholders(v, context) for k, v in val.items()}
        return val

    def _update_context_from_result(self, data: dict, context: dict) -> None:
        """Extract known artifact keys from a task result and store in context."""
        if "spreadsheetId" in data:
            context["last_spreadsheet_id"] = data["spreadsheetId"]
        if "spreadsheetUrl" in data:
            context["last_spreadsheet_url"] = data["spreadsheetUrl"]
        if "documentId" in data:
            context["last_document_id"] = data["documentId"]
            context["last_document_url"] = (
                f"https://docs.google.com/document/d/{data['documentId']}/edit"
            )
        if "messages" in data:
            msgs = data["messages"]
            if msgs and isinstance(msgs, list):
                context["gmail_message_body"] = msgs[0].get("id", "")
                context["gmail_summary_values"] = [
                    [m.get("id", ""), m.get("threadId", "")] for m in msgs
                ]
        if "files" in data:
            files = data["files"]
            if files and isinstance(files, list):
                context["drive_summary_values"] = [
                    [f.get("name", ""), f.get("mimeType", ""), f.get("webViewLink", "")]
                    for f in files
                ]
        if "values" in data and "range" in data:
            rows = data["values"]
            lines = [" | ".join(str(c) for c in row) for row in rows]
            context["sheet_email_body"] = "\n".join(lines)

    def _handle_web_search_task(self, task: Any, context: dict) -> Any:
        """Execute a web search task and populate context with results."""
        from .models import ExecutionResult
        try:
            from .tools.web_search import web_search_tool
            query = task.parameters.get("query", "")
            result_data = web_search_tool.invoke({"query": query})
            results = result_data.get("results", [])

            markdown_lines = []
            table_values = [["Title", "Content", "Link"]]
            for r in results:
                title   = r.get("title", "")
                content = r.get("content", "")
                link    = r.get("link", "")
                markdown_lines.append(f"## {title}\n{content}\n{link}")
                table_values.append([title, content, link])

            context["web_search_markdown"]    = "\n\n".join(markdown_lines)
            context["web_search_table_values"] = table_values

            return ExecutionResult(
                success=True,
                command=["web_search", query],
                stdout=json.dumps(result_data),
            )
        except Exception as exc:
            from .models import ExecutionResult
            return ExecutionResult(success=False, command=["web_search"], error=str(exc))

    def _maybe_inject_artifact_links(
        self, task: Any, context: dict, result: Any
    ) -> None:
        """Rebuild the sent email MIME to include doc/sheet URLs from context."""
        body      = task.parameters.get("body", "")
        doc_url   = context.get("last_document_url", "")
        sheet_url = context.get("last_spreadsheet_url", "")

        if not doc_url and not sheet_url:
            return

        links = []
        if doc_url:
            links.append(f"Google Doc: {doc_url}")
        if sheet_url:
            links.append(f"Google Sheet: {sheet_url}")

        full_body = f"{body}\n\n" + "\n".join(links)
        to_email  = task.parameters.get("to_email", "")
        subject   = task.parameters.get("subject", "")

        new_params = dict(task.parameters)
        new_params["body"] = full_body
        new_args = self.planner.build_command(task.service, task.action, new_params)
        patched  = self.runner.run(new_args)
        result.stdout  = patched.stdout
        result.success = patched.success

    def execute(self, plan: Any) -> Any:
        from .models import PlanExecutionReport, TaskExecution
        executions = []
        context: dict = {}

        for task in plan.tasks:
            # Resolve all placeholders before execution
            task.parameters = self._resolve_placeholders(task.parameters, context)

            # Web search tasks handled internally
            if task.service == "search" and task.action == "web_search":
                result = self._handle_web_search_task(task, context)
                executions.append(TaskExecution(task=task, result=result))
                continue

            result = self.execute_single_task(task, context)

            try:
                data = json.loads(result.stdout)
                self._update_context_from_result(data, context)
            except Exception:
                pass

            if task.service == "gmail" and task.action == "send_message":
                self._maybe_inject_artifact_links(task, context, result)

            executions.append(TaskExecution(task=task, result=result))

        return PlanExecutionReport(plan=plan, executions=executions)

    def execute_single_task(self, task: Any, context: Any) -> Any:
        args = self.planner.build_command(task.service, task.action, task.parameters)
        return self.runner.run(args)


@dataclass
class SearchToSheetsWorkflow:
    """Search the web and save results to a Google Sheet via the GWS runner."""
    runner: Any
    planner: Any

    def execute(self, query: str, title: str = "Search Results") -> bool:
        if not query or not isinstance(query, str):
            logger.error("Invalid query provided: %s", query)
            raise ValueError("Query must be a non-empty string.")

        logger.info("Starting SearchToSheetsWorkflow for query: %s", query)
        try:
            from .tools.web_search import web_search_tool
            result_data = web_search_tool.invoke({"query": query})
            results     = result_data.get("results", [])

            if not results:
                logger.warning("No results found for query: %s", query)
                return False

            rows = [
                [r.get("title", ""), r.get("content", ""), r.get("link", "")]
                for r in results
            ]

            create_args = self.planner.build_command(
                "sheets", "create_spreadsheet", {"title": title}
            )
            create_result  = self.runner.run(create_args)
            sheet_data     = json.loads(create_result.stdout)
            spreadsheet_id = sheet_data["spreadsheetId"]

            values      = [["Title", "Description", "Link"]] + rows
            append_args = self.planner.build_command(
                "sheets", "append_values",
                {"spreadsheet_id": spreadsheet_id, "range": "Sheet1!A1", "values": values},
            )
            self.runner.run(append_args)

            logger.info(
                "Successfully created spreadsheet '%s' with %d rows.", title, len(rows)
            )
            return True
        except Exception as exc:
            logger.error(
                "SearchToSheetsWorkflow failed for query '%s': %s", query, str(exc),
                exc_info=True,
            )
            raise


@dataclass
class DriveToGmailWorkflow:
    """Search Google Drive for a file and send its content via Gmail."""
    runner: Any
    planner: Any

    def execute(self, query: str, email: str) -> bool:
        logger.info(
            "Starting DriveToGmailWorkflow for query: %s, email: %s", query, email
        )
        try:
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                raise ValueError("Invalid email address")

            list_args   = self.planner.build_command(
                "drive", "list_files", {"q": query}
            )
            list_result = self.runner.run(list_args)
            file_data   = json.loads(list_result.stdout)
            files       = file_data.get("files", [])

            if not files:
                raise FileNotFoundError(f"No file found for query: {query}")

            file_info = files[0]
            file_id   = file_info["id"]
            file_name = file_info.get("name", "Document")

            export_args   = self.planner.build_command(
                "drive", "export_file",
                {"file_id": file_id, "mime_type": "text/plain"},
            )
            export_result = self.runner.run(export_args)
            content       = export_result.stdout or f"(Could not read content of {file_name})"

            send_args = self.planner.build_command(
                "gmail", "send_message",
                {"to_email": email, "subject": f"Document: {file_name}", "body": content},
            )
            self.runner.run(send_args)

            logger.info("Successfully sent document '%s' to %s", file_name, email)
            return True
        except Exception as exc:
            logger.error(
                "DriveToGmailWorkflow failed for query '%s': %s", query, str(exc)
            )
            raise
