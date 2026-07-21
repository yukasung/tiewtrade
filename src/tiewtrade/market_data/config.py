import re
from dataclasses import dataclass
from datetime import timedelta


_TIMEFRAME_PATTERN = re.compile(r"^(?P<value>[1-9][0-9]*)(?P<unit>[mhd])$")


def timeframe_to_interval(timeframe: str) -> timedelta:
    match = _TIMEFRAME_PATTERN.fullmatch(timeframe)
    if match is None:
        raise ValueError("timeframe must use a positive m, h, or d interval")

    value = int(match.group("value"))
    unit = match.group("unit")
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    return timedelta(days=value)


@dataclass(frozen=True, slots=True)
class MarketDataConfig:
    symbol: str
    timeframe: str

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must not be blank")
        timeframe_to_interval(self.timeframe)

    @property
    def interval(self) -> timedelta:
        return timeframe_to_interval(self.timeframe)
