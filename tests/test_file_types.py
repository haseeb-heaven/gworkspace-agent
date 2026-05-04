"""Unit tests for file type / MIME helpers."""

from pathlib import Path

import pytest

from gws_assistant.file_types import (
    all_supported_extensions,
    default_export_mime,
    describe_supported_file_types,
    export_extension_for_mime,
    guess_mime_type,
    is_binary_media,
    is_workspace_native,
    supported_export_formats,
    upload_command_flags,
)


class TestGuessMimeType:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("document.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            ("budget.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("slides.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
            ("report.pdf", "application/pdf"),
            ("data.csv", "text/csv"),
            ("notes.txt", "text/plain"),
            ("image.png", "image/png"),
            ("photo.jpg", "image/jpeg"),
            ("audio.mp3", "audio/mpeg"),
            ("video.mp4", "video/mp4"),
            ("movie.mkv", "video/x-matroska"),
            ("archive.zip", "application/zip"),
            ("script.py", "text/x-python"),
            ("config.yaml", "application/x-yaml"),
            ("index.html", "text/html"),
            ("sheet.gsheet", "application/vnd.google-apps.spreadsheet"),
            ("doc.gdoc", "application/vnd.google-apps.document"),
        ],
    )
    def test_known_extensions(self, path: str, expected: str):
        assert guess_mime_type(path) == expected

    def test_path_object(self):
        assert guess_mime_type(Path("some/path/to/file.pdf")) == "application/pdf"

    def test_unknown_fallback_to_stdlib(self, tmp_path):
        # create a dummy file with an extension that mimetypes may know
        p = tmp_path / "dummy.css"
        p.write_text("body{}")
        result = guess_mime_type(p)
        # stdlib knows .css
        assert result == "text/css"

    def test_no_extension_returns_none(self, tmp_path):
        p = tmp_path / "README"
        p.write_text("hello")
        # stdlib returns None for extensionless files
        assert guess_mime_type(p) is None


class TestIsWorkspaceNative:
    def test_true_for_gdoc(self):
        assert is_workspace_native("application/vnd.google-apps.document") is True

    def test_true_for_gsheet(self):
        assert is_workspace_native("application/vnd.google-apps.spreadsheet") is True

    def test_false_for_pdf(self):
        assert is_workspace_native("application/pdf") is False

    def test_none_is_false(self):
        assert is_workspace_native(None) is False


class TestIsBinaryMedia:
    def test_images_are_binary(self):
        assert is_binary_media("image/png") is True
        assert is_binary_media("image/jpeg") is True

    def test_audio_video_are_binary(self):
        assert is_binary_media("audio/mpeg") is True
        assert is_binary_media("video/mp4") is True

    def test_pdf_is_binary(self):
        assert is_binary_media("application/pdf") is True

    def test_text_is_not_binary(self):
        assert is_binary_media("text/plain") is False
        assert is_binary_media("text/csv") is False


class TestSupportedExportFormats:
    def test_document_formats(self):
        fmts = supported_export_formats("application/vnd.google-apps.document")
        assert "text/plain" in fmts
        assert "application/pdf" in fmts
        assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in fmts

    def test_spreadsheet_formats(self):
        fmts = supported_export_formats("application/vnd.google-apps.spreadsheet")
        assert "text/csv" in fmts
        assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in fmts

    def test_presentation_formats(self):
        fmts = supported_export_formats("application/vnd.google-apps.presentation")
        assert "application/pdf" in fmts
        assert "application/vnd.openxmlformats-officedocument.presentationml.presentation" in fmts

    def test_non_workspace_returns_none(self):
        assert supported_export_formats("application/pdf") is None
        assert supported_export_formats(None) is None


class TestDefaultExportMime:
    def test_doc_defaults_to_text_plain(self):
        assert default_export_mime("application/vnd.google-apps.document") == "text/plain"

    def test_sheet_defaults_to_csv(self):
        assert default_export_mime("application/vnd.google-apps.spreadsheet") == "text/csv"

    def test_presentation_defaults_to_pdf(self):
        assert default_export_mime("application/vnd.google-apps.presentation") == "application/pdf"

    def test_requested_mime_respected_when_supported(self):
        assert (
            default_export_mime("application/vnd.google-apps.document", "application/pdf")
            == "application/pdf"
        )

    def test_unsupported_requested_mime_ignored(self):
        # spreadsheet does not support text/plain in our map
        assert default_export_mime("application/vnd.google-apps.spreadsheet", "text/plain") == "text/csv"

    def test_no_source_mime_uses_requested(self):
        assert default_export_mime(None, "image/png") == "image/png"

    def test_no_source_no_requested_defaults_pdf(self):
        assert default_export_mime(None, None) == "application/pdf"


class TestExportExtensionForMime:
    def test_pdf(self):
        assert export_extension_for_mime("application/pdf") == ".pdf"

    def test_csv(self):
        assert export_extension_for_mime("text/csv") == ".csv"

    def test_unknown_returns_dat(self):
        assert export_extension_for_mime("application/x-custom-thing") == ".dat"


class TestUploadCommandFlags:
    def test_pdf(self):
        assert upload_command_flags("report.pdf") == {"upload_content_type": "application/pdf"}

    def test_mp4(self):
        assert upload_command_flags("movie.mp4") == {"upload_content_type": "video/mp4"}

    def test_no_extension(self, tmp_path):
        p = tmp_path / "README"
        p.write_text("hi")
        assert upload_command_flags(p) == {}


class TestDescribeSupportedFileTypes:
    def test_contains_all_categories(self):
        desc = describe_supported_file_types()
        assert "Google Workspace" in desc
        assert "Documents" in desc
        assert "Images" in desc
        assert "Audio" in desc
        assert "Video" in desc
        assert "Archives" in desc
        assert "Code / Data" in desc

    def test_mp4_in_video(self):
        desc = describe_supported_file_types()
        assert ".mp4" in desc

    def test_mkv_in_video(self):
        desc = describe_supported_file_types()
        assert ".mkv" in desc


class TestAllSupportedExtensions:
    def test_includes_common_types(self):
        exts = all_supported_extensions()
        assert ".pdf" in exts
        assert ".png" in exts
        assert ".mp3" in exts
        assert ".mp4" in exts
        assert ".mkv" in exts
        assert ".csv" in exts
        assert ".xlsx" in exts
