from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from tiewtrade.market_data.candle import Candle
from tiewtrade.strategies.rsi_step_grid.strategy import EntryIntent
from tiewtrade.trading.basket import Basket, BasketCloseReason
from tiewtrade.trading.capital import FuturesCapitalPlan
from tiewtrade.trading.position import PositionSide
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.symbol_rules import SymbolRules


@dataclass(frozen=True, slots=True)
class PaperFuturesEntryFill:
    order_id: str
    fill_id: str
    intent_id: str
    side: PositionSide
    price: Decimal
    quantity: Decimal
    fee: Decimal
    filled_at: datetime


@dataclass(frozen=True, slots=True)
class PaperFuturesExitFill:
    order_id: str
    fill_id: str
    side: PositionSide
    close_reason: BasketCloseReason
    price: Decimal
    quantity: Decimal
    fee: Decimal
    filled_at: datetime


class PaperFuturesExecutor:
    def __init__(self, session: SessionConfig, symbol_rules: SymbolRules) -> None:
        if (
            session.trade_mode is not TradeMode.PAPER
            or session.market_type is not MarketType.FUTURES
            or session.futures_policy is None
        ):
            raise ValueError(
                "PaperFuturesExecutor requires a Paper Futures configuration"
            )

        self._session = session
        self._symbol_rules = symbol_rules
        self._capital_plan = FuturesCapitalPlan.from_available(
            session.available_capital,
            session.futures_policy,
            session.entry_policy,
        )

    def fill_entry(
        self, intent: EntryIntent, candle: Candle
    ) -> PaperFuturesEntryFill | None:
        slippage = self._slippage
        if intent.side is PositionSide.LONG:
            raw_price = candle.open * (Decimal("1") + slippage)
            price = self._symbol_rules.ceil_price(raw_price)
        else:
            raw_price = candle.open * (Decimal("1") - slippage)
            price = self._symbol_rules.floor_price(raw_price)

        if not price.is_finite() or price <= 0:
            return None

        quantity = self._symbol_rules.floor_quantity(
            self._capital_plan.target_notional_per_entry / price
        )
        if not self._symbol_rules.meets_min_notional(price=price, quantity=quantity):
            return None

        order_id = f"entry:{intent.intent_id}"
        return PaperFuturesEntryFill(
            order_id=order_id,
            fill_id=f"paper:{self._session.session_id}:{order_id}:fill",
            intent_id=intent.intent_id,
            side=intent.side,
            price=price,
            quantity=quantity,
            fee=price * quantity * self._session.fee_rate,
            filled_at=candle.open_time,
        )

    def fill_take_profit(
        self, basket: Basket, candle: Candle
    ) -> PaperFuturesExitFill | None:
        if basket.take_profit_price is None:
            return None

        if basket.position_side is PositionSide.LONG:
            if candle.high < basket.take_profit_price:
                return None
            price = self._symbol_rules.floor_price(
                basket.take_profit_price * (Decimal("1") - self._slippage)
            )
        else:
            if candle.low > basket.take_profit_price:
                return None
            price = self._symbol_rules.ceil_price(
                basket.take_profit_price * (Decimal("1") + self._slippage)
            )

        return self._exit_fill(
            basket=basket,
            price=price,
            close_reason=BasketCloseReason.TAKE_PROFIT,
            filled_at=candle.close_time,
        )

    def fill_liquidation(
        self,
        basket: Basket,
        candle: Candle,
        *,
        liquidation_price: Decimal,
    ) -> PaperFuturesExitFill | None:
        if not liquidation_price.is_finite() or liquidation_price <= 0:
            raise ValueError("liquidation_price must be finite and positive")

        if basket.position_side is PositionSide.LONG:
            if candle.low > liquidation_price:
                return None
            raw_price = min(candle.open, liquidation_price) * (
                Decimal("1") - self._slippage
            )
            price = self._symbol_rules.floor_price(raw_price)
        else:
            if candle.high < liquidation_price:
                return None
            raw_price = max(candle.open, liquidation_price) * (
                Decimal("1") + self._slippage
            )
            price = self._symbol_rules.ceil_price(raw_price)

        return self._exit_fill(
            basket=basket,
            price=price,
            close_reason=BasketCloseReason.LIQUIDATION,
            filled_at=candle.close_time,
        )

    @property
    def _slippage(self) -> Decimal:
        return self._session.slippage_bps / Decimal("10000")

    def _exit_fill(
        self,
        *,
        basket: Basket,
        price: Decimal,
        close_reason: BasketCloseReason,
        filled_at: datetime,
    ) -> PaperFuturesExitFill | None:
        if not price.is_finite() or price <= 0:
            return None

        quantity = basket.total_quantity
        if not quantity.is_finite() or quantity <= 0:
            return None

        order_id = f"{close_reason.value}:{basket.basket_id}"
        return PaperFuturesExitFill(
            order_id=order_id,
            fill_id=f"paper:{self._session.session_id}:{order_id}:fill",
            side=basket.position_side,
            close_reason=close_reason,
            price=price,
            quantity=quantity,
            fee=price * quantity * self._session.fee_rate,
            filled_at=filled_at,
        )
