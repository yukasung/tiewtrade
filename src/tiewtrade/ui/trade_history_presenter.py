from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from tiewtrade.application.trade_history import TradeHistoryFilter
from tiewtrade.trading.session_config import MarketType, TradeMode
from tiewtrade.trading.trade_history import (
    BasketResult,
    BasketStatus,
    TradeFill,
)


@dataclass(frozen=True, slots=True)
class TradeHistoryFilterValues:
    symbol: str | None = None
    timeframe: str | None = None
    market_type: str | None = None
    trade_mode: str | None = None
    status: str | None = None
    from_date: date | None = None
    to_date: date | None = None


@dataclass(frozen=True, slots=True)
class BasketRow:
    basket_id: UUID
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FillRow:
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PageState:
    current_page: int
    total_pages: int
    previous_enabled: bool
    next_enabled: bool


def trade_history_filter(values: TradeHistoryFilterValues) -> TradeHistoryFilter:
    if values.from_date is not None and values.to_date is not None:
        if values.from_date > values.to_date:
            raise ValueError("From Date must not be after To Date")

    return TradeHistoryFilter(
        symbol=values.symbol,
        timeframe=values.timeframe,
        market_type=(
            MarketType(values.market_type) if values.market_type is not None else None
        ),
        trade_mode=(
            TradeMode(values.trade_mode) if values.trade_mode is not None else None
        ),
        status=BasketStatus(values.status) if values.status is not None else None,
        opened_from_utc=_utc_start(values.from_date),
        opened_before_utc=(
            _utc_start(values.to_date + timedelta(days=1))
            if values.to_date is not None
            else None
        ),
    )


def basket_rows(baskets: tuple[BasketResult, ...]) -> tuple[BasketRow, ...]:
    return tuple(
        BasketRow(
            basket_id=basket.basket_id,
            values=(
                _utc_text(basket.opened_at_utc),
                _display_enum(basket.trade_mode.value),
                _display_enum(basket.market_type.value),
                basket.symbol,
                basket.timeframe,
                str(basket.entry_count),
                _usdt_text(basket.invested_notional),
                _usdt_text(basket.gross_realized_pnl),
                _usdt_text(basket.trading_fees),
                _usdt_text(basket.funding_fee),
                pnl_text(basket.net_realized_pnl),
                _display_enum(basket.status.value),
            ),
        )
        for basket in baskets
    )


def fill_rows(fills: tuple[TradeFill, ...]) -> tuple[FillRow, ...]:
    return tuple(
        FillRow(
            values=(
                _utc_text(fill.filled_at_utc),
                _display_enum(fill.side.value),
                str(fill.entry_number) if fill.entry_number is not None else "—",
                _decimal_text(fill.price),
                _decimal_text(fill.quantity),
                _usdt_text(fill.notional),
                _usdt_text(fill.commission),
                pnl_text(fill.realized_pnl),
                _display_enum(fill.source.value),
            )
        )
        for fill in fills
    )


def page_state(*, page: int, page_size: int, total_items: int) -> PageState:
    if page_size < 1:
        raise ValueError("page_size must be positive")
    if total_items < 0:
        raise ValueError("total_items must not be negative")

    total_pages = max(1, (total_items + page_size - 1) // page_size)
    current_page = min(max(page, 1), total_pages)
    return PageState(
        current_page=current_page,
        total_pages=total_pages,
        previous_enabled=current_page > 1,
        next_enabled=current_page < total_pages,
    )


def pnl_text(value: Decimal) -> str:
    if value > 0:
        label = "Profit"
    elif value < 0:
        label = "Loss"
    else:
        label = "Break-even"
    return f"{_decimal_text(value)} USDT · {label}"


def _utc_start(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime(value.year, value.month, value.day, tzinfo=UTC)


def _utc_text(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S UTC")


def _usdt_text(value: Decimal) -> str:
    return f"{_decimal_text(value)} USDT"


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0.00"
    return format(value, "f")


def _display_enum(value: str) -> str:
    return value.replace("_", " ").title()
