import pytest
import json
from gws_assistant.planner import CommandPlanner
from gws_assistant.exceptions import ValidationError

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
        assert params["removeParents"] == "root"
