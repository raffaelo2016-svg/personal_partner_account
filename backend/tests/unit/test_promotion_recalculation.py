from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.promotion_recalculation import apply_promotion_to_open_fees


@pytest.fixture(autouse=True)
def setup_db():
    """These unit tests use a mocked session and need no database."""
    yield


def fee(status="unpaid", **kwargs):
    return SimpleNamespace(id="fee", client_id="client", status=status, paid_at=None,
                           amount=1_700_000, base_amount=1_700_000, discount_amount=0, **kwargs)


def setup(fees, limit=1, end=None):
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = fees
    session.execute.return_value = result
    session.get.return_value = SimpleNamespace(deleted_at=None)
    session.scalar.return_value = False
    session.add = MagicMock()
    partner = SimpleNamespace(id="partner", free_client_limit=limit,
                              promotion_start_date=date(2026, 10, 7), promotion_end_date=end)
    return session, partner


@pytest.mark.asyncio
async def test_retroactive_discount_is_idempotent_and_respects_limit():
    first, second = fee(), fee()
    session, partner = setup([first, second])
    assert await apply_promotion_to_open_fees(session, partner) == 1
    assert (first.status, first.amount, first.discount_amount) == ("promo_free", 0, 1_700_000)
    assert second.amount == 1_700_000
    assert await apply_promotion_to_open_fees(session, partner) == 0
    session.add.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["paid", "promo_free"])
async def test_preserves_settled_and_existing_free_fees(status):
    existing = fee(status)
    session, partner = setup([existing])
    assert await apply_promotion_to_open_fees(session, partner) == 0
    assert existing.status == status


@pytest.mark.asyncio
async def test_skips_payment_in_progress_and_deleted_client():
    session, partner = setup([fee()])
    session.scalar.return_value = True
    assert await apply_promotion_to_open_fees(session, partner) == 0
    session.get.return_value.deleted_at = datetime.now(UTC)
    session.scalar.return_value = False
    assert await apply_promotion_to_open_fees(session, partner) == 0


@pytest.mark.asyncio
async def test_disabled_promotion_does_not_query_fees():
    session, partner = setup([fee()], limit=0)
    assert await apply_promotion_to_open_fees(session, partner) == 0
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_date_bounds_use_moscow_and_include_entire_last_day():
    session, partner = setup([], end=date(2026, 10, 8))
    await apply_promotion_to_open_fees(session, partner)
    query = session.execute.call_args.args[0]
    values = list(query.compile().params.values())
    assert datetime(2026, 10, 6, 21, tzinfo=UTC) in values
    assert datetime(2026, 10, 8, 21, tzinfo=UTC) in values
