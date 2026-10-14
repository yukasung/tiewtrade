"""UTC candle schedules, including calendar week and month boundaries."""

from calendar import monthrange
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from tiewtrade.core.moments import require_aware


class Timeframe(StrEnum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"
    MN1 = "1M"

    @property
    def fixed_span(self) -> timedelta | None:
        seconds = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "1h": 3600,
            "4h": 14400,
            "1d": 86400,
            "1w": 604800,
        }
        value = seconds.get(self.value)
        return None if value is None else timedelta(seconds=value)

    @property
    def span(self) -> timedelta:
        """Compatibility for fixed schedules; calendar months require an anchor."""
        span = self.fixed_span
        if span is None:
            raise ValueError("calendar timeframe has no fixed span")
        return span


def align_floor(moment: datetime, timeframe: Timeframe) -> datetime:
    require_aware("moment", moment)
    value = moment.astimezone(UTC)
    if timeframe is Timeframe.MN1:
        return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if timeframe is Timeframe.W1:
        day = value.replace(hour=0, minute=0, second=0, microsecond=0)
        return day - timedelta(days=day.weekday())
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    span = timeframe.span
    return epoch + ((value - epoch) // span) * span


def advance(moment: datetime, timeframe: Timeframe, slots: int) -> datetime:
    require_aware("moment", moment)
    if type(slots) is not int:
        raise TypeError("slot count must be an integer")
    value = moment.astimezone(UTC)
    if timeframe is not Timeframe.MN1:
        return value + timeframe.span * slots
    if align_floor(value, timeframe) != value:
        raise ValueError("calendar advance requires an aligned open")
    index = value.year * 12 + value.month - 1 + slots
    year, month_index = divmod(index, 12)
    if year < 1 or year > 9999:
        raise ValueError("calendar advance outside datetime range")
    return value.replace(year=year, month=month_index + 1, day=1)


def next_open(open_at: datetime, timeframe: Timeframe) -> datetime:
    return advance(open_at, timeframe, 1)


def previous_open(open_at: datetime, timeframe: Timeframe) -> datetime:
    return advance(open_at, timeframe, -1)


def align_ceil(moment: datetime, timeframe: Timeframe) -> datetime:
    floor = align_floor(moment, timeframe)
    return floor if floor == moment.astimezone(UTC) else next_open(floor, timeframe)


def slot_count(start: datetime, end: datetime, timeframe: Timeframe) -> int:
    """Count aligned opens in the half-open interval [start, end)."""
    require_aware("start", start)
    require_aware("end", end)
    if end < start:
        raise ValueError("slot range must not run backwards")
    first = align_ceil(start, timeframe)
    end_utc = end.astimezone(UTC)
    if first >= end_utc:
        return 0
    if timeframe is not Timeframe.MN1:
        span = timeframe.span
        return int((end_utc - first + span - timedelta(microseconds=1)) // span)
    months = (end_utc.year - first.year) * 12 + end_utc.month - first.month
    return months + (1 if advance(first, timeframe, months) < end_utc else 0)


def subtract_calendar_years(moment: datetime, years: int) -> datetime:
    require_aware("moment", moment)
    value = moment.astimezone(UTC)
    year = value.year - years
    day = min(value.day, monthrange(year, value.month)[1])
    return value.replace(year=year, day=day)


def retention_cutoff(as_of: datetime, timeframe: Timeframe) -> datetime:
    require_aware("as_of", as_of)
    value = as_of.astimezone(UTC)
    if timeframe in (Timeframe.W1, Timeframe.MN1):
        return subtract_calendar_years(value, 5)
    return value - timedelta(days=365)


def candle_storage_cutoff(as_of: datetime, timeframe: Timeframe) -> datetime:
    """Candle storage is independent of the unchanged indicator seed horizon."""
    if timeframe in (Timeframe.W1, Timeframe.MN1):
        return datetime(1970, 1, 1, tzinfo=UTC)
    return retention_cutoff(as_of, timeframe)


def chart_display_start(as_of: datetime, timeframe: Timeframe) -> datetime:
    """Three calendar months, including the candle intersecting the boundary."""
    require_aware("as_of", as_of)
    value = as_of.astimezone(UTC)
    month = value.year * 12 + value.month - 1 - 3
    year, index = divmod(month, 12)
    cutoff = value.replace(
        year=year, month=index + 1, day=min(value.day, monthrange(year, index + 1)[1])
    )
    return align_floor(cutoff, timeframe)
