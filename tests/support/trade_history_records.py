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


def trade_fill(
    *,
    fill_id: str = "fill-1",
    basket_id: UUID = BASKET_ID,
    session_id: UUID = SESSION_ID,
    order_id: str = "order-1",
    exchange_trade_id: str | None = None,
    side: FillSide = FillSide.BUY,
    entry_number: int | None = 1,
    filled_at_utc: datetime = datetime(2026, 1, 1, tzinfo=UTC),
    price: Decimal = Decimal("100"),
    quantity: Decimal = Decimal("2"),
    notional: Decimal = Decimal("200"),
    commission: Decimal = Decimal("0.2"),
    commission_asset: str = "USDT",
    realized_pnl: Decimal = Decimal("0"),
    source: FillSource = FillSource.PAPER_EXECUTOR,
) -> TradeFill:
    return TradeFill(
        fill_id=fill_id,
        basket_id=basket_id,
        session_id=session_id,
        order_id=order_id,
        exchange_trade_id=exchange_trade_id,
        side=side,
        entry_number=entry_number,
        filled_at_utc=filled_at_utc,
        price=price,
        quantity=quantity,
        notional=notional,
        commission=commission,
        commission_asset=commission_asset,
        realized_pnl=realized_pnl,
        source=source,
    )


def basket_result(
    *,
    basket_id: UUID = BASKET_ID,
    session_id: UUID = SESSION_ID,
    trade_mode: TradeMode = TradeMode.PAPER,
    market_type: MarketType = MarketType.SPOT,
    symbol: str = "BTCUSDT",
    timeframe: str = "5m",
    strategy_preset_version: str = "rsi-step-grid-v1",
    opened_at_utc: datetime = datetime(2026, 1, 1, tzinfo=UTC),
    closed_at_utc: datetime | None = datetime(2026, 1, 2, tzinfo=UTC),
    entry_count: int = 1,
    invested_notional: Decimal = Decimal("200"),
    gross_realized_pnl: Decimal = Decimal("20"),
    trading_fees: Decimal = Decimal("0.42"),
    funding_fee: Decimal = Decimal("0"),
    net_realized_pnl: Decimal = Decimal("19.58"),
    status: BasketStatus = BasketStatus.CLOSED,
    leverage: int | None = None,
) -> BasketResult:
    return BasketResult(
        basket_id=basket_id,
        session_id=session_id,
        trade_mode=trade_mode,
        market_type=market_type,
        symbol=symbol,
        timeframe=timeframe,
        strategy_preset_version=strategy_preset_version,
        opened_at_utc=opened_at_utc,
        closed_at_utc=closed_at_utc,
        entry_count=entry_count,
        invested_notional=invested_notional,
        gross_realized_pnl=gross_realized_pnl,
        trading_fees=trading_fees,
        funding_fee=funding_fee,
        net_realized_pnl=net_realized_pnl,
        status=status,
        leverage=leverage,
    )
