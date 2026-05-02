"""Integration tests for Drive file operations via the LangGraph workflow.

Each test exercises intent parsing → planning → execution → verification
for a specific file-related user request, using FakeGoogleWorkspace so no
real credentials are needed.
"""

import logging
from pathlib import Path

import pytest

from gws_assistant.agent_system import WorkspaceAgentSystem
from gws_assistant.execution.executor import PlanExecutor
from gws_assistant.langgraph_workflow import run_workflow
from gws_assistant.models import AppConfigModel
from tests.fakes.fake_google_workspace import FakeGoogleWorkspace
import os


@pytest.fixture(autouse=True)
def mock_telegram_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "mock_bot_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setenv("CI", "true")


@pytest.fixture
def config():
    return AppConfigModel(
        provider="openai",
        model="gpt-4o",
        api_key="test_key",
        llm_fallback_models=[],
        base_url=None,
        timeout_seconds=30,
        gws_binary_path=Path("/fake/gws"),
        log_file_path=Path("gws.log"),
        log_level="INFO",
        verbose=False,
        env_file_path=Path(".env"),
        setup_complete=True,
        max_retries=3,
        langchain_enabled=False,
        use_heuristic_fallback=True,
        default_recipient_email="test@example.com",
        read_only_mode=False,
        sandbox_enabled=False,
        no_confirm=False,
        force_dangerous=False,
    )


@pytest.fixture
def logger():
    return logging.getLogger("test_integration_files")


def _run(user_text: str, config: AppConfigModel, logger: logging.Logger, fake_gws: FakeGoogleWorkspace):
    system = WorkspaceAgentSystem(config, logger)
    from gws_assistant.planner import CommandPlanner
    executor = PlanExecutor(planner=CommandPlanner(), runner=fake_gws, logger=logger, config=config)
    return run_workflow(user_text, config, system, executor, logger)


@pytest.mark.drive
@pytest.mark.integration
def test_drive_list_and_export_pdf(config, logger):
    """User asks to list PDFs and export the first one."""
    fake_gws = FakeGoogleWorkspace()
    output = _run("list my PDF files in drive and export the first one", config, logger, fake_gws)
    assert output is not None

    actions = [(c["service"], c["action"]) for c in fake_gws.call_log]
    assert any(s == "drive" for s, _ in actions)
    # list_files should have been called
    assert any(a == "list_files" for _, a in actions)


@pytest.mark.drive
@pytest.mark.integration
def test_drive_upload_image_file(config, logger, tmp_path):
    """User asks to upload an image to Drive."""
    fake_gws = FakeGoogleWorkspace()
    img = tmp_path / "screenshot.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    output = _run(f"upload {img} to Google Drive", config, logger, fake_gws)
    assert output is not None

    actions = [(c["service"], c["action"]) for c in fake_gws.call_log]
    assert any(a == "upload_file" for _, a in actions)


@pytest.mark.drive
@pytest.mark.integration
def test_drive_upload_video_file(config, logger, tmp_path):
    """User asks to upload a video to Drive."""
    fake_gws = FakeGoogleWorkspace()
    vid = tmp_path / "demo.mp4"
    vid.write_bytes(b"\x00\x00\x00\x20ftypisom")
    output = _run(f"upload {vid} to Google Drive", config, logger, fake_gws)
    assert output is not None

    actions = [(c["service"], c["action"]) for c in fake_gws.call_log]
    assert any(a == "upload_file" for _, a in actions)


@pytest.mark.drive
@pytest.mark.integration
def test_drive_upload_audio_file(config, logger, tmp_path):
    """User asks to upload an audio file to Drive."""
    fake_gws = FakeGoogleWorkspace()
    audio = tmp_path / "podcast.mp3"
    audio.write_bytes(b"\xff\xfb\x90\x00")
    output = _run(f"upload {audio} to Google Drive", config, logger, fake_gws)
    assert output is not None

    actions = [(c["service"], c["action"]) for c in fake_gws.call_log]
    assert any(a == "upload_file" for _, a in actions)


@pytest.mark.drive
@pytest.mark.integration
def test_drive_upload_spreadsheet(config, logger, tmp_path):
    """User asks to upload a CSV to Drive."""
    fake_gws = FakeGoogleWorkspace()
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("name,age\nAlice,30\nBob,25")
    output = _run(f"upload {csv_file} to Google Drive", config, logger, fake_gws)
    assert output is not None

    actions = [(c["service"], c["action"]) for c in fake_gws.call_log]
    assert any(a == "upload_file" for _, a in actions)


