import logging
from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from tiewtrade.market_data.completed_candle_stream import CandleAcceptance
from tiewtrade.market_data.runtime_logging import (
    MarketDataEventName,
    MarketDataRuntimeLog,
)
from tiewtrade.market_data.runtime_state import MarketDataRuntimeReason
from tiewtrade.market_data.source_errors import MarketDataFailureKind


def configured_log(name: str) -> tuple[MarketDataRuntimeLog, logging.Logger]:
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.propagate = True
    logger.setLevel(logging.DEBUG)
    return (
        MarketDataRuntimeLog(
            logger,
            symbol="BTCUSDT",
            timeframe="5m",
        ),
        logger,
    )


def custom_fields(record: logging.LogRecord) -> dict[str, object]:
    standard = {**logging.makeLogRecord({}).__dict__, "message": None}
    return {key: value for key, value in record.__dict__.items() if key not in standard}


OPENED = datetime(2026, 1, 1, 0, 15, tzinfo=UTC)
CLOSED = datetime(2026, 1, 1, 0, 18, tzinfo=UTC)
RECEIVED = datetime(2026, 1, 1, 0, 19, tzinfo=UTC)
BACKFILL_END = datetime(2026, 1, 1, 0, 20, tzinfo=UTC)
PROHIBITED_FIELDS = {
    "api_key",
    "secret",
    "credentials",
    "payload",
    "exception",
    "open",
    "high",
    "low",
    "close",
    "volume",
}


