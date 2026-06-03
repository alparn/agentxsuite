"""Project-wide pytest fixtures."""
from __future__ import annotations

from unittest import mock

import pytest


class SimpleMocker:
    """Small pytest-mock compatible subset used by the existing test suite."""

    Mock = mock.Mock
    MagicMock = mock.MagicMock

    def __init__(self) -> None:
        self._patches: list[mock._patch] = []

    def patch(self, target: str, *args, **kwargs):
        patcher = mock.patch(target, *args, **kwargs)
        patched = patcher.start()
        self._patches.append(patcher)
        return patched

    def stopall(self) -> None:
        for patcher in reversed(self._patches):
            patcher.stop()
        self._patches.clear()


@pytest.fixture
def mocker() -> SimpleMocker:
    """Provide the mocker fixture without requiring pytest-mock as a dependency."""
    fixture = SimpleMocker()
    try:
        yield fixture
    finally:
        fixture.stopall()
