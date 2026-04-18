import json
import pytest
from gws_assistant.planner import CommandPlanner
from gws_assistant.exceptions import ValidationError

class TestDriveCRUD:
    planner = CommandPlanner()

    def test_create_file(self):
        args = self.planner.build_command("drive", "create_file", {"name": "Test Doc"})
        assert args[:3] == ["drive", "files", "create"]
        params = json.loads(args[args.index("--params") + 1])
        assert "id,name,mimeType,webViewLink" in params["fields"]
        body = json.loads(args[args.index("--json") + 1])
        assert body["name"] == "Test Doc"
        assert body["mimeType"] == "application/vnd.google-apps.document"

    def test_create_file_with_folder(self):
        args = self.planner.build_command("drive", "create_file", {"name": "Test Doc", "folder_id": "fld_123"})
        body = json.loads(args[args.index("--json") + 1])
        assert body["parents"] == ["fld_123"]

    def test_update_file_metadata(self):
        args = self.planner.build_command("drive", "update_file_metadata", {"file_id": "fid_123", "name": "New Name", "description": "New Desc"})
        assert args[:3] == ["drive", "files", "update"]
        params = json.loads(args[args.index("--params") + 1])
        assert params["fileId"] == "fid_123"
        body = json.loads(args[args.index("--json") + 1])
        assert body["name"] == "New Name"
        assert body["description"] == "New Desc"

    def test_update_file_metadata_rejects_empty_payload(self):
        with pytest.raises(ValidationError) as excinfo:
            self.planner.build_command("drive", "update_file_metadata", {"file_id": "fid_123"})
        assert "At least one metadata field" in str(excinfo.value)

    def test_delete_file_exists(self):
        args = self.planner.build_command("drive", "delete_file", {"file_id": "fake_id_123"})
        assert args[:3] == ["drive", "files", "delete"]
        params = json.loads(args[args.index("--params") + 1])
        assert params["fileId"] == "fake_id_123"
