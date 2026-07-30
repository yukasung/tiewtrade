import logging
from collections.abc import Iterable
from typing import Protocol, cast


class MarketDataLogRecord(Protocol):
    levelno: int
    event_name: str
    symbol: str
    timeframe: str
    reason: str
    failure_kind: str | None
    attempt: int
    delay_seconds: float
    discard_reason: str
    skew_seconds: float
    start: str
    end: str
    candle_count: int

    def getMessage(self) -> str: ...


def as_market_data_record(record: logging.LogRecord) -> MarketDataLogRecord:
    assert hasattr(record, "event_name")
    return cast(MarketDataLogRecord, record)


def market_data_records(
    records: Iterable[logging.LogRecord],
) -> list[MarketDataLogRecord]:
    return [
        as_market_data_record(record)
        for record in records
        if hasattr(record, "event_name")
    ]