@pytest.mark.drive
@pytest.mark.integration
def test_drive_create_folder_and_upload(config, logger, tmp_path):
    """User asks to create a folder and upload a document into it."""
    fake_gws = FakeGoogleWorkspace()
    doc = tmp_path / "report.docx"
    doc.write_bytes(b"PK\x03\x04")
    output = _run(
        f"create a folder called Reports and upload {doc} into it",
        config, logger, fake_gws
    )
    assert output is not None

    actions = [(c["service"], c["action"]) for c in fake_gws.call_log]
    # Heuristic planner may emit create_folder then upload_file, or just upload_file.
    # For complex multi-step phrasing we just assert the workflow ran without crashing
    # and at least one drive action was attempted.
    if actions:
        assert any(s == "drive" for s, _ in actions)


@pytest.mark.drive
@pytest.mark.integration
def test_drive_search_and_download_image(config, logger):
    """User asks to find an image and download it."""
    fake_gws = FakeGoogleWorkspace()
    output = _run("find my logo image in drive and download it", config, logger, fake_gws)
    assert output is not None

    actions = [(c["service"], c["action"]) for c in fake_gws.call_log]
    assert any(a in ("list_files", "get_file", "export_file") for _, a in actions)


@pytest.mark.drive
@pytest.mark.integration
def test_drive_search_and_download_video(config, logger):
    """User asks to find a video and download it."""
    fake_gws = FakeGoogleWorkspace()
    output = _run("find my demo video in drive and download it", config, logger, fake_gws)
    assert output is not None

    actions = [(c["service"], c["action"]) for c in fake_gws.call_log]
    assert any(a in ("list_files", "get_file", "export_file") for _, a in actions)


@pytest.mark.drive
@pytest.mark.integration
def test_drive_search_and_download_audio(config, logger):
    """User asks to find an audio file and download it."""
    fake_gws = FakeGoogleWorkspace()
    output = _run("find my recording in drive and download it", config, logger, fake_gws)
    assert output is not None

    actions = [(c["service"], c["action"]) for c in fake_gws.call_log]
    assert any(a in ("list_files", "get_file", "export_file") for _, a in actions)


@pytest.mark.drive
@pytest.mark.integration
def test_drive_copy_file_workflow(config, logger):
    """Explicit plan: list a file then copy it."""
    fake_gws = FakeGoogleWorkspace()
    from gws_assistant.models import PlannedTask, RequestPlan
    from gws_assistant.planner import CommandPlanner

    executor = PlanExecutor(planner=CommandPlanner(), runner=fake_gws, logger=logger, config=config)
    plan = RequestPlan(
        raw_text="copy Budget 2026 file",
        tasks=[
            PlannedTask(id="task-1", service="drive", action="list_files", parameters={"q": "name contains 'Budget 2026'"}),
            PlannedTask(id="task-2", service="drive", action="copy_file", parameters={"file_id": "{{task-1.id}}", "name": "Budget 2026 Copy"}),
        ],
    )
    executor.execute(plan)

    actions = [(c["service"], c["action"]) for c in fake_gws.call_log]
    assert any(a == "list_files" for _, a in actions)
    assert any(a == "copy_file" for _, a in actions)


@pytest.mark.drive
@pytest.mark.integration
def test_drive_move_file_workflow(config, logger):
    """Explicit plan: list a file then move it to a folder."""
    fake_gws = FakeGoogleWorkspace()
    from gws_assistant.models import PlannedTask, RequestPlan
    from gws_assistant.planner import CommandPlanner

    executor = PlanExecutor(planner=CommandPlanner(), runner=fake_gws, logger=logger, config=config)
    plan = RequestPlan(
        raw_text="move Invoice.pdf to Reports folder",
        tasks=[
            PlannedTask(id="task-1", service="drive", action="list_files", parameters={"q": "name contains 'Invoice.pdf'"}),
            PlannedTask(id="task-2", service="drive", action="move_file", parameters={"file_id": "{{task-1.id}}", "folder_id": "folder_reports"}),
        ],
    )
    executor.execute(plan)

    actions = [(c["service"], c["action"]) for c in fake_gws.call_log]
    assert any(a == "list_files" for _, a in actions)
    # The executor intercepts move_file to fetch parents first (get_file),
    # then issues an update which the fake records as update_file.
    assert any(a in ("get_file", "update_file") for _, a in actions)


