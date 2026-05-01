import os

import pytest

from framework.task_runner import TaskRunner


@pytest.fixture
def runner():
    return TaskRunner()


@pytest.mark.live_integration
def test_search_and_email(runner, default_email):
    query = os.getenv("TEST_WEB_SEARCH_QUERY", "Agentic AI Google Workspace")
    success = runner.execute_and_validate(
        task=f"Web search for '{query}' and email the top results to {default_email}",
        expected_texts=["completed"],
    )
    assert success
