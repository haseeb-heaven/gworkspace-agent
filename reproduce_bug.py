import logging
from unittest.mock import MagicMock

from gws_assistant.langgraph_workflow import create_workflow
from gws_assistant.models import AppConfigModel, RequestPlan


def test_empty_executions_no_memory_pollution():
    logger = logging.getLogger("test")
    system = MagicMock()
    executor = MagicMock()

    # Mock system.memory to track calls
    system.memory = MagicMock()

    config = AppConfigModel(
        provider="openai",
        model="gpt-4.1-mini",
        api_key="sk-test",
        llm_fallback_models=[],
        base_url=None,
        timeout_seconds=30,
        gws_binary_path="gws",
        log_file_path="l.log",
        log_level="INFO",
        verbose=True,
        env_file_path=".env",
        setup_complete=True,
        max_retries=3,
        langchain_enabled=True,
        use_heuristic_fallback=False,
        code_execution_enabled=True,
    )

    app = create_workflow(config, system, executor, logger)

    # Scenario: GWS intent but planner produced 0 tasks.
    # route_after_plan will go to format_output.

    # Initial state for format_output_node
    state = {
        "user_text": "search my emails",
        "plan": RequestPlan(raw_text="search my emails", tasks=[], no_service_detected=False),
        "executions": [],
        "context": {},
        "conversation_history": [],
        "thought_trace": [],
        "final_output": "No tasks were executed."
    }

    # Mocking internal components for create_workflow if needed.
    system.plan.return_value = RequestPlan(raw_text="search my emails", tasks=[], no_service_detected=False)

    # Let's run it.
    app.invoke(state)

    # Check if system.memory.add was called
    # With the fix, it SHOULD NOT be called.
    assert not system.memory.add.called, "Fix failed: system.memory.add was called for empty executions!"

if __name__ == "__main__":
    try:
        test_empty_executions_no_memory_pollution()
        print("Test passed: Bug fixed (memory.add was NOT called)")
    except AssertionError as e:
        print(f"Test failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
