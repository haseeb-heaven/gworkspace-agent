from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pytest

from gws_assistant.execution import PlanExecutor
from gws_assistant.models import PlannedTask, RequestPlan, ExecutionResult
from gws_assistant.planner import CommandPlanner
from gws_assistant.gws_runner import GWSRunner

class FakeRunner(GWSRunner):
    def __init__(self) -> None:
        super().__init__(Path("gws"), logging.getLogger("test"))
        self.commands: list[list[str]] = []

    def run(self, args: list[str], timeout_seconds: int = 90) -> ExecutionResult:
        self.commands.append(args)
        
        if args[:3] == ["sheets", "spreadsheets", "create"]:
            return ExecutionResult(
                success=True,
                command=args,
                stdout=json.dumps({
                    "spreadsheetId": "sheet-123",
                    "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/sheet-123/edit",
                    "title": "Test Sheet"
                })
            )
        
        if args[:3] == ["sheets", "spreadsheets", "get"]:
            return ExecutionResult(
                success=True,
                command=args,
                stdout=json.dumps({
                    "spreadsheetId": "sheet-123",
                    "title": "Test Sheet"
                })
            )
            
        if args[:4] == ["sheets", "spreadsheets", "values", "append"]:
            return ExecutionResult(
                success=True,
                command=args,
                stdout=json.dumps({"updates": {"updatedRows": 1}})
            )
            
        if args[:2] == ["sheets", "+read"]:
            return ExecutionResult(
                success=True,
                command=args,
                stdout=json.dumps({"values": [["Data1", "Data2"]]})
            )
            
        if args[:4] == ["sheets", "spreadsheets", "values", "clear"]:
            return ExecutionResult(
                success=True,
                command=args,
                stdout=json.dumps({"spreadsheetId": "sheet-123", "clearedRange": "Sheet1!A1:Z100"})
            )
            
        if args[:3] == ["drive", "files", "delete"]:
            return ExecutionResult(
                success=True,
                command=args,
                stdout=""
            )
            
        return ExecutionResult(success=True, command=args, stdout="{}")

@pytest.fixture(autouse=True)
def mock_react(mocker):
    mocker.patch("gws_assistant.execution.PlanExecutor._think", return_value="Thought")
    mocker.patch("gws_assistant.execution.PlanExecutor._should_replan", return_value=False)
    mocker.patch("gws_assistant.execution.PlanExecutor.verify_resource", return_value=True)

def test_sheets_lifecycle_crud():
    runner = FakeRunner()
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
    
    plan = RequestPlan(
        raw_text="Sheet lifecycle test",
        tasks=[
            # 1. Create
            PlannedTask(id="t1", service="sheets", action="create_spreadsheet", parameters={"title": "Lifecycle Test"}),
            # 2. Append
            PlannedTask(id="t2", service="sheets", action="append_values", 
                        parameters={"spreadsheet_id": "$last_spreadsheet_id", "values": [["A", "B"]]}),
            # 3. Get
            PlannedTask(id="t3", service="sheets", action="get_values", 
                        parameters={"spreadsheet_id": "$last_spreadsheet_id", "range": "Sheet1!A1:B1"}),
            # 4. Clear
            PlannedTask(id="t4", service="sheets", action="clear_values", 
                        parameters={"spreadsheet_id": "$last_spreadsheet_id", "range": "Sheet1!A1:B1"}),
            # 5. Delete
            PlannedTask(id="t5", service="sheets", action="delete_spreadsheet", 
                        parameters={"spreadsheet_id": "$last_spreadsheet_id"}),
        ]
    )
    
    report = executor.execute(plan)
    
    assert report.success is True
    assert len(runner.commands) == 5
    
    assert runner.commands[0][:3] == ["sheets", "spreadsheets", "create"]
    assert runner.commands[1][:4] == ["sheets", "spreadsheets", "values", "append"]
    assert runner.commands[2][:2] == ["sheets", "+read"]
    assert runner.commands[3][:4] == ["sheets", "spreadsheets", "values", "clear"]
    assert runner.commands[4][:3] == ["drive", "files", "delete"]
    
    # Verify spreadsheet_id was resolved correctly for clear and delete
    assert '"spreadsheetId": "sheet-123"' in runner.commands[3][runner.commands[3].index("--params") + 1]
    assert '"fileId": "sheet-123"' in runner.commands[4][runner.commands[4].index("--params") + 1]
