import json
import os
import tempfile

import pytest

from gws_assistant.exceptions import ValidationError
from gws_assistant.planner import CommandPlanner
from gws_assistant.service_catalog import SERVICES


class TestDriveUnit:
    planner = CommandPlanner()

    def test_list_files_with_query(self):
        args = self.planner.build_command("drive", "list_files", {"q": "name contains 'Budget'", "page_size": 20})
        params = json.loads(args[args.index("--params") + 1])
        assert params["q"] == "name contains 'Budget'"
        assert params["pageSize"] == 20

    def test_create_folder(self):
        args = self.planner.build_command("drive", "create_folder", {"folder_name": "My Folder"})
        assert args[:3] == ["drive", "files", "create"]
        body = json.loads(args[args.index("--json") + 1])
        assert body["name"] == "My Folder"
        assert body["mimeType"] == "application/vnd.google-apps.folder"

    def test_create_folder_rejects_empty_name(self):
        with pytest.raises(ValidationError):
            self.planner.build_command("drive", "create_folder", {"folder_name": ""})

    def test_delete_file(self):
        args = self.planner.build_command("drive", "delete_file", {"file_id": "fake_id_123"})
        assert args[:3] == ["drive", "files", "delete"]
        params = json.loads(args[args.index("--params") + 1])
        assert params["fileId"] == "fake_id_123"

    def test_move_file(self):
        args = self.planner.build_command("drive", "move_file", {"file_id": "fid_123", "folder_id": "fld_123"})
        assert args[:3] == ["drive", "files", "update"]
        params = json.loads(args[args.index("--params") + 1])
        assert params["fileId"] == "fid_123"
        assert params["addParents"] == "fld_123"
        # assert params["removeParents"] == "root"  # removeParents is dynamically fetched now

    def _make_temp_file(self, suffix=".txt") -> str:
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        return path

    def test_upload_file_without_folder_id_has_no_parents(self):
        tmp = self._make_temp_file()
        args = self.planner.build_command("drive", "upload_file", {"file_path": tmp})
        body = json.loads(args[args.index("--json") + 1])
        assert "parents" not in body

    def test_upload_file_with_folder_id_adds_parents_list(self):
        tmp = self._make_temp_file()
        args = self.planner.build_command(
            "drive", "upload_file", {"file_path": tmp, "folder_id": "folder-123"}
        )
        body = json.loads(args[args.index("--json") + 1])
        assert body.get("parents") == ["folder-123"]

    def test_upload_file_empty_folder_id_no_parents(self):
        tmp = self._make_temp_file()
        args = self.planner.build_command(
            "drive", "upload_file", {"file_path": tmp, "folder_id": ""}
        )
        body = json.loads(args[args.index("--json") + 1])
        assert "parents" not in body


# ---------------------------------------------------------------------------
# service_catalog.py — upload_file folder_id ParameterSpec (PR change)
# ---------------------------------------------------------------------------


class TestServiceCatalogUploadFileFolderId:
    """SERVICES['drive']['upload_file'] must expose the new folder_id parameter."""

    def _get_upload_params(self):
        return {p.name: p for p in SERVICES["drive"].actions["upload_file"].parameters}

    def test_upload_file_has_folder_id_parameter(self):
        params = self._get_upload_params()
        assert "folder_id" in params

    def test_folder_id_is_not_required(self):
        params = self._get_upload_params()
        assert params["folder_id"].required is False

    def test_folder_id_example_is_empty_string(self):
        params = self._get_upload_params()
        assert params["folder_id"].example == ""

    def test_folder_id_prompt_mentions_folder(self):
        params = self._get_upload_params()
        assert "folder" in params["folder_id"].prompt.lower()

    def test_upload_file_still_has_file_path_parameter(self):
        params = self._get_upload_params()
        assert "file_path" in params

    def test_upload_file_still_has_name_parameter(self):
        params = self._get_upload_params()
        assert "name" in params
