from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.tasks import bitrix24_sync


@pytest.fixture
def setup_db() -> None:
    """These pure runner tests do not need the autouse database fixture."""


def test_run_async_disposes_pool_after_each_celery_unit(monkeypatch: pytest.MonkeyPatch) -> None:
    dispose = AsyncMock()
    monkeypatch.setattr(bitrix24_sync, "async_engine", SimpleNamespace(dispose=dispose))

    async def operation(value: int) -> int:
        return value

    assert bitrix24_sync._run_async(operation(1)) == 1
    assert bitrix24_sync._run_async(operation(2)) == 2
    assert dispose.await_count == 2


def test_run_async_disposes_pool_when_operation_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    dispose = AsyncMock()
    monkeypatch.setattr(bitrix24_sync, "async_engine", SimpleNamespace(dispose=dispose))

    async def failing_operation() -> None:
        raise RuntimeError("expected test failure")

    with pytest.raises(RuntimeError, match="expected test failure"):
        bitrix24_sync._run_async(failing_operation())

    dispose.assert_awaited_once()
