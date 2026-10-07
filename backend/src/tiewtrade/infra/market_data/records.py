from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Literal

from tiewtrade.core.market_data import Candle, CandleWindow
from tiewtrade.infra.db.errors import InfraError


class MarketDataInputError(InfraError):
    code: ClassVar[str] = "INPUT_REJECTED"


class UnsupportedSeriesError(MarketDataInputError):
    code: ClassVar[str] = "UNSUPPORTED_SERIES"


class RetentionError(MarketDataInputError):
    code: ClassVar[str] = "RANGE_OUTSIDE_RETENTION"


class WindowTooLargeError(MarketDataInputError):
    code: ClassVar[str] = "WINDOW_TOO_LARGE"


class PartitionUnavailableError(InfraError):
    code: ClassVar[str] = "PARTITION_UNAVAILABLE"


class StaleClaimError(InfraError):
    code: ClassVar[str] = "STALE_CLAIM"


@dataclass(frozen=True, slots=True)
class StoredCandle:
    candle: Candle
    fetch_started_at: datetime
    last_checked_at: datetime


@dataclass(frozen=True, slots=True)
class CandleRead:
    candles: tuple[StoredCandle, ...]
    gaps: tuple[CandleWindow, ...]
    coverage: Literal["PRESENT", "INCOMPLETE", "UNAVAILABLE"]
    observed_at: datetime
    refresh_pending: bool
    status: str | None
    failure_code: str | None
