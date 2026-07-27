from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from tiewtrade.trading.session_config import MarketType, TradeMode


class BasketStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class FillSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class FillSource(StrEnum):
    PAPER_EXECUTOR = "paper_executor"
    BINANCE = "binance"


def _require_utc(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must use UTC")


def _require_non_negative(value: Decimal, field: str) -> None:
    if not value.is_finite() or value < 0:
        raise ValueError(f"{field} must be a finite non-negative decimal")


def _require_finite(value: Decimal, field: str) -> None:
    if not value.is_finite():
        raise ValueError(f"{field} must be finite")


def _require_positive(value: Decimal, field: str) -> None:
    if not value.is_finite() or value <= 0:
        raise ValueError(f"{field} must be a finite positive decimal")


def _require_non_empty(value: str, field: str) -> None:
    if not value:
        raise ValueError(f"{field} must not be empty")


@dataclass(frozen=True, slots=True)
class TradeFill:
    fill_id: str
    basket_id: UUID
    session_id: UUID
    order_id: str
    exchange_trade_id: str | None
    side: FillSide
    entry_number: int | None
    filled_at_utc: datetime
    price: Decimal
    quantity: Decimal
    notional: Decimal
    commission: Decimal
    commission_asset: str
    realized_pnl: Decimal
    source: FillSource

    def __post_init__(self) -> None:
        _require_non_empty(self.fill_id, "fill_id")
        _require_non_empty(self.order_id, "order_id")
        if self.exchange_trade_id is not None:
            _require_non_empty(self.exchange_trade_id, "exchange_trade_id")
        _require_utc(self.filled_at_utc, "filled_at_utc")
        _require_positive(self.price, "price")
        _require_positive(self.quantity, "quantity")
        _require_finite(self.notional, "notional")
        if self.notional != self.price * self.quantity:
            raise ValueError("notional must equal price * quantity")
        _require_non_negative(self.commission, "commission")
        _require_non_empty(self.commission_asset, "commission_asset")
        _require_finite(self.realized_pnl, "realized_pnl")
        if self.entry_number is not None and self.entry_number <= 0:
            raise ValueError("entry_number must be positive when present")


@dataclass(frozen=True, slots=True)
class BasketResult:
    basket_id: UUID
    session_id: UUID
    trade_mode: TradeMode
    market_type: MarketType
    symbol: str
    timeframe: str
    strategy_preset_version: str
    opened_at_utc: datetime
    closed_at_utc: datetime | None
    entry_count: int
    invested_notional: Decimal
    gross_realized_pnl: Decimal
    trading_fees: Decimal
    funding_fee: Decimal
    net_realized_pnl: Decimal
    status: BasketStatus
    leverage: int | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.symbol, "symbol")
        _require_non_empty(self.timeframe, "timeframe")
        _require_non_empty(self.strategy_preset_version, "strategy_preset_version")
        if self.market_type is MarketType.FUTURES:
            if (
                isinstance(self.leverage, bool)
                or not isinstance(self.leverage, int)
                or not 1 <= self.leverage <= 5
            ):
                raise ValueError("Futures Basket requires leverage between 1 and 5")
        elif self.leverage is not None:
            raise ValueError("Spot Basket must not have leverage")
        _require_utc(self.opened_at_utc, "opened_at_utc")
        if self.closed_at_utc is not None:
            _require_utc(self.closed_at_utc, "closed_at_utc")
        if self.entry_count < 1:
            raise ValueError("entry_count must be at least 1")
        _require_non_negative(self.invested_notional, "invested_notional")
        _require_finite(self.gross_realized_pnl, "gross_realized_pnl")
        _require_non_negative(self.trading_fees, "trading_fees")
        _require_finite(self.funding_fee, "funding_fee")
        _require_finite(self.net_realized_pnl, "net_realized_pnl")
        expected_net = self.gross_realized_pnl - self.trading_fees - self.funding_fee
        if self.net_realized_pnl != expected_net:
            raise ValueError("net_realized_pnl does not match gross minus costs")
        if self.status is BasketStatus.OPEN and self.closed_at_utc is not None:
            raise ValueError("open Basket must not have closed_at_utc")
        if self.status is BasketStatus.CLOSED and self.closed_at_utc is None:
            raise ValueError("closed Basket requires closed_at_utc")
