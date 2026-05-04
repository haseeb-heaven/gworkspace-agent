from __future__ import annotations

import os
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def clear_config_cache():
    """Clear the AppConfig singleton cache before and after each test."""
    try:
        from gws_assistant.config import AppConfig
        AppConfig.clear_cache()
        # Clean up any potential state pollution from tests that modify environ
        for key in ["LLM_FALLBACK_MODEL", "LLM_FALLBACK_MODEL2", "LLM_FALLBACK_MODEL3", "OPENROUTER_MODEL"]:
            os.environ.pop(key, None)
        yield
        AppConfig.clear_cache()
        for key in ["LLM_FALLBACK_MODEL", "LLM_FALLBACK_MODEL2", "LLM_FALLBACK_MODEL3", "OPENROUTER_MODEL"]:
            os.environ.pop(key, None)
    except ImportError:
        yield


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
    # First pass: mark manual tests and prepare gws_binary filtering
    items_to_remove = []

    # Check if any test is from test_gws_binary.py
    is_gws_binary = any("test_gws_binary.py" in str(item.fspath).replace("\\", "/") for item in items)
    if is_gws_binary:
        print(f"\nGWS_BINARY TESTS: Filtering by enabled services (gmail,docs,sheets,drive,calendar,tasks,keep,slides)\n")

    for item in items:
        # Get path relative to tests directory
        rel_path = str(item.fspath).replace("\\", "/")

        # Mark manual tests
        if "tests/manual" in rel_path:
            item.add_marker(pytest.mark.manual)

        # When running test_gws_binary.py, filter by service markers
        if "test_gws_binary.py" in rel_path:
            # Get enabled services from environment or default to main services
            enabled_services = os.getenv("GWS_ENABLED_SERVICES", "gmail,docs,sheets,drive,calendar,tasks,keep,slides")
            enabled_list = [s.strip() for s in enabled_services.split(",")]

            # Check if test has any of the enabled service markers
            # Check both the test method and its parent class
            marker_names = []
            for marker in item.iter_markers():
                marker_names.append(marker.name)
            # Also check class-level markers
            if item.cls:
                for marker in item.cls.pytestmark if hasattr(item.cls, 'pytestmark') else []:
                    marker_names.append(marker.name)

            has_enabled_marker = any(service in marker_names for service in enabled_list)

            # Also allow gws_binary marked tests (schema, help tests)
            has_gws_binary_marker = "gws_binary" in marker_names

            if not has_enabled_marker and not has_gws_binary_marker:
                service_name = item.name.replace("test_", "").split("_")[0]  # Extract service from test name
                print(f"  SKIPPING: {item.name} (service: {service_name} not enabled)")
                items_to_remove.append(item)

    # Remove filtered items
    removed_count = len(items_to_remove)
    for item in items_to_remove:
        items.remove(item)
    if removed_count > 0:
        print(f"\n  Filtered out {removed_count} tests for disabled services\n")

    # Service mapping - auto-mark tests based on file path
    for item in items:
        rel_path = str(item.fspath).replace("\\", "/")
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
