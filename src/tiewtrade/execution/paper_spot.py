from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from tiewtrade.market_data.candle import Candle
from tiewtrade.strategies.rsi_step_grid.strategy import EntryIntent
from tiewtrade.trading.basket import Basket
from tiewtrade.trading.capital import SpotCapitalPlan
from tiewtrade.trading.session_config import SessionConfig
from tiewtrade.trading.symbol_rules import SymbolRules


@dataclass(frozen=True, slots=True)
class PaperSpotEntryFill:
    intent_id: str
    price: Decimal
    quantity: Decimal
    fee: Decimal
    filled_at: datetime


@dataclass(frozen=True, slots=True)
class PaperSpotExitFill:
    price: Decimal
    quantity: Decimal
    fee: Decimal
    filled_at: datetime


class PaperSpotExecutor:
    def __init__(self, session: SessionConfig, symbol_rules: SymbolRules) -> None:
        if session.spot_policy is None:
            raise ValueError("spot_policy is required for Paper Spot execution")

        self._session = session
        self._symbol_rules = symbol_rules
        self._capital_plan = SpotCapitalPlan.from_available(
            session.available_capital,
            session.spot_policy,
            session.entry_policy,
        )

    def fill_entry(
        self, intent: EntryIntent, candle: Candle
    ) -> PaperSpotEntryFill | None:
        price = self._symbol_rules.floor_price(
            candle.open * (Decimal("1") + self._session.slippage_bps / Decimal("10000"))
        )
        quantity = self._symbol_rules.floor_quantity(
            self._capital_plan.entry_notional / price
        )
        if not self._symbol_rules.meets_min_notional(price=price, quantity=quantity):
            return None

        notional = price * quantity
        return PaperSpotEntryFill(
            intent_id=intent.intent_id,
            price=price,
            quantity=quantity,
            fee=notional * self._session.fee_rate,
            filled_at=candle.open_time,
        )

    def fill_take_profit(
        self, basket: Basket, candle: Candle
    ) -> PaperSpotExitFill | None:
        if basket.take_profit_price is None or candle.high < basket.take_profit_price:
            return None

        price = self._symbol_rules.floor_price(
            basket.take_profit_price
            * (Decimal("1") - self._session.slippage_bps / Decimal("10000"))
        )
        quantity = basket.total_quantity
        notional = price * quantity
        return PaperSpotExitFill(
            price=price,
            quantity=quantity,
            fee=notional * self._session.fee_rate,
            filled_at=candle.close_time,
        )
