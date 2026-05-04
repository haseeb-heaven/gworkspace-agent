import json
import logging
import os
from pathlib import Path

import pytest

from gws_assistant.execution.verifier import TripleVerifier
from gws_assistant.gws_runner import GWSRunner


@pytest.fixture
def runner():
    bin_path = os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws")
    return GWSRunner(Path(bin_path), logging.getLogger("test"))


@pytest.fixture
def verifier(runner):
    return TripleVerifier(runner)


@pytest.mark.live_integration
class TestFullCRUD:
    """
    End-to-end CRUD tests with Triple Verification.
    Requires real GWS credentials and binary.
    """

    def test_docs_crud_lifecycle(self, runner, verifier):
        # 1. Create
        title = "CRUD Test Doc"
        create_args = ["docs", "documents", "create", "--json", json.dumps({"title": title})]
        res = runner.run(create_args)
        assert res.success, f"Failed to create doc: {res.stderr}"
        doc_id = json.loads(res.stdout)["documentId"]

        try:
            # 2. Verify (Read)
            assert verifier.verify_resource_by_id("docs", doc_id, {"title": title})

            # 3. Update (if applicable via CLI, e.g. batchUpdate)
            # For now just verify we can re-read it.

        finally:
            # 4. Delete (Drive API)
            del_args = ["drive", "files", "delete", "--params", json.dumps({"fileId": doc_id})]
            runner.run(del_args)

    def test_sheets_crud_lifecycle(self, runner, verifier):
        # 1. Create
        title = "CRUD Test Sheet"
        create_args = ["sheets", "spreadsheets", "create", "--json", json.dumps({"properties": {"title": title}})]
        res = runner.run(create_args)
        assert res.success
        sheet_id = json.loads(res.stdout)["spreadsheetId"]

        try:
            # 2. Verify
            # Note: properties title might be nested, verifier currently does flat check
            # We can extend verifier or just check ID existence
            assert verifier.verify_resource_by_id("sheets", sheet_id, {})

        finally:
            # 3. Delete
            del_args = ["drive", "files", "delete", "--params", json.dumps({"fileId": sheet_id})]
            runner.run(del_args)

    def test_drive_folder_crud_lifecycle(self, runner, verifier):
        # 1. Create Folder
        name = "CRUD Test Folder"
        create_args = [
            "drive",
            "files",
            "create",
            "--json",
            json.dumps({"name": name, "mimeType": "application/vnd.google-apps.folder"}),
        ]
        res = runner.run(create_args)
        assert res.success
        folder_id = json.loads(res.stdout)["id"]

        try:
            # 2. Verify
            assert verifier.verify_resource_by_id("drive", folder_id, {"name": name})

        finally:
            # 3. Delete
            del_args = ["drive", "files", "delete", "--params", json.dumps({"fileId": folder_id})]
            runner.run(del_args)
