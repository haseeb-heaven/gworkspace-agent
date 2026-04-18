import pytest
import logging
import time
from pathlib import Path
from gws_assistant.execution import PlanExecutor
from gws_assistant.planner import CommandPlanner
from gws_assistant.models import RequestPlan, PlannedTask, ExecutionResult
from gws_assistant.gws_runner import GWSRunner

class TripleCheckRunner(GWSRunner):
    def __init__(self):
        super().__init__(Path("gws"), logging.getLogger("test"))
        self.commands = []
        self.get_count = 0

    def run(self, args, timeout_seconds=90):
        self.commands.append(args)
        if "create" in args or "insert" in args:
            if "spreadsheets" in args:
                return ExecutionResult(success=True, command=args, stdout='{"spreadsheetId": "sheet-1"}')
            if "documents" in args:
                return ExecutionResult(success=True, command=args, stdout='{"documentId": "doc-1"}')
            if "files" in args:
                return ExecutionResult(success=True, command=args, stdout='{"id": "file-1"}')
            if "events" in args:
                return ExecutionResult(success=True, command=args, stdout='{"id": "event-1"}')
        
        if "get" in args:
            self.get_count += 1
            return ExecutionResult(success=True, command=args, stdout='{"status": "ok"}')
            
        return ExecutionResult(success=True, command=args, stdout='{}')

def test_triple_check_on_create_spreadsheet(mocker):
    sleep_mock = mocker.patch("time.sleep") # Don't actually sleep
    runner = TripleCheckRunner()
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
    
    plan = RequestPlan(
        raw_text="create sheet",
        tasks=[
            PlannedTask(id="t1", service="sheets", action="create_spreadsheet", parameters={"title": "Test"})
        ]
    )
    
    executor.execute(plan)
    
    # After 1 create, we expect 3 get calls for verification
    # commands: [create, get, get, get]
    assert runner.get_count == 3
    
    # Check increasing delays
    from unittest.mock import call
    calls = [call(0), call(2), call(4)]
    sleep_mock.assert_has_calls(calls)

def test_triple_check_fails_if_get_fails(mocker):
    mocker.patch("time.sleep")
    runner = TripleCheckRunner()
    
    # Make the 2nd GET fail
    def side_effect(args, timeout_seconds=90):
        runner.commands.append(args)
        if "create" in args:
            return ExecutionResult(success=True, command=args, stdout='{"spreadsheetId": "sheet-1"}')
        if "get" in args:
            runner.get_count += 1
            if runner.get_count == 2:
                return ExecutionResult(success=False, command=args, error="Not found yet")
            return ExecutionResult(success=True, command=args, stdout='{"status": "ok"}')
        return ExecutionResult(success=True, command=args, stdout='{}')
    
    runner.run = side_effect
    
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
    
    plan = RequestPlan(
        raw_text="create sheet",
        tasks=[
            PlannedTask(id="t1", service="sheets", action="create_spreadsheet", parameters={"title": "Test"})
        ]
    )
    
    report = executor.execute(plan)
    
    assert report.success is False
    assert runner.get_count == 2 # Stopped after second fail

def test_triple_check_on_create_document(mocker):
    mocker.patch("time.sleep")
    runner = TripleCheckRunner()
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
    
    plan = RequestPlan(
        raw_text="create doc",
        tasks=[
            PlannedTask(id="t1", service="docs", action="create_document", parameters={"title": "Test Doc"})
        ]
    )
    
    executor.execute(plan)
    assert runner.get_count == 3

def test_triple_check_on_create_file(mocker):
    mocker.patch("time.sleep")
    runner = TripleCheckRunner()
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
    
    plan = RequestPlan(
        raw_text="create file",
        tasks=[
            PlannedTask(id="t1", service="drive", action="create_file", parameters={"name": "Test File"})
        ]
    )
    
    executor.execute(plan)
    assert runner.get_count == 3

def test_triple_check_on_insert_event(mocker):
    mocker.patch("time.sleep")
    runner = TripleCheckRunner()
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
    
    plan = RequestPlan(
        raw_text="insert event",
        tasks=[
            PlannedTask(id="t1", service="calendar", action="insert_event", parameters={"summary": "Meeting"})
        ]
    )
    
    executor.execute(plan)
    assert runner.get_count == 3
