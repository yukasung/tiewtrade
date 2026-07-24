from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from tiewtrade.trading.session_config import MarketType, TradeMode
from tiewtrade.trading.trade_history import (
    BasketResult,
    BasketStatus,
    FillSide,
    FillSource,
    TradeFill,
)

SESSION_ID = UUID("00000000-0000-0000-0000-000000000101")
BASKET_ID = UUID("00000000-0000-0000-0000-000000000102")


def trade_fill(**overrides: object) -> TradeFill:
    values: dict[str, object] = {
        "fill_id": "fill-1",
        "basket_id": BASKET_ID,
        "session_id": SESSION_ID,
        "order_id": "order-1",
        "exchange_trade_id": None,
        "side": FillSide.BUY,
        "entry_number": 1,
        "filled_at_utc": datetime(2026, 1, 1, tzinfo=UTC),
        "price": Decimal("100"),
        "quantity": Decimal("2"),
        "notional": Decimal("200"),
        "commission": Decimal("0.2"),
        "commission_asset": "USDT",
        "realized_pnl": Decimal("0"),
        "source": FillSource.PAPER_EXECUTOR,
    }
    values.update(overrides)
    return TradeFill(**values)  # type: ignore[arg-type]


def basket_result(**overrides: object) -> BasketResult:
    values: dict[str, object] = {
        "basket_id": BASKET_ID,
        "session_id": SESSION_ID,
        "trade_mode": TradeMode.PAPER,
        "market_type": MarketType.SPOT,
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "strategy_preset_version": "rsi-step-grid-v1",
        "opened_at_utc": datetime(2026, 1, 1, tzinfo=UTC),
        "closed_at_utc": datetime(2026, 1, 2, tzinfo=UTC),
        "entry_count": 1,
        "invested_notional": Decimal("200"),
        "gross_realized_pnl": Decimal("20"),
        "trading_fees": Decimal("0.42"),
        "funding_fee": Decimal("0"),
        "net_realized_pnl": Decimal("19.58"),
        "status": BasketStatus.CLOSED,
    }
    values.update(overrides)
    return BasketResult(**values)  # type: ignore[arg-type]
