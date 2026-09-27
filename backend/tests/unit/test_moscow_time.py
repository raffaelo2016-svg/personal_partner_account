from datetime import UTC, date, datetime

from app.core.time import moscow_date_bounds_utc, moscow_date_start_utc, moscow_today


def test_moscow_today_switches_at_moscow_midnight() -> None:
    assert moscow_today(datetime(2026, 4, 13, 20, 59, tzinfo=UTC)) == date(2026, 4, 13)
    assert moscow_today(datetime(2026, 4, 13, 21, 0, tzinfo=UTC)) == date(2026, 4, 14)


def test_moscow_date_start_is_previous_utc_evening() -> None:
    assert moscow_date_start_utc(date(2026, 4, 14)) == datetime(2026, 4, 13, 21, 0, tzinfo=UTC)


def test_moscow_date_bounds_are_half_open_utc_range() -> None:
    assert moscow_date_bounds_utc(date(2026, 4, 14), date(2026, 4, 15)) == (
        datetime(2026, 4, 13, 21, 0, tzinfo=UTC),
        datetime(2026, 4, 15, 21, 0, tzinfo=UTC),
    )
