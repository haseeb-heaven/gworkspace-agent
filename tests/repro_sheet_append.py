import json
import logging
from pathlib import Path
from gws_assistant.execution import PlanExecutor
from gws_assistant.gws_runner import GWSRunner
from gws_assistant.models import ExecutionResult, PlannedTask, RequestPlan
from gws_assistant.planner import CommandPlanner

class FakeRunner(GWSRunner):
    def __init__(self) -> None:
        super().__init__(Path("gws.exe"), logging.getLogger("test"))
        self.commands: list[list[str]] = []

    def run(self, args: list[str], timeout_seconds: int = 90) -> ExecutionResult:
        self.commands.append(args)
        if args[:4] == ["code", "execute", "internal", "--json"]:
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout="",
                output={"parsed_value": [["Sender", "Subject", "Date"], ["test@example.com", "Test Subject", "2026-04-15"]]}
            )
        if args[:4] == ["sheets", "spreadsheets", "values", "append"]:
            return ExecutionResult(success=True, command=["gws.exe", *args], stdout='{}')
        return ExecutionResult(success=True, command=["gws.exe", *args], stdout='{}')

def test_sheet_append_list_placeholder():
    runner = FakeRunner()
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
    
    plan = RequestPlan(
        raw_text="extract and append",
        tasks=[
            PlannedTask(id="task-1", service="code", action="execute", parameters={"code": "print([['a','b']])"}),
            PlannedTask(id="task-2", service="sheets", action="append_values", parameters={"spreadsheet_id": "sid123", "values": "{{task-1.parsed_value}}"}),
        ],
    )
    
    report = executor.execute(plan)
    assert report.success is True
    
    # Check that append_values was called with a list, not a string of a list
    append_cmd = runner.commands[1]
    json_str = append_cmd[append_cmd.index("--json") + 1]
    data = json.loads(json_str)
    
    expected_values = [["Sender", "Subject", "Date"], ["test@example.com", "Test Subject", "2026-04-15"]]
    assert data["values"] == expected_values, f"Expected values to be a list, but got {type(data['values'])}"

if __name__ == "__main__":
    test_sheet_append_list_placeholder()
