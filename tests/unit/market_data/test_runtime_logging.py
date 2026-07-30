import logging
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


def test_candle_discard_record_has_exact_whitelisted_fields(caplog) -> None:
    runtime_log, logger = configured_log("tests.market_data.discard")
    caplog.set_level(logging.INFO, logger=logger.name)
    opened = datetime(2026, 1, 1, 0, 15, tzinfo=UTC)
    received = datetime(2026, 1, 1, 0, 19, tzinfo=UTC)

    runtime_log.candle_discarded(
        open_time=opened,
        received_at=received,
        discard_reason=CandleAcceptance.NOT_CLOSED,
    )

    record = caplog.records[-1]
    assert record.levelno == logging.INFO
    assert record.getMessage() == MarketDataEventName.CANDLE_DISCARDED.value
    assert custom_fields(record) == {
        "event_name": "market_data.candle.discarded",
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "open_time": "2026-01-01T00:15:00+00:00",
        "received_at": "2026-01-01T00:19:00+00:00",
        "discard_reason": "not_closed",
    }


def test_event_names_and_levels_are_stable(caplog) -> None:
    runtime_log, logger = configured_log("tests.market_data.events")
    caplog.set_level(logging.DEBUG, logger=logger.name)
    opened = datetime(2026, 1, 1, 0, 15, tzinfo=UTC)
    closed = datetime(2026, 1, 1, 0, 20, tzinfo=UTC)
    received = datetime(2026, 1, 1, 0, 19, tzinfo=UTC)
    calls = {
        MarketDataEventName.CANDLE_DISCARDED: lambda: runtime_log.candle_discarded(
            open_time=opened,
            received_at=received,
            discard_reason=CandleAcceptance.NOT_CLOSED,
        ),
        MarketDataEventName.CLOCK_SKEW_DETECTED: lambda: (
            runtime_log.clock_skew_detected(
                open_time=opened,
                close_time=closed,
                received_at=received,
            )
        ),
        MarketDataEventName.STALE_DETECTED: lambda: runtime_log.stale_detected(
            reason=MarketDataRuntimeReason.DATA_STALE,
            last_accepted_open_time=opened,
        ),
        MarketDataEventName.RECONNECT_ATTEMPTED: lambda: (
            runtime_log.reconnect_attempted(
                attempt=1,
                delay_seconds=1.0,
                reason=MarketDataRuntimeReason.DATA_STALE,
            )
        ),
        MarketDataEventName.BACKFILL_COMPLETED: lambda: runtime_log.backfill_completed(
            start=opened,
            end=closed,
            candle_count=1,
        ),
        MarketDataEventName.BACKFILL_FAILED: lambda: runtime_log.backfill_failed(
            start=opened,
            end=closed,
            reason=MarketDataRuntimeReason.SOURCE_FATAL,
            failure_kind=MarketDataFailureKind.PROTOCOL,
        ),
        MarketDataEventName.RUNTIME_FAILED_CLOSED: lambda: runtime_log.failed_closed(
            reason=MarketDataRuntimeReason.SOURCE_FATAL,
            failure_kind=MarketDataFailureKind.PROTOCOL,
        ),
    }
    expected_levels = {
        MarketDataEventName.CANDLE_DISCARDED: logging.INFO,
        MarketDataEventName.CLOCK_SKEW_DETECTED: logging.WARNING,
        MarketDataEventName.STALE_DETECTED: logging.WARNING,
        MarketDataEventName.RECONNECT_ATTEMPTED: logging.WARNING,
        MarketDataEventName.BACKFILL_COMPLETED: logging.INFO,
        MarketDataEventName.BACKFILL_FAILED: logging.ERROR,
        MarketDataEventName.RUNTIME_FAILED_CLOSED: logging.ERROR,
    }

    for event_name, call in calls.items():
        call()
        record = caplog.records[-1]
        assert record.getMessage() == event_name.value
        assert record.event_name == event_name.value
        assert record.levelno == expected_levels[event_name]


def test_clock_skew_and_failed_closed_serialize_diagnostic_values(caplog) -> None:
    runtime_log, logger = configured_log("tests.market_data.diagnostics")
    caplog.set_level(logging.DEBUG, logger=logger.name)
    opened = datetime(2026, 1, 1, 0, 15, tzinfo=UTC)
    closed = datetime(2026, 1, 1, 0, 20, tzinfo=UTC)
    received = datetime(2026, 1, 1, 0, 19, tzinfo=UTC)

    runtime_log.clock_skew_detected(
        open_time=opened,
        close_time=closed,
        received_at=received,
    )
    runtime_log.failed_closed(
        reason=MarketDataRuntimeReason.SOURCE_FATAL,
        failure_kind=MarketDataFailureKind.PROTOCOL,
    )

    assert caplog.records[-2].skew_seconds == 60.0
    assert caplog.records[-1].failure_kind == "protocol"


def test_records_do_not_include_sensitive_or_candle_price_fields(caplog) -> None:
    runtime_log, logger = configured_log("tests.market_data.sensitive")
    caplog.set_level(logging.DEBUG, logger=logger.name)

    runtime_log.failed_closed(
        reason=MarketDataRuntimeReason.SOURCE_ERROR,
        failure_kind=None,
    )

    fields = custom_fields(caplog.records[-1])
    prohibited = {
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
    assert prohibited.isdisjoint(fields)


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
