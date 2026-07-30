import logging
from datetime import datetime
from enum import StrEnum

from tiewtrade.market_data.completed_candle_stream import CandleAcceptance
from tiewtrade.market_data.runtime_state import MarketDataRuntimeReason
from tiewtrade.market_data.source_errors import MarketDataFailureKind


class MarketDataEventName(StrEnum):
    CANDLE_DISCARDED = "market_data.candle.discarded"
    CLOCK_SKEW_DETECTED = "market_data.clock_skew.detected"
    STALE_DETECTED = "market_data.stale.detected"
    RECONNECT_ATTEMPTED = "market_data.reconnect.attempted"
    BACKFILL_COMPLETED = "market_data.backfill.completed"
    BACKFILL_FAILED = "market_data.backfill.failed"
    RUNTIME_FAILED_CLOSED = "market_data.runtime.failed_closed"


class MarketDataRuntimeLog:
    def __init__(
        self,
        logger: logging.Logger,
        *,
        symbol: str,
        timeframe: str,
    ) -> None:
        self._logger = logger
        self._common = {"symbol": symbol, "timeframe": timeframe}

    def candle_discarded(
        self,
        *,
        open_time: datetime,
        received_at: datetime,
        discard_reason: CandleAcceptance,
    ) -> None:
        self._emit(
            logging.INFO,
            MarketDataEventName.CANDLE_DISCARDED,
            {
                "open_time": open_time.isoformat(),
                "received_at": received_at.isoformat(),
                "discard_reason": discard_reason.value,
            },
        )

    def clock_skew_detected(
        self,
        *,
        open_time: datetime,
        close_time: datetime,
        received_at: datetime,
    ) -> None:
        self._emit(
            logging.WARNING,
            MarketDataEventName.CLOCK_SKEW_DETECTED,
            {
                "open_time": open_time.isoformat(),
                "close_time": close_time.isoformat(),
                "received_at": received_at.isoformat(),
                "skew_seconds": max(
                    0.0,
                    (close_time - received_at).total_seconds(),
                ),
            },
        )

    def stale_detected(
        self,
        *,
        reason: MarketDataRuntimeReason,
        last_accepted_open_time: datetime | None,
    ) -> None:
        self._emit(
            logging.WARNING,
            MarketDataEventName.STALE_DETECTED,
            {
                "reason": reason.value,
                "last_accepted_open_time": (
                    last_accepted_open_time.isoformat()
                    if last_accepted_open_time is not None
                    else None
                ),
            },
        )

    def reconnect_attempted(
        self,
        *,
        attempt: int,
        delay_seconds: float,
        reason: MarketDataRuntimeReason,
    ) -> None:
        self._emit(
            logging.WARNING,
            MarketDataEventName.RECONNECT_ATTEMPTED,
            {
                "attempt": attempt,
                "delay_seconds": max(0.0, delay_seconds),
                "reason": reason.value,
            },
        )

    def backfill_completed(
        self,
        *,
        start: datetime,
        end: datetime,
        candle_count: int,
    ) -> None:
        self._emit(
            logging.INFO,
            MarketDataEventName.BACKFILL_COMPLETED,
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "candle_count": candle_count,
            },
        )

    def backfill_failed(
        self,
        *,
        start: datetime,
        end: datetime,
        reason: MarketDataRuntimeReason,
        failure_kind: MarketDataFailureKind | None,
    ) -> None:
        self._emit(
            logging.ERROR,
            MarketDataEventName.BACKFILL_FAILED,
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "reason": reason.value,
                "failure_kind": (
                    failure_kind.value if failure_kind is not None else None
                ),
            },
        )

    def failed_closed(
        self,
        *,
        reason: MarketDataRuntimeReason,
        failure_kind: MarketDataFailureKind | None,
    ) -> None:
        self._emit(
            logging.ERROR,
            MarketDataEventName.RUNTIME_FAILED_CLOSED,
            {
                "reason": reason.value,
                "failure_kind": (
                    failure_kind.value if failure_kind is not None else None
                ),
            },
        )

    def _emit(
        self,
        level: int,
        event_name: MarketDataEventName,
        fields: dict[str, object],
    ) -> None:
        extra = {
            "event_name": event_name.value,
            **self._common,
            **fields,
        }
        try:
            self._logger.log(level, event_name.value, extra=extra)
        except Exception:
            return
