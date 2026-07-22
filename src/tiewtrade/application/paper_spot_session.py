from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from tiewtrade.execution.paper_spot import PaperSpotEntryFill, PaperSpotExecutor
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.completed_candle_stream import CompletedCandleStream
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.strategies.rsi_step_grid.indicators import WilderIndicators
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.strategies.rsi_step_grid.strategy import (
    EntryIntent,
    RsiStepGridStrategy,
)
from tiewtrade.trading.basket import Basket, ClosedBasket
from tiewtrade.trading.entry_pair import EntryPairLifecycle
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.symbol_rules import SymbolRules


@dataclass(frozen=True, slots=True)
class PaperSpotSessionSnapshot:
    accepted: bool
    pending_intent: EntryIntent | None
    entry_fill: PaperSpotEntryFill | None
    closed_basket: ClosedBasket | None
    basket_entry_count: int
    take_profit_price: Decimal | None


class PaperSpotSession:
    def __init__(
        self,
        session: SessionConfig,
        market_data: MarketDataConfig,
        symbol_rules: SymbolRules,
        preset: RsiStepGridPreset,
    ) -> None:
        if (
            session.trade_mode is not TradeMode.PAPER
            or session.market_type is not MarketType.SPOT
        ):
            raise ValueError("PaperSpotSession requires a Paper Spot configuration")
        if session.preset_version != preset.version:
            raise ValueError("session preset version does not match the preset")

        self._session = session
        self._symbol_rules = symbol_rules
        self._preset = preset
        self._candles = CompletedCandleStream(market_data)
        self._executor = PaperSpotExecutor(session, symbol_rules)
        self._indicators = WilderIndicators(preset)
        self._strategy = RsiStepGridStrategy(session.session_id, preset)
        self._lifecycle = EntryPairLifecycle(session.entry_policy)
        self._basket: Basket | None = None
        self._pending_intent: EntryIntent | None = None

    def process_completed_candle(
        self, candle: Candle, *, received_at: datetime
    ) -> PaperSpotSessionSnapshot:
        if not self._candles.accept(candle, received_at):
            return self._snapshot(accepted=False)

        basket_existed_at_candle_open = self._basket is not None
        entry_fill = self._fill_pending_intent(candle)
        entry_filled_on_current_candle = entry_fill is not None
        closed_basket: ClosedBasket | None = None

        if basket_existed_at_candle_open and not entry_filled_on_current_candle:
            closed_basket = self._fill_take_profit(candle)

        indicators = self._indicators.update(candle)
        if indicators is not None:
            can_enter = self._lifecycle.can_enter(candle.close_time) and (
                self._basket is None
                or self._basket.entry_count < self._session.entry_policy.max_entries
            )
            intent = self._strategy.evaluate(
                candle,
                indicators,
                entry_number=self._lifecycle.entry_count + 1,
                can_enter=can_enter,
            )
            if intent is not None:
                self._pending_intent = intent

        return self._snapshot(
            accepted=True,
            entry_fill=entry_fill,
            closed_basket=closed_basket,
        )

    def _fill_pending_intent(self, candle: Candle) -> PaperSpotEntryFill | None:
        if self._pending_intent is None:
            return None

        fill = self._executor.fill_entry(self._pending_intent, candle)
        if fill is None:
            self._strategy.on_entry_rejected(self._pending_intent.intent_id)
            self._pending_intent = None
            return None

        if self._basket is None:
            self._basket = Basket(
                self._session.entry_policy,
                self._preset.take_profit_atr_multiplier,
            )
        self._basket.add_entry(
            price=fill.price,
            quantity=fill.quantity,
            fee=fill.fee,
            filled_at=fill.filled_at,
            atr=self._pending_intent.atr,
            tick_size=self._symbol_rules.tick_size,
        )
        self._lifecycle.record_fill(fill.filled_at)
        self._strategy.on_entry_filled(self._pending_intent.intent_id)
        self._pending_intent = None
        return fill

    def _fill_take_profit(self, candle: Candle) -> ClosedBasket | None:
        assert self._basket is not None
        exit_fill = self._executor.fill_take_profit(self._basket, candle)
        if exit_fill is None:
            return None

        closed = self._basket.close(
            exit_price=exit_fill.price,
            exit_fee=exit_fill.fee,
            closed_at=exit_fill.filled_at,
        )
        self._basket = None
        self._lifecycle.reset()
        return closed

    def _snapshot(
        self,
        *,
        accepted: bool,
        entry_fill: PaperSpotEntryFill | None = None,
        closed_basket: ClosedBasket | None = None,
    ) -> PaperSpotSessionSnapshot:
        return PaperSpotSessionSnapshot(
            accepted=accepted,
            pending_intent=self._pending_intent,
            entry_fill=entry_fill,
            closed_basket=closed_basket,
            basket_entry_count=0 if self._basket is None else self._basket.entry_count,
            take_profit_price=(
                None if self._basket is None else self._basket.take_profit_price
            ),
        )
