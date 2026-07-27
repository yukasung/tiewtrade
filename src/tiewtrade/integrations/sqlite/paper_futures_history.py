from dataclasses import dataclass, replace
from decimal import Decimal
from uuid import UUID

from tiewtrade.application.paper_futures_session import PaperFuturesSessionIdentity
from tiewtrade.execution.paper_futures import (
    PaperFuturesEntryFill,
    PaperFuturesExitFill,
)
from tiewtrade.integrations.sqlite.trade_history import SQLiteTradeHistory
from tiewtrade.trading.basket import ClosedBasket
from tiewtrade.trading.position import PositionSide
from tiewtrade.trading.session_config import MarketType, TradeMode
from tiewtrade.trading.trade_history import (
    BasketResult,
    BasketStatus,
    FillSide,
    FillSource,
    TradeFill,
)

PAPER_FUTURES_FUNDING_FEE = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class PaperFuturesHistoryContext:
    session_id: UUID
    symbol: str
    timeframe: str
    preset_version: str
    commission_asset: str
    leverage: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.leverage, bool)
            or not isinstance(self.leverage, int)
            or not 1 <= self.leverage <= 5
        ):
            raise ValueError("leverage must be between 1 and 5")

    @property
    def session_identity(self) -> PaperFuturesSessionIdentity:
        return PaperFuturesSessionIdentity(
            session_id=self.session_id,
            symbol=self.symbol,
            timeframe=self.timeframe,
            preset_version=self.preset_version,
            leverage=self.leverage,
        )


class PaperFuturesSQLiteHistory:
    def __init__(
        self,
        context: PaperFuturesHistoryContext,
        store: SQLiteTradeHistory,
    ) -> None:
        self._context = context
        self._store = store

    @property
    def session_identity(self) -> PaperFuturesSessionIdentity:
        return self._context.session_identity

    def record_entry(
        self,
        *,
        basket_id: UUID,
        entry_number: int,
        fill: PaperFuturesEntryFill,
    ) -> bool:
        normalized_fill = TradeFill(
            fill_id=fill.fill_id,
            basket_id=basket_id,
            session_id=self._context.session_id,
            order_id=fill.order_id,
            exchange_trade_id=None,
            side=_entry_fill_side(fill.side),
            entry_number=entry_number,
            filled_at_utc=fill.filled_at,
            price=fill.price,
            quantity=fill.quantity,
            notional=fill.price * fill.quantity,
            commission=fill.fee,
            commission_asset=self._context.commission_asset,
            realized_pnl=Decimal("0"),
            source=FillSource.PAPER_EXECUTOR,
        )
        existing = self._store.get_basket(basket_id)
        if existing is None:
            basket = BasketResult(
                basket_id=basket_id,
                session_id=self._context.session_id,
                trade_mode=TradeMode.PAPER,
                market_type=MarketType.FUTURES,
                symbol=self._context.symbol,
                timeframe=self._context.timeframe,
                strategy_preset_version=self._context.preset_version,
                opened_at_utc=fill.filled_at,
                closed_at_utc=None,
                entry_count=1,
                invested_notional=normalized_fill.notional,
                gross_realized_pnl=Decimal("0"),
                trading_fees=normalized_fill.commission,
                funding_fee=PAPER_FUTURES_FUNDING_FEE,
                net_realized_pnl=-normalized_fill.commission,
                status=BasketStatus.OPEN,
                leverage=self._context.leverage,
            )
            return self._store.record_open_basket(basket, normalized_fill)

        order_already_filled = any(
            item.order_id == normalized_fill.order_id
            for item in self._store.list_fills(basket_id)
        )
        basket = replace(
            existing,
            leverage=self._context.leverage,
            entry_count=(
                existing.entry_count
                if order_already_filled
                else existing.entry_count + 1
            ),
            invested_notional=existing.invested_notional + normalized_fill.notional,
            trading_fees=existing.trading_fees + normalized_fill.commission,
            net_realized_pnl=(
                existing.gross_realized_pnl
                - existing.trading_fees
                - normalized_fill.commission
                - existing.funding_fee
            ),
        )
        return self._store.record_entry_fill(basket, normalized_fill)

    def record_close(
        self,
        *,
        basket_id: UUID,
        fill: PaperFuturesExitFill,
        closed: ClosedBasket,
    ) -> bool:
        if closed.basket_id != basket_id:
            raise ValueError("closed Basket does not match basket_id")
        if closed.position_side is not fill.side:
            raise ValueError("closed Basket and exit Fill use different sides")
        if closed.funding_fee != 0:
            raise ValueError("Paper Futures Funding Fee must be 0.00")

        existing = self._store.get_basket(basket_id)
        if existing is None:
            raise ValueError("Basket does not exist")

        normalized_fill = TradeFill(
            fill_id=fill.fill_id,
            basket_id=basket_id,
            session_id=self._context.session_id,
            order_id=fill.order_id,
            exchange_trade_id=None,
            side=_exit_fill_side(fill.side),
            entry_number=None,
            filled_at_utc=fill.filled_at,
            price=fill.price,
            quantity=fill.quantity,
            notional=fill.price * fill.quantity,
            commission=fill.fee,
            commission_asset=self._context.commission_asset,
            realized_pnl=closed.net_realized_pnl,
            source=FillSource.PAPER_EXECUTOR,
        )
        basket = replace(
            existing,
            leverage=self._context.leverage,
            closed_at_utc=closed.closed_at,
            entry_count=closed.entry_count,
            gross_realized_pnl=closed.gross_realized_pnl,
            trading_fees=closed.trading_fees,
            funding_fee=PAPER_FUTURES_FUNDING_FEE,
            net_realized_pnl=closed.net_realized_pnl,
            status=BasketStatus.CLOSED,
        )
        return self._store.record_closed_basket(basket, normalized_fill)


def _entry_fill_side(side: PositionSide) -> FillSide:
    if side is PositionSide.LONG:
        return FillSide.BUY
    return FillSide.SELL


def _exit_fill_side(side: PositionSide) -> FillSide:
    if side is PositionSide.LONG:
        return FillSide.SELL
    return FillSide.BUY
