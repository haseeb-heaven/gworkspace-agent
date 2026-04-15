import pytest
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
        if args[:4] == ["gmail", "users", "messages", "list"]:
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout='{"messages":[{"id":"m1","threadId":"t1"}],"resultSizeEstimate":1}',
            )
        if args[:4] == ["gmail", "users", "messages", "get"]:
            return ExecutionResult(
                success=True,
                command=["gws.exe", *args],
                stdout='{"id":"m1","payload":{"headers":[{"name":"Subject","value":"Test"}]}}',
            )
        return ExecutionResult(success=True, command=["gws.exe", *args], stdout='{}')

def test_get_message_placeholder_resolution():
    runner = FakeRunner()
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))
    
    # Simulate a plan where message_id is NOT provided in parameters, 
    # so CommandPlanner.build_command will insert "{{message_id}}"
    plan = RequestPlan(
        raw_text="search and get",
        tasks=[
            PlannedTask(id="task-1", service="gmail", action="list_messages", parameters={"q": "test"}),
            PlannedTask(id="task-2", service="gmail", action="get_message", parameters={}),
        ],
    )
    
    report = executor.execute(plan)
    assert report.success is True
    
    # Check the second command (get_message)
    get_cmd = runner.commands[1]
    params_str = get_cmd[get_cmd.index("--params") + 1]
    params = json.loads(params_str)
    
    # This is what we WANT: it should be "m1", not "{{message_id}}"
    assert params["id"] == "m1", f"Expected 'm1', but got '{params['id']}'"

if __name__ == "__main__":
    test_get_message_placeholder_resolution()