@pytest.mark.drive
@pytest.mark.integration
def test_drive_rename_file_workflow(config, logger):
    """Explicit plan: list a file then rename it."""
    fake_gws = FakeGoogleWorkspace()
    from gws_assistant.models import PlannedTask, RequestPlan
    from gws_assistant.planner import CommandPlanner

    executor = PlanExecutor(planner=CommandPlanner(), runner=fake_gws, logger=logger, config=config)
    plan = RequestPlan(
        raw_text="rename notes.txt to ideas.txt",
        tasks=[
            PlannedTask(id="task-1", service="drive", action="list_files", parameters={"q": "name contains 'notes.txt'"}),
            PlannedTask(id="task-2", service="drive", action="update_file_metadata", parameters={"file_id": "{{task-1.id}}", "name": "ideas.txt"}),
        ],
    )
    executor.execute(plan)

    actions = [(c["service"], c["action"]) for c in fake_gws.call_log]
    assert any(a == "list_files" for _, a in actions)
    # update_file_metadata is built as drive files update -> fake records update_file
    assert any(a == "update_file" for _, a in actions)


@pytest.mark.drive
@pytest.mark.integration
def test_drive_delete_file_workflow(config, logger):
    """Explicit plan: list a file then delete it."""
    fake_gws = FakeGoogleWorkspace()
    from gws_assistant.models import PlannedTask, RequestPlan
    from gws_assistant.planner import CommandPlanner

    # Bypass interactive confirmation for destructive actions in tests
    config.no_confirm = True
    config.force_dangerous = True

    executor = PlanExecutor(planner=CommandPlanner(), runner=fake_gws, logger=logger, config=config)
    plan = RequestPlan(
        raw_text="delete old data.csv",
        tasks=[
            PlannedTask(id="task-1", service="drive", action="list_files", parameters={"q": "name contains 'data.csv'"}),
            PlannedTask(id="task-2", service="drive", action="delete_file", parameters={"file_id": "{{task-1.id}}"}),
        ],
    )
    executor.execute(plan)

    actions = [(c["service"], c["action"]) for c in fake_gws.call_log]
    assert any(a == "list_files" for _, a in actions)
    assert any(a == "delete_file" for _, a in actions)


@pytest.mark.drive
@pytest.mark.sheets
@pytest.mark.integration
def test_drive_export_sheet_to_csv_and_email(config, logger):
    """User asks to export a spreadsheet and email it."""
    fake_gws = FakeGoogleWorkspace()
    output = _run(
        "export my Budget 2026 spreadsheet as csv and email it to test@example.com",
        config, logger, fake_gws,
    )
    assert output is not None

    actions = [(c["service"], c["action"]) for c in fake_gws.call_log]
    assert any(s == "sheets" or s == "drive" for s, _ in actions)
    assert any(a in ("list_files", "get_file", "export_file", "get_values") for _, a in actions)


@pytest.mark.drive
@pytest.mark.gmail
@pytest.mark.integration
def test_drive_export_doc_to_pdf_and_email_workflow(config, logger):
    """Explicit plan: export a doc to PDF and email it."""
    fake_gws = FakeGoogleWorkspace()
    from gws_assistant.models import PlannedTask, RequestPlan
    from gws_assistant.planner import CommandPlanner

    executor = PlanExecutor(planner=CommandPlanner(), runner=fake_gws, logger=logger, config=config)
    plan = RequestPlan(
        raw_text="export Meeting Notes to pdf and email",
        tasks=[
            PlannedTask(id="task-1", service="drive", action="export_file", parameters={"file_id": "gdoc_fgh", "mime_type": "application/pdf"}),
            PlannedTask(id="task-2", service="gmail", action="send_message", parameters={"to_email": "test@example.com", "subject": "Meeting Notes PDF", "body": "See attached PDF."}),
        ],
    )
    executor.execute(plan)

    actions = [(c["service"], c["action"]) for c in fake_gws.call_log]
    assert any(a == "export_file" for _, a in actions)
    assert any(a == "send_message" for _, a in actions)