@pytest.mark.parametrize(
    ("emit", "event_name", "level", "expected_fields"),
    [
        pytest.param(
            lambda runtime_log: runtime_log.candle_discarded(
                open_time=OPENED,
                received_at=RECEIVED,
                discard_reason=CandleAcceptance.NOT_CLOSED,
            ),
            MarketDataEventName.CANDLE_DISCARDED,
            logging.INFO,
            {
                "event_name": "market_data.candle.discarded",
                "symbol": "BTCUSDT",
                "timeframe": "5m",
                "open_time": "2026-01-01T00:15:00+00:00",
                "received_at": "2026-01-01T00:19:00+00:00",
                "discard_reason": "not_closed",
            },
            id="candle-discarded",
        ),
        pytest.param(
            lambda runtime_log: runtime_log.clock_skew_detected(
                open_time=OPENED,
                close_time=CLOSED,
                received_at=RECEIVED,
            ),
            MarketDataEventName.CLOCK_SKEW_DETECTED,
            logging.WARNING,
            {
                "event_name": "market_data.clock_skew.detected",
                "symbol": "BTCUSDT",
                "timeframe": "5m",
                "open_time": "2026-01-01T00:15:00+00:00",
                "close_time": "2026-01-01T00:18:00+00:00",
                "received_at": "2026-01-01T00:19:00+00:00",
                "skew_seconds": 0.0,
            },
            id="clock-skew-detected",
        ),
        pytest.param(
            lambda runtime_log: runtime_log.stale_detected(
                reason=MarketDataRuntimeReason.DATA_STALE,
                last_accepted_open_time=None,
            ),
            MarketDataEventName.STALE_DETECTED,
            logging.WARNING,
            {
                "event_name": "market_data.stale.detected",
                "symbol": "BTCUSDT",
                "timeframe": "5m",
                "reason": "data_stale",
                "last_accepted_open_time": None,
            },
            id="stale-detected",
        ),
        pytest.param(
            lambda runtime_log: runtime_log.reconnect_attempted(
                attempt=3,
                delay_seconds=-2.0,
                reason=MarketDataRuntimeReason.SOURCE_DISCONNECTED,
            ),
            MarketDataEventName.RECONNECT_ATTEMPTED,
            logging.WARNING,
            {
                "event_name": "market_data.reconnect.attempted",
                "symbol": "BTCUSDT",
                "timeframe": "5m",
                "attempt": 3,
                "delay_seconds": 0.0,
                "reason": "source_disconnected",
            },
            id="reconnect-attempted",
        ),
        pytest.param(
            lambda runtime_log: runtime_log.backfill_completed(
                start=OPENED,
                end=BACKFILL_END,
                candle_count=2,
            ),
            MarketDataEventName.BACKFILL_COMPLETED,
            logging.INFO,
            {
                "event_name": "market_data.backfill.completed",
                "symbol": "BTCUSDT",
                "timeframe": "5m",
                "start": "2026-01-01T00:15:00+00:00",
                "end": "2026-01-01T00:20:00+00:00",
                "candle_count": 2,
            },
            id="backfill-completed",
        ),
        pytest.param(
            lambda runtime_log: runtime_log.backfill_failed(
                start=OPENED,
                end=BACKFILL_END,
                reason=MarketDataRuntimeReason.SOURCE_FATAL,
                failure_kind=MarketDataFailureKind.PROTOCOL,
            ),
            MarketDataEventName.BACKFILL_FAILED,
            logging.ERROR,
            {
                "event_name": "market_data.backfill.failed",
                "symbol": "BTCUSDT",
                "timeframe": "5m",
                "start": "2026-01-01T00:15:00+00:00",
                "end": "2026-01-01T00:20:00+00:00",
                "reason": "source_fatal",
                "failure_kind": "protocol",
            },
            id="backfill-failed",
        ),
        pytest.param(
            lambda runtime_log: runtime_log.failed_closed(
                reason=MarketDataRuntimeReason.SOURCE_ERROR,
                failure_kind=None,
            ),
            MarketDataEventName.RUNTIME_FAILED_CLOSED,
            logging.ERROR,
            {
                "event_name": "market_data.runtime.failed_closed",
                "symbol": "BTCUSDT",
                "timeframe": "5m",
                "reason": "source_error",
                "failure_kind": None,
            },
            id="runtime-failed-closed",
        ),
    ],
)
def test_typed_event_records_follow_exact_contract(
    caplog,
    emit: Callable[[MarketDataRuntimeLog], None],
    event_name: MarketDataEventName,
    level: int,
    expected_fields: dict[str, object],
) -> None:
    runtime_log, logger = configured_log(f"tests.market_data.{event_name.value}")
    caplog.set_level(logging.DEBUG, logger=logger.name)

    emit(runtime_log)

    record = caplog.records[-1]
    fields = custom_fields(record)
    assert record.getMessage() == event_name.value
    assert record.levelno == level
    assert fields == expected_fields
    assert PROHIBITED_FIELDS.isdisjoint(fields)
    for integer_field in ("attempt", "candle_count"):
        if integer_field in fields:
            assert type(fields[integer_field]) is int
    for float_field in ("delay_seconds", "skew_seconds"):
        if float_field in fields:
            assert type(fields[float_field]) is float
            assert fields[float_field] >= 0.0


class RaisingHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        raise RuntimeError("logging failed")


class InterruptingHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        raise KeyboardInterrupt(record.msg)


def test_logging_exception_does_not_escape() -> None:
    logger = logging.getLogger("tests.market_data.raise")
    logger.handlers[:] = [RaisingHandler()]
    logger.propagate = False
    runtime_log = MarketDataRuntimeLog(
        logger,
        symbol="BTCUSDT",
        timeframe="5m",
    )

    runtime_log.failed_closed(
        reason=MarketDataRuntimeReason.SOURCE_ERROR,
        failure_kind=None,
    )


def test_logging_base_exception_still_escapes() -> None:
    logger = logging.getLogger("tests.market_data.interrupt")
    logger.handlers[:] = [InterruptingHandler()]
    logger.propagate = False
    runtime_log = MarketDataRuntimeLog(
        logger,
        symbol="BTCUSDT",
        timeframe="5m",
    )

    with pytest.raises(KeyboardInterrupt):
        runtime_log.failed_closed(
            reason=MarketDataRuntimeReason.SOURCE_ERROR,
            failure_kind=None,
        )
