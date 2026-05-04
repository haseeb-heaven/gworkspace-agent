"""Live integration tests for Drive file operations across all supported types.

Requires:
  - RUN_LIVE_INTEGRATION=true
  - GWS_BINARY_PATH pointing to a working gws binary
  - Valid Google Workspace credentials

All created resources are cleaned up after the test run.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from gws_assistant.gws_runner import GWSRunner
from gws_assistant.planner import CommandPlanner


@pytest.fixture(scope="module")
def live_runner() -> GWSRunner | None:
    if os.getenv("RUN_LIVE_INTEGRATION") != "true":
        pytest.skip("RUN_LIVE_INTEGRATION is not enabled.")

    raw_path = os.getenv("GWS_BINARY_PATH")
    if raw_path:
        gws_binary = Path(raw_path).expanduser()
    else:
        found = shutil.which("gws.exe" if os.name == "nt" else "gws")
        if not found:
            pytest.skip("GWS_BINARY_PATH does not exist for live integration run.")
        gws_binary = Path(found)

    import logging
    logger = logging.getLogger("live-file-ops")
    return GWSRunner(gws_binary, logger)


@pytest.fixture(scope="module")
def planner() -> CommandPlanner:
    return CommandPlanner()


@pytest.fixture
def live_tmp_path() -> Path:
    """Return a project-local temp directory for upload files.

    The GWS binary on Windows rejects --upload paths outside the current
    working directory, so we create test files inside the repo instead of
    using pytest's system temp root.
    """
    base = Path(__file__).resolve().parent.parent / "scratch" / "live_test_files"
    base.mkdir(parents=True, exist_ok=True)
    return base


@pytest.fixture(scope="module")
def test_folder_id(live_runner: GWSRunner, planner: CommandPlanner):
    """Create a temporary test folder and yield its ID; delete it after the module."""
    folder_name = "GWS Agent File Test Folder"
    cmd = planner.build_command("drive", "create_folder", {"folder_name": folder_name})
    result = live_runner.run(cmd, timeout_seconds=90)
    assert result.success, f"Failed to create test folder: {result.error or result.stderr}"
    payload = json.loads(result.stdout or "{}")
    folder_id = payload.get("id")
    assert folder_id, f"Missing folder id in response: {payload}"

    yield folder_id

    # Cleanup: delete the folder (and all contents)
    delete_cmd = planner.build_command("drive", "delete_file", {"file_id": folder_id})
    live_runner.run(delete_cmd, timeout_seconds=90)


@pytest.mark.live_integration
def test_live_upload_and_download_pdf(live_runner: GWSRunner, planner: CommandPlanner, test_folder_id: str, live_tmp_path: Path):
    """Upload a PDF and download it back."""
    pdf = live_tmp_path / "test_doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n\ntrailer\n<< /Root 1 0 R >>\n%%EOF")

    upload_cmd = planner.build_command("drive", "upload_file", {"file_path": str(pdf), "name": "test_doc.pdf"})
    upload_res = live_runner.run(upload_cmd, timeout_seconds=90)
    assert upload_res.success, f"Upload failed: {upload_res.error or upload_res.stderr}"
    upload_payload = json.loads(upload_res.stdout or "{}")
    file_id = upload_payload.get("id")
    assert file_id, f"Missing file id in upload response: {upload_payload}"

    # Download
    download_cmd = planner.build_command("drive", "export_file", {"file_id": file_id, "source_mime": "application/pdf"})
    download_res = live_runner.run(download_cmd, timeout_seconds=90)
    assert download_res.success, f"Download failed: {download_res.error or download_res.stderr}"
    download_payload = json.loads(download_res.stdout or "{}")
    saved = download_payload.get("saved_file")
    assert saved and Path(saved).exists(), f"Downloaded file not found: {saved}"

    # Cleanup
    live_runner.run(planner.build_command("drive", "delete_file", {"file_id": file_id}), timeout_seconds=30)


@pytest.mark.live_integration
def test_live_upload_and_download_txt(live_runner: GWSRunner, planner: CommandPlanner, test_folder_id: str, live_tmp_path: Path):
    """Upload a text file and download it back."""
    txt = live_tmp_path / "notes.txt"
    txt.write_text("Hello from live integration test!")

    upload_cmd = planner.build_command("drive", "upload_file", {"file_path": str(txt), "name": "notes.txt"})
    upload_res = live_runner.run(upload_cmd, timeout_seconds=90)
    assert upload_res.success, f"Upload failed: {upload_res.error or upload_res.stderr}"
    upload_payload = json.loads(upload_res.stdout or "{}")
    file_id = upload_payload.get("id")
    assert file_id

    download_cmd = planner.build_command("drive", "export_file", {"file_id": file_id, "source_mime": "text/plain"})
    download_res = live_runner.run(download_cmd, timeout_seconds=90)
    assert download_res.success, f"Download failed: {download_res.error or download_res.stderr}"
    download_payload = json.loads(download_res.stdout or "{}")
    saved = download_payload.get("saved_file")
    assert saved and Path(saved).exists()
    content = Path(saved).read_text(encoding="utf-8")
    assert "Hello from live integration test" in content

    live_runner.run(planner.build_command("drive", "delete_file", {"file_id": file_id}), timeout_seconds=30)


@pytest.mark.live_integration
def test_live_upload_and_download_csv(live_runner: GWSRunner, planner: CommandPlanner, test_folder_id: str, live_tmp_path: Path):
    """Upload a CSV and download it back."""
    csv_file = live_tmp_path / "data.csv"
    csv_file.write_text("name,score\nAlice,100\nBob,95")

    upload_cmd = planner.build_command("drive", "upload_file", {"file_path": str(csv_file), "name": "data.csv"})
    upload_res = live_runner.run(upload_cmd, timeout_seconds=90)
    assert upload_res.success, f"Upload failed: {upload_res.error or upload_res.stderr}"
    upload_payload = json.loads(upload_res.stdout or "{}")
    file_id = upload_payload.get("id")
    assert file_id

    download_cmd = planner.build_command("drive", "export_file", {"file_id": file_id, "source_mime": "text/csv"})
    download_res = live_runner.run(download_cmd, timeout_seconds=90)
    assert download_res.success, f"Download failed: {download_res.error or download_res.stderr}"
    download_payload = json.loads(download_res.stdout or "{}")
    saved = download_payload.get("saved_file")
    assert saved and Path(saved).exists()
    content = Path(saved).read_text(encoding="utf-8")
    assert "Alice,100" in content

    live_runner.run(planner.build_command("drive", "delete_file", {"file_id": file_id}), timeout_seconds=30)


@pytest.mark.live_integration
def test_live_upload_and_download_image_png(live_runner: GWSRunner, planner: CommandPlanner, test_folder_id: str, live_tmp_path: Path):
    """Upload a PNG image and download it back."""
    img = live_tmp_path / "test_image.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x00\x00\x00\x01\x01\x00\x05\xfe\x02\xfe\x00\x00\x00\x00IEND\xaeB`\x82")

    upload_cmd = planner.build_command("drive", "upload_file", {"file_path": str(img), "name": "test_image.png"})
    upload_res = live_runner.run(upload_cmd, timeout_seconds=90)
    assert upload_res.success, f"Upload failed: {upload_res.error or upload_res.stderr}"
    upload_payload = json.loads(upload_res.stdout or "{}")
    file_id = upload_payload.get("id")
    assert file_id
    assert upload_payload.get("mimeType") == "image/png"

    download_cmd = planner.build_command("drive", "export_file", {"file_id": file_id, "source_mime": "image/png"})
    download_res = live_runner.run(download_cmd, timeout_seconds=90)
    assert download_res.success, f"Download failed: {download_res.error or download_res.stderr}"
    download_payload = json.loads(download_res.stdout or "{}")
    saved = download_payload.get("saved_file")
    assert saved and Path(saved).exists()
    downloaded_bytes = Path(saved).read_bytes()
    assert downloaded_bytes[:4] == b"\x89PNG"

    live_runner.run(planner.build_command("drive", "delete_file", {"file_id": file_id}), timeout_seconds=30)


@pytest.mark.live_integration
def test_live_upload_and_download_mp4(live_runner: GWSRunner, planner: CommandPlanner, test_folder_id: str, live_tmp_path: Path):
    """Upload a minimal MP4 video and download it back."""
    vid = live_tmp_path / "test_video.mp4"
    # Minimal valid MP4 header (ftyp box)
    vid.write_bytes(b"\x00\x00\x00\x20ftypisom\x00\x00\x00\x00isommp41\x00\x00\x00\x00")

    upload_cmd = planner.build_command("drive", "upload_file", {"file_path": str(vid), "name": "test_video.mp4"})
    upload_res = live_runner.run(upload_cmd, timeout_seconds=90)
    assert upload_res.success, f"Upload failed: {upload_res.error or upload_res.stderr}"
    upload_payload = json.loads(upload_res.stdout or "{}")
    file_id = upload_payload.get("id")
    assert file_id
    assert upload_payload.get("mimeType") == "video/mp4"

    download_cmd = planner.build_command("drive", "export_file", {"file_id": file_id, "source_mime": "video/mp4"})
    download_res = live_runner.run(download_cmd, timeout_seconds=90)
    assert download_res.success, f"Download failed: {download_res.error or download_res.stderr}"
    download_payload = json.loads(download_res.stdout or "{}")
    saved = download_payload.get("saved_file")
    assert saved and Path(saved).exists()

    live_runner.run(planner.build_command("drive", "delete_file", {"file_id": file_id}), timeout_seconds=30)


@pytest.mark.live_integration
def test_live_upload_and_download_mp3(live_runner: GWSRunner, planner: CommandPlanner, test_folder_id: str, live_tmp_path: Path):
    """Upload a minimal MP3 audio file and download it back."""
    audio = live_tmp_path / "test_audio.mp3"
    # Minimal MP3 frame header
    audio.write_bytes(b"\xff\xfb\x90\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")

    upload_cmd = planner.build_command("drive", "upload_file", {"file_path": str(audio), "name": "test_audio.mp3"})
    upload_res = live_runner.run(upload_cmd, timeout_seconds=90)
    assert upload_res.success, f"Upload failed: {upload_res.error or upload_res.stderr}"
    upload_payload = json.loads(upload_res.stdout or "{}")
    file_id = upload_payload.get("id")
    assert file_id
    assert upload_payload.get("mimeType") == "audio/mpeg"

    download_cmd = planner.build_command("drive", "export_file", {"file_id": file_id, "source_mime": "audio/mpeg"})
    download_res = live_runner.run(download_cmd, timeout_seconds=90)
    assert download_res.success, f"Download failed: {download_res.error or download_res.stderr}"
    download_payload = json.loads(download_res.stdout or "{}")
    saved = download_payload.get("saved_file")
    assert saved and Path(saved).exists()

    live_runner.run(planner.build_command("drive", "delete_file", {"file_id": file_id}), timeout_seconds=30)


@pytest.mark.live_integration
def test_live_copy_rename_move_trash(live_runner: GWSRunner, planner: CommandPlanner, test_folder_id: str, live_tmp_path: Path):
    """Upload a file, copy it, rename the copy, move it, then trash it."""
    txt = live_tmp_path / "lifecycle.txt"
    txt.write_text("lifecycle test")

    # Upload
    upload_res = live_runner.run(
        planner.build_command("drive", "upload_file", {"file_path": str(txt), "name": "lifecycle.txt"}),
        timeout_seconds=90,
    )
    assert upload_res.success
    file_id = json.loads(upload_res.stdout or "{}").get("id")
    assert file_id

    # Copy
    copy_res = live_runner.run(
        planner.build_command("drive", "copy_file", {"file_id": file_id, "name": "lifecycle_copy.txt"}),
        timeout_seconds=90,
    )
    assert copy_res.success, f"Copy failed: {copy_res.error or copy_res.stderr}"
    copy_payload = json.loads(copy_res.stdout or "{}")
    copy_id = copy_payload.get("id")
    assert copy_id

    # Rename copy
    rename_res = live_runner.run(
        planner.build_command("drive", "update_file_metadata", {"file_id": copy_id, "name": "renamed_lifecycle.txt"}),
        timeout_seconds=90,
    )
    assert rename_res.success, f"Rename failed: {rename_res.error or rename_res.stderr}"

    # Move copy to test folder
    # The planner emits a placeholder for removeParents that the executor resolves.
    # In a direct runner call we must fetch the current parents first.
    get_res = live_runner.run(
        planner.build_command("drive", "get_file", {"file_id": copy_id}),
        timeout_seconds=90,
    )
    assert get_res.success, f"Get parents failed: {get_res.error or get_res.stderr}"
    get_payload = json.loads(get_res.stdout or "{}")
    current_parents = get_payload.get("parents", [])
    remove_parents = current_parents[0] if current_parents else ""

    move_cmd = [
        "drive", "files", "update",
        "--params", json.dumps({
            "fileId": copy_id,
            "addParents": test_folder_id,
            "removeParents": remove_parents,
        }),
    ]
    move_res = live_runner.run(move_cmd, timeout_seconds=90)
    assert move_res.success, f"Move failed: {move_res.error or move_res.stderr}"

    # Trash original
    trash_res = live_runner.run(
        planner.build_command("drive", "move_to_trash", {"file_id": file_id}),
        timeout_seconds=90,
    )
    assert trash_res.success, f"Trash failed: {trash_res.error or trash_res.stderr}"

    # Cleanup: permanently delete copy from test folder
    live_runner.run(planner.build_command("drive", "delete_file", {"file_id": copy_id}), timeout_seconds=30)
    # Cleanup: permanently delete original (already trashed, but try anyway)
    live_runner.run(planner.build_command("drive", "delete_file", {"file_id": file_id}), timeout_seconds=30)


@pytest.mark.live_integration
def test_live_create_google_doc_and_export(live_runner: GWSRunner, planner: CommandPlanner, test_folder_id: str):
    """Create a Google Doc, export it to PDF, then delete it."""
    create_res = live_runner.run(
        planner.build_command("docs", "create_document", {"title": "Live Test Doc", "content": "Hello world"}),
        timeout_seconds=90,
    )
    assert create_res.success, f"Doc creation failed: {create_res.error or create_res.stderr}"
    create_payload = json.loads(create_res.stdout or "{}")
    doc_id = create_payload.get("documentId")
    assert doc_id

    # Export to PDF
    export_res = live_runner.run(
        planner.build_command("drive", "export_file", {"file_id": doc_id, "source_mime": "application/vnd.google-apps.document", "mime_type": "application/pdf"}),
        timeout_seconds=90,
    )
    assert export_res.success, f"Export failed: {export_res.error or export_res.stderr}"
    export_payload = json.loads(export_res.stdout or "{}")
    saved = export_payload.get("saved_file")
    assert saved and Path(saved).exists()

    # Cleanup
    live_runner.run(planner.build_command("drive", "delete_file", {"file_id": doc_id}), timeout_seconds=30)


@pytest.mark.live_integration
def test_live_create_google_sheet_and_export_csv(live_runner: GWSRunner, planner: CommandPlanner, test_folder_id: str):
    """Create a Google Sheet, export it to CSV, then delete it."""
    create_res = live_runner.run(
        planner.build_command("sheets", "create_spreadsheet", {"title": "Live Test Sheet"}),
        timeout_seconds=90,
    )
    assert create_res.success, f"Sheet creation failed: {create_res.error or create_res.stderr}"
    create_payload = json.loads(create_res.stdout or "{}")
    sheet_id = create_payload.get("spreadsheetId")
    assert sheet_id

    # Append some data (range without sheet name works with the GWS binary)
    append_res = live_runner.run(
        planner.build_command("sheets", "append_values", {
            "spreadsheet_id": sheet_id,
            "range": "A1",
            "values": [["Name", "Score"], ["Alice", "100"]],
        }),
        timeout_seconds=90,
    )
    assert append_res.success, f"Append failed: {append_res.error or append_res.stderr}"

    # Export to CSV
    export_res = live_runner.run(
        planner.build_command("drive", "export_file", {"file_id": sheet_id, "source_mime": "application/vnd.google-apps.spreadsheet", "mime_type": "text/csv"}),
        timeout_seconds=90,
    )
    assert export_res.success, f"Export failed: {export_res.error or export_res.stderr}"
    export_payload = json.loads(export_res.stdout or "{}")
    saved = export_payload.get("saved_file")
    assert saved and Path(saved).exists()
    content = Path(saved).read_text(encoding="utf-8")
    assert "Alice,100" in content

    # Cleanup
    live_runner.run(planner.build_command("drive", "delete_file", {"file_id": sheet_id}), timeout_seconds=30)


@pytest.mark.live_integration
def test_live_create_google_slide_and_export_pdf(live_runner: GWSRunner, planner: CommandPlanner, test_folder_id: str):
    """Create a Google Slides presentation, export it to PDF, then delete it."""
    create_res = live_runner.run(
        planner.build_command("slides", "create_presentation", {"title": "Live Test Slides"}),
        timeout_seconds=90,
    )
    assert create_res.success, f"Slide creation failed: {create_res.error or create_res.stderr}"
    create_payload = json.loads(create_res.stdout or "{}")
    slide_id = create_payload.get("presentationId")
    assert slide_id

    # Export to PDF
    export_res = live_runner.run(
        planner.build_command("drive", "export_file", {"file_id": slide_id, "source_mime": "application/vnd.google-apps.presentation", "mime_type": "application/pdf"}),
        timeout_seconds=90,
    )
    assert export_res.success, f"Export failed: {export_res.error or export_res.stderr}"
    export_payload = json.loads(export_res.stdout or "{}")
    saved = export_payload.get("saved_file")
    assert saved and Path(saved).exists()

    # Cleanup
    live_runner.run(planner.build_command("drive", "delete_file", {"file_id": slide_id}), timeout_seconds=30)
