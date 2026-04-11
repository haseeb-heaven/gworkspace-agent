from __future__ import annotations

from unittest.mock import patch

import pytest


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


class _PatchProxy:
    def __init__(self, owner: _SimpleMocker) -> None:
        self._owner = owner

    def __call__(self, target: str, *args, **kwargs):
        return self._owner._patch(target, *args, **kwargs)

    def object(self, target, attribute, *args, **kwargs):
        return self._owner._patch_object(target, attribute, *args, **kwargs)


@pytest.fixture
def mocker():
    helper = _SimpleMocker()
    try:
        yield helper
    finally:
        helper.stopall()
