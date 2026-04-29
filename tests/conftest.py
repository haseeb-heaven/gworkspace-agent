from __future__ import annotations

import os
from unittest.mock import patch

import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_session_env():
    """Ensure required environment variables are set for the entire test session."""
    if not os.getenv("GWS_BINARY_PATH"):
        os.environ["GWS_BINARY_PATH"] = "gws"
    if not os.getenv("DEFAULT_RECIPIENT_EMAIL"):
        os.environ["DEFAULT_RECIPIENT_EMAIL"] = "test@example.com"


class _SimpleMocker:
    def __init__(self) -> None:
        self._patchers: list[object] = []
        self.patch = _PatchProxy(self)

    def _patch(self, target: str, *args, **kwargs):
        patcher = patch(target, *args, **kwargs)
        mocked = patcher.start()
        self._patchers.append(patcher)
        return mocked

    def stopall(self) -> None:
        while self._patchers:
            self._patchers.pop().stop()

    def _patch_object(self, target, attribute, *args, **kwargs):
        patcher = patch.object(target, attribute, *args, **kwargs)
        mocked = patcher.start()
        self._patchers.append(patcher)
        return mocked

    def _patch_dict(self, in_dict, values=None, clear=False, **kwargs):
        patcher = patch.dict(in_dict, values or {}, clear=clear, **kwargs)
        patcher.start()
        self._patchers.append(patcher)


class _PatchProxy:
    def __init__(self, owner: _SimpleMocker) -> None:
        self._owner = owner

    def __call__(self, target: str, *args, **kwargs):
        return self._owner._patch(target, *args, **kwargs)

    def object(self, target, attribute, *args, **kwargs):
        return self._owner._patch_object(target, attribute, *args, **kwargs)

    def dict(self, in_dict, values=None, clear=False, **kwargs):
        return self._owner._patch_dict(in_dict, values, clear=clear, **kwargs)


@pytest.fixture
def mocker():
    helper = _SimpleMocker()
    try:
        yield helper
    finally:
        helper.stopall()


@pytest.fixture
def default_email(request):
    import os

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    email = os.getenv("DEFAULT_RECIPIENT_EMAIL")
    if not email:
        if request.node.get_closest_marker("live_integration") or os.getenv("RUN_LIVE_TESTS"):
            pytest.skip("DEFAULT_RECIPIENT_EMAIL must be set in .env for live integration tests")
        return "test@example.com"
    return email


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their directory and filename."""
    for item in items:
        # Get path relative to tests directory
        rel_path = str(item.fspath).replace("\\", "/")

        # Mark manual tests
        if "tests/manual" in rel_path:
            item.add_marker(pytest.mark.manual)

        # Service mapping
        services = {
            "gmail": pytest.mark.gmail,
            "docs": pytest.mark.docs,
            "sheets": pytest.mark.sheets,
            "drive": pytest.mark.drive,
            "calendar": pytest.mark.calendar,
            "tasks": pytest.mark.tasks,
            "classroom": pytest.mark.classroom,
            "keep": pytest.mark.keep,
            "forms": pytest.mark.forms,
            "slides": pytest.mark.slides,
            "contacts": pytest.mark.contacts,
            "admin": pytest.mark.admin,
            "script": pytest.mark.script,
            "model_armor": pytest.mark.modelarmor,
            "events": pytest.mark.events,
        }

        for name, marker in services.items():
            if f"/{name}" in rel_path or f"_{name}" in rel_path:
                item.add_marker(marker)
