from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

MOSCOW_TIMEZONE = "Europe/Moscow"
MOSCOW_TZ = ZoneInfo(MOSCOW_TIMEZONE)


def moscow_now(value: datetime | None = None) -> datetime:
    """Return an aware datetime in the cabinet's business timezone."""
    current = value or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.astimezone(MOSCOW_TZ)


def moscow_today(value: datetime | None = None) -> date:
    return moscow_now(value).date()


def moscow_date_start_utc(value: date) -> datetime:
    """Convert the start of a Moscow calendar day to an aware UTC instant."""
    return datetime.combine(value, time.min, tzinfo=MOSCOW_TZ).astimezone(UTC)


def moscow_date_bounds_utc(start: date, end: date) -> tuple[datetime, datetime]:
    """Return the half-open UTC range covering Moscow dates [start, end]."""
    return moscow_date_start_utc(start), moscow_date_start_utc(end + timedelta(days=1))
