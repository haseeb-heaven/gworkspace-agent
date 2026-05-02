"""Unit tests for Drive file operations across all supported document types."""

from pathlib import Path

import pytest

from gws_assistant.file_types import guess_mime_type, is_binary_media, is_workspace_native
from gws_assistant.planner import CommandPlanner
from tests.fakes.fake_google_workspace import FakeGoogleWorkspace


class TestPlannerUploadMimeDetection:
    """Verify build_command injects --upload-content-type for known extensions."""

    @pytest.mark.parametrize(
        "file_path,expected_mime",
        [
            ("/tmp/report.pdf", "application/pdf"),
            ("/tmp/photo.png", "image/png"),
            ("/tmp/song.mp3", "audio/mpeg"),
            ("/tmp/movie.mp4", "video/mp4"),
            ("/tmp/archive.mkv", "video/x-matroska"),
            ("/tmp/data.csv", "text/csv"),
            ("/tmp/notes.txt", "text/plain"),
            ("/tmp/sheet.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("/tmp/slides.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
            ("/tmp/document.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ],
    )
    def test_upload_includes_content_type_flag(self, file_path: str, expected_mime: str):
        planner = CommandPlanner()
        cmd = planner.build_command("drive", "upload_file", {"file_path": file_path})
        assert "--upload-content-type" in cmd
        idx = cmd.index("--upload-content-type")
        assert cmd[idx + 1] == expected_mime

    def test_upload_without_extension_has_no_content_type(self):
        planner = CommandPlanner()
        cmd = planner.build_command("drive", "upload_file", {"file_path": "/tmp/README"})
        assert "--upload-content-type" not in cmd

    def test_upload_custom_name_preserved(self):
        planner = CommandPlanner()
        cmd = planner.build_command("drive", "upload_file", {"file_path": "/tmp/old.pdf", "name": "new_report.pdf"})
        assert "new_report.pdf" in cmd[-1]  # --json payload contains name


class TestPlannerExportFileTypeNegotiation:
    """Verify export_file command picks correct endpoint for each MIME type."""

    def test_workspace_document_uses_export_endpoint(self):
        planner = CommandPlanner()
        cmd = planner.build_command(
            "drive", "export_file",
            {"file_id": "gdoc_fgh", "source_mime": "application/vnd.google-apps.document"}
        )
        assert "export" in cmd
        assert "text/plain" in cmd[-3]  # default export mime

    def test_workspace_spreadsheet_uses_export_csv(self):
        planner = CommandPlanner()
        cmd = planner.build_command(
            "drive", "export_file",
            {"file_id": "gsheet_ijk", "source_mime": "application/vnd.google-apps.spreadsheet"}
        )
        assert "export" in cmd
        assert "text/csv" in cmd[-3]

    def test_workspace_presentation_uses_export_pdf(self):
        planner = CommandPlanner()
        cmd = planner.build_command(
            "drive", "export_file",
            {"file_id": "gslides_lmn", "source_mime": "application/vnd.google-apps.presentation"}
        )
        assert "export" in cmd
        assert "application/pdf" in cmd[-3]

    def test_pdf_uses_download_endpoint(self):
        planner = CommandPlanner()
        cmd = planner.build_command(
            "drive", "export_file",
            {"file_id": "pdf_jkl_4", "source_mime": "application/pdf"}
        )
        assert "get" in cmd
        assert "alt" in cmd[-3]

    def test_image_png_uses_download_endpoint(self):
        planner = CommandPlanner()
        cmd = planner.build_command(
            "drive", "export_file",
            {"file_id": "img_stu_7", "source_mime": "image/png"}
        )
        assert "get" in cmd
        assert "media" in cmd[-3]

    def test_video_mp4_uses_download_endpoint(self):
        planner = CommandPlanner()
        cmd = planner.build_command(
            "drive", "export_file",
            {"file_id": "video_0ab", "source_mime": "video/mp4"}
        )
        assert "get" in cmd

    def test_audio_mp3_uses_download_endpoint(self):
        planner = CommandPlanner()
        cmd = planner.build_command(
            "drive", "export_file",
            {"file_id": "audio_yz9", "source_mime": "audio/mpeg"}
        )
        assert "get" in cmd

    def test_office_docx_uses_download_endpoint(self):
        planner = CommandPlanner()
        cmd = planner.build_command(
            "drive", "export_file",
            {"file_id": "doc_abc_1", "source_mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
        )
        assert "get" in cmd

    def test_folder_raises_validation_error(self):
        planner = CommandPlanner()
        with pytest.raises(Exception) as exc_info:
            planner.build_command(
                "drive", "export_file",
                {"file_id": "folder_1", "source_mime": "application/vnd.google-apps.folder"}
            )
        assert "folder" in str(exc_info.value).lower()

    def test_requested_mime_respected_for_document(self):
        planner = CommandPlanner()
        cmd = planner.build_command(
            "drive", "export_file",
            {
                "file_id": "gdoc_fgh",
                "source_mime": "application/vnd.google-apps.document",
                "mime_type": "application/pdf",
            }
        )
        assert "export" in cmd
        assert "application/pdf" in cmd[-3]

    def test_media_flag_uses_download(self):
        planner = CommandPlanner()
        cmd = planner.build_command(
            "drive", "export_file",
            {"file_id": "gdoc_fgh", "source_mime": "application/vnd.google-apps.document", "mime_type": "media"}
        )
        assert "get" in cmd


class TestFakeDriveListFiles:
    """Verify FakeGoogleWorkspace returns metadata for all file types."""

    def test_list_files_returns_diverse_mime_types(self):
        fake = FakeGoogleWorkspace()
        result = fake.run(["drive", "files", "list", "--params", '{"pageSize": 20}'])
        assert result.success
        payload = result.output or {}
        files = payload.get("files", [])
        mime_types = {f["mimeType"] for f in files}
        assert "application/pdf" in mime_types
        assert "image/png" in mime_types
        assert "audio/mpeg" in mime_types
        assert "video/mp4" in mime_types
        assert "text/plain" in mime_types
        assert "application/vnd.google-apps.document" in mime_types

    def test_list_files_with_query_filters(self):
        fake = FakeGoogleWorkspace()
        result = fake.run(["drive", "files", "list", "--params", '{"q": "name contains \"logo\""}'])
        payload = result.output or {}
        names = [f["name"] for f in payload.get("files", [])]
        assert any("logo" in n.lower() for n in names)


class TestFakeDriveUploadFile:
    """Verify upload_file returns proper metadata with MIME type."""

    @pytest.mark.parametrize(
        "path,name,expected_mime",
        [
            ("/tmp/report.pdf", "report.pdf", "application/pdf"),
            ("/tmp/song.mp3", "song.mp3", "audio/mpeg"),
            ("/tmp/video.mp4", "video.mp4", "video/mp4"),
            ("/tmp/archive.mkv", "archive.mkv", "video/x-matroska"),
            ("/tmp/image.png", "image.png", "image/png"),
            ("/tmp/photo.jpg", "photo.jpg", "image/jpeg"),
            ("/tmp/data.csv", "data.csv", "text/csv"),
            ("/tmp/notes.txt", "notes.txt", "text/plain"),
            ("/tmp/doc.docx", "doc.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            ("/tmp/sheet.xlsx", "sheet.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("/tmp/slides.pptx", "slides.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ],
    )
    def test_upload_returns_correct_mime(self, path: str, name: str, expected_mime: str):
        fake = FakeGoogleWorkspace()
        cmd = [
            "drive", "files", "create",
            "--upload", path,
            "--upload-content-type", expected_mime,
            "--params", '{"fields": "id,name,mimeType,webViewLink"}',
            "--json", f'{{"name": "{name}"}}',
        ]
        result = fake.run(cmd)
        assert result.success
        payload = result.output or {}
        assert payload.get("mimeType") == expected_mime
        assert payload.get("name") == name
        assert payload.get("id", "").startswith("upload_")


class TestFakeDriveExportFile:
    """Verify export/download produces saved_file metadata for each type."""

    @pytest.mark.parametrize(
        "file_id,expected_ext",
        [
            ("doc_abc_1", ".docx"),
            ("sheet_def_2", ".xlsx"),
            ("slide_ghi_3", ".pptx"),
            ("pdf_jkl_4", ".pdf"),
            ("txt_mno_5", ".txt"),
            ("csv_pqr_6", ".csv"),
            ("img_stu_7", ".png"),
            ("img_vwx_8", ".jpg"),
            ("audio_yz9", ".mp3"),
            ("video_0ab", ".mp4"),
            ("video_cde", ".mkv"),
        ],
    )
    def test_export_returns_saved_file_with_extension(self, file_id: str, expected_ext: str):
        fake = FakeGoogleWorkspace()
        cmd = [
            "drive", "files", "get",
            "--params", f'{{"fileId": "{file_id}", "alt": "media"}}',
            "-o", f"scratch/exports/download_{file_id}{expected_ext}",
        ]
        result = fake.run(cmd)
        assert result.success
        payload = result.output or {}
        assert payload.get("saved_file", "").endswith(expected_ext)
        assert Path(payload["saved_file"]).exists()

    def test_export_google_doc_returns_text(self):
        fake = FakeGoogleWorkspace()
        cmd = [
            "drive", "files", "export",
            "--params", '{"fileId": "gdoc_fgh", "mimeType": "text/plain"}',
            "-o", "scratch/exports/download_gdoc_fgh.txt",
        ]
        result = fake.run(cmd)
        assert result.success
        payload = result.output or {}
        assert "content" in payload
        assert Path(payload["saved_file"]).exists()

    def test_export_google_doc_returns_pdf(self):
        fake = FakeGoogleWorkspace()
        cmd = [
            "drive", "files", "export",
            "--params", '{"fileId": "gdoc_fgh", "mimeType": "application/pdf"}',
            "-o", "scratch/exports/download_gdoc_fgh.pdf",
        ]
        result = fake.run(cmd)
        assert result.success
        payload = result.output or {}
        assert payload.get("mimeType") == "application/vnd.google-apps.document"
        assert Path(payload["saved_file"]).exists()


class TestFakeDriveCopyMoveDelete:
    """Verify lifecycle operations work for all file types."""

    def test_copy_file_returns_new_id(self):
        fake = FakeGoogleWorkspace()
        cmd = [
            "drive", "files", "copy",
            "--params", '{"fileId": "img_stu_7"}',
            "--json", '{"name": "logo_backup.png"}',
        ]
        result = fake.run(cmd)
        assert result.success
        payload = result.output or {}
        assert payload.get("id", "").startswith("copy_")
        assert payload.get("name") == "logo_backup.png"
        assert payload.get("mimeType") == "image/png"

    def test_delete_file(self):
        fake = FakeGoogleWorkspace()
        cmd = [
            "drive", "files", "delete",
            "--params", '{"fileId": "audio_yz9"}',
        ]
        result = fake.run(cmd)
        assert result.success
        assert result.output == {}

    def test_trash_file(self):
        fake = FakeGoogleWorkspace()
        cmd = [
            "drive", "files", "update",
            "--params", '{"fileId": "video_0ab"}',
            "--json", '{"trashed": true}',
        ]
        result = fake.run(cmd)
        assert result.success
        payload = result.output or {}
        assert payload.get("trashed") is True

    def test_rename_file(self):
        fake = FakeGoogleWorkspace()
        cmd = [
            "drive", "files", "update",
            "--params", '{"fileId": "csv_pqr_6", "fields": "id,name,description"}',
            "--json", '{"name": "renamed_data.csv", "description": "Updated desc"}',
        ]
        result = fake.run(cmd)
        assert result.success
        payload = result.output or {}
        assert payload.get("name") == "renamed_data.csv"
        assert payload.get("description") == "Updated desc"

    def test_move_file(self):
        fake = FakeGoogleWorkspace()
        cmd = [
            "drive", "files", "update",
            "--params", '{"fileId": "pdf_jkl_4", "addParents": "folder_123"}',
        ]
        result = fake.run(cmd)
        assert result.success
        payload = result.output or {}
        assert payload.get("parents") == ["folder_123"]

    def test_create_folder(self):
        fake = FakeGoogleWorkspace()
        cmd = [
            "drive", "files", "create",
            "--params", '{"fields": "id,name,mimeType,webViewLink"}',
            "--json", '{"mimeType": "application/vnd.google-apps.folder", "name": "Test Folder"}',
        ]
        result = fake.run(cmd)
        assert result.success
        payload = result.output or {}
        assert payload.get("mimeType") == "application/vnd.google-apps.folder"
        assert payload.get("name") == "Test Folder"


class TestMimeTypeHelpers:
    """Cross-check file_types helpers against known extensions."""

    @pytest.mark.parametrize(
        "ext,expected",
        [
            (".mp4", "video/mp4"),
            (".mkv", "video/x-matroska"),
            (".mp3", "audio/mpeg"),
            (".wav", "audio/wav"),
            (".png", "image/png"),
            (".jpg", "image/jpeg"),
            (".jpeg", "image/jpeg"),
            (".gif", "image/gif"),
            (".webp", "image/webp"),
            (".pdf", "application/pdf"),
            (".csv", "text/csv"),
            (".txt", "text/plain"),
            (".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            (".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            (".pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
            (".zip", "application/zip"),
            (".py", "text/x-python"),
            (".yaml", "application/x-yaml"),
            (".yml", "application/x-yaml"),
            (".json", "application/json"),
        ],
    )
    def test_guess_mime_type(self, ext: str, expected: str):
        assert guess_mime_type(f"file{ext}") == expected

    def test_is_workspace_native_true(self):
        assert is_workspace_native("application/vnd.google-apps.document") is True
        assert is_workspace_native("application/vnd.google-apps.spreadsheet") is True

    def test_is_workspace_native_false(self):
        assert is_workspace_native("application/pdf") is False
        assert is_workspace_native("image/png") is False
        assert is_workspace_native("video/mp4") is False

    def test_is_binary_media(self):
        assert is_binary_media("image/png") is True
        assert is_binary_media("audio/mpeg") is True
        assert is_binary_media("video/mp4") is True
        assert is_binary_media("application/pdf") is True
        assert is_binary_media("application/zip") is True
        assert is_binary_media("text/plain") is False
        assert is_binary_media("text/csv") is False
