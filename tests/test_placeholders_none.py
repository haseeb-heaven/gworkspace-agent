
import logging
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from gws_assistant.execution import PlanExecutor


def test_none_resolution():
    logging.basicConfig(level=logging.DEBUG)
    executor = PlanExecutor(planner=None, runner=None)

    context = {
        "task_results": {
            "task-1": {"id": None, "value": "foo"},
            "task-2": {"content": "None"}
        },
        "last_code_result": None
    }

    # Case 1: Resolved value is None
    res1 = executor._resolve_placeholders("{task-1.id}", context)
    print(f"Case 1 (None value): {{task-1.id}} -> {res1}")

    # Case 2: Resolved value is string "None"
    res2 = executor._resolve_placeholders("{task-2.content}", context)
    print(f"Case 2 (String 'None'): {{task-2.content}} -> {res2}")

    # Case 3: Unresolved placeholder
    res3 = executor._resolve_placeholders("{task-99.id}", context)
    print(f"Case 3 (Unresolved): {{task-99.id}} -> {res3}")

    # Case 4: Scalar None in context
    res4 = executor._resolve_placeholders("$last_code_result", context)
    print(f"Case 4 (Scalar None): $last_code_result -> {res4}")

if __name__ == "__main__":
    test_none_resolution()
