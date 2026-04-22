import math
from datetime import datetime, timezone


FIRST_HOUR_RATE = 60.0
ADDITIONAL_HOUR_RATE = 30.0


def _as_utc(dt: datetime) -> datetime:
    """MySQL DATETIME strips tz info on read — treat naive datetimes as UTC."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def calculate_parking_cost(entry_time: datetime, exit_time: datetime | None = None) -> tuple[float, float]:
    """Returns (cost, duration_minutes)."""
    if exit_time is None:
        exit_time = datetime.now(timezone.utc)

    delta = _as_utc(exit_time) - _as_utc(entry_time)
    duration_minutes = delta.total_seconds() / 60

    hours = max(1, math.ceil(duration_minutes / 60))
    cost = FIRST_HOUR_RATE + max(0, hours - 1) * ADDITIONAL_HOUR_RATE

    return round(cost, 2), round(duration_minutes, 2)
