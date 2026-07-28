from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid5

from tiewtrade.execution.paper_spot import (
    PaperSpotEntryFill,
    PaperSpotExecutor,
    PaperSpotExitFill,
)
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.completed_candle_stream import CompletedCandleStream
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.strategies.rsi_step_grid.indicators import (
    IndicatorSnapshot,
    WilderIndicators,
)
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.strategies.rsi_step_grid.strategy import (
    EntryIntent,
    RsiStepGridStrategy,
)
from tiewtrade.trading.basket import Basket, ClosedBasket
from tiewtrade.trading.entry_pair import EntryPairLifecycle
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.symbol_rules import SymbolRules


class PaperSpotSessionState(StrEnum):
    ACTIVE = "active"
    FAILED_CLOSED = "failed_closed"


class PaperSpotFailureReason(StrEnum):
    EXECUTION_ERROR = "execution_error"


class PaperSpotSessionError(RuntimeError):
    """Paper Spot stopped because an execution invariant failed."""


@dataclass(frozen=True, slots=True)
class PaperSpotSessionSnapshot:
    accepted: bool
    state: PaperSpotSessionState
    failure_reason: PaperSpotFailureReason | None
    pending_intent: EntryIntent | None
    entry_fill: PaperSpotEntryFill | None
    take_profit_fill: PaperSpotExitFill | None
    closed_basket: ClosedBasket | None
    closed_basket_count: int
    basket_id: UUID | None
    basket_entry_count: int
    take_profit_price: Decimal | None


@dataclass(frozen=True, slots=True)
class PaperSpotSessionIdentity:
    session_id: UUID
    symbol: str
    timeframe: str
    preset_version: str


@dataclass(slots=True)
class _PaperSpotTransition:
    indicators: WilderIndicators
    strategy: RsiStepGridStrategy
    lifecycle: EntryPairLifecycle
    basket: Basket | None
    pending_intent: EntryIntent | None
    closed_basket_count: int


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
        self._identity = PaperSpotSessionIdentity(
            session_id=session.session_id,
            symbol=market_data.symbol,
            timeframe=market_data.timeframe,
            preset_version=session.preset_version,
        )
        self._symbol_rules = symbol_rules
        self._preset = preset
        self._candles = CompletedCandleStream(market_data)
        self._executor = PaperSpotExecutor(session, symbol_rules)
        self._indicators = WilderIndicators(preset)
        self._strategy = RsiStepGridStrategy(session.session_id, preset)
        self._lifecycle = EntryPairLifecycle(session.entry_policy)
        self._basket: Basket | None = None
        self._pending_intent: EntryIntent | None = None
        self._closed_basket_count = 0
        self._state = PaperSpotSessionState.ACTIVE
        self._failure_reason: PaperSpotFailureReason | None = None

    @property
    def identity(self) -> PaperSpotSessionIdentity:
        return self._identity

    @property
    def snapshot(self) -> PaperSpotSessionSnapshot:
        return self._snapshot(accepted=self._state is PaperSpotSessionState.ACTIVE)

    def process_completed_candle(
        self, candle: Candle, *, received_at: datetime
    ) -> PaperSpotSessionSnapshot:
        if self._state is not PaperSpotSessionState.ACTIVE:
            return self._snapshot(accepted=False)
        if not self._candles.accept(candle, received_at):
            return self._snapshot(accepted=False)

        try:
            transition = self._new_transition()
            basket_existed_at_candle_open = transition.basket is not None
            entry_fill = self._fill_pending_intent(transition, candle)
            entry_filled_on_current_candle = entry_fill is not None
            take_profit_fill: PaperSpotExitFill | None = None
            closed_basket: ClosedBasket | None = None

            if basket_existed_at_candle_open and not entry_filled_on_current_candle:
                take_profit_fill = self._fill_take_profit(transition, candle)
                if take_profit_fill is not None:
                    closed_basket = self._close_basket(transition, take_profit_fill)

            indicators = transition.indicators.update(candle)
            self._evaluate_strategy(transition, candle, indicators)
            self._commit_transition(transition)

            return self._snapshot(
                accepted=True,
                entry_fill=entry_fill,
                take_profit_fill=take_profit_fill,
                closed_basket=closed_basket,
            )
        except PaperSpotSessionError:
            raise
        except Exception as error:
            self._fail_closed()
            raise PaperSpotSessionError("Paper Spot execution failed") from error

    def warm_up_completed_candles(
        self,
        candles: Iterable[Candle],
        *,
        received_at: datetime,
    ) -> None:
        if self._state is not PaperSpotSessionState.ACTIVE:
            raise PaperSpotSessionError("Paper Spot session is not active")
        for candle in candles:
            if not self._candles.accept(candle, received_at):
                raise ValueError("warm-up requires new completed candles")
            self._indicators.update(candle)

    def _new_transition(self) -> _PaperSpotTransition:
        return _PaperSpotTransition(
            indicators=deepcopy(self._indicators),
            strategy=deepcopy(self._strategy),
            lifecycle=deepcopy(self._lifecycle),
            basket=deepcopy(self._basket),
            pending_intent=self._pending_intent,
            closed_basket_count=self._closed_basket_count,
        )

    def _commit_transition(self, transition: _PaperSpotTransition) -> None:
        self._indicators = transition.indicators
        self._strategy = transition.strategy
        self._lifecycle = transition.lifecycle
        self._basket = transition.basket
        self._pending_intent = transition.pending_intent
        self._closed_basket_count = transition.closed_basket_count

    def _fill_pending_intent(
        self,
        transition: _PaperSpotTransition,
        candle: Candle,
    ) -> PaperSpotEntryFill | None:
        if transition.pending_intent is None:
            return None

        intent = transition.pending_intent
        fill = self._executor.fill_entry(intent, candle)
        if fill is None:
            transition.strategy.on_entry_rejected(intent.intent_id)
            transition.pending_intent = None
            return None

        if transition.basket is None:
            basket_id = uuid5(
                self._session.session_id,
                f"basket:{transition.closed_basket_count + 1}",
            )
            transition.basket = Basket(
                basket_id,
                self._session.entry_policy,
                self._preset.take_profit_atr_multiplier,
            )
        transition.basket.add_entry(
            price=fill.price,
            quantity=fill.quantity,
            fee=fill.fee,
            filled_at=fill.filled_at,
            atr=intent.atr,
            tick_size=self._symbol_rules.tick_size,
        )
        transition.lifecycle.record_fill(fill.filled_at)
        transition.strategy.on_entry_filled(intent.intent_id)
        transition.pending_intent = None
        return fill

    def _fail_closed(self) -> None:
        self._state = PaperSpotSessionState.FAILED_CLOSED
        self._failure_reason = PaperSpotFailureReason.EXECUTION_ERROR
        self._pending_intent = None
        self._strategy = RsiStepGridStrategy(self._session.session_id, self._preset)

    def _fill_take_profit(
        self,
        transition: _PaperSpotTransition,
        candle: Candle,
    ) -> PaperSpotExitFill | None:
        assert transition.basket is not None
        return self._executor.fill_take_profit(transition.basket, candle)

    def _close_basket(
        self,
        transition: _PaperSpotTransition,
        exit_fill: PaperSpotExitFill,
    ) -> ClosedBasket:
        assert transition.basket is not None
        closed = transition.basket.close(
            exit_price=exit_fill.price,
            exit_fee=exit_fill.fee,
            closed_at=exit_fill.filled_at,
        )
        transition.basket = None
        transition.lifecycle.reset()
        transition.closed_basket_count += 1
        return closed

    def _evaluate_strategy(
        self,
        transition: _PaperSpotTransition,
        candle: Candle,
        indicators: IndicatorSnapshot | None,
    ) -> None:
        if indicators is None:
            return
        can_enter = transition.lifecycle.can_enter(candle.close_time) and (
            transition.basket is None
            or transition.basket.entry_count < self._session.entry_policy.max_entries
        )
        intent = transition.strategy.evaluate(
            candle,
            indicators,
            entry_number=transition.lifecycle.entry_count + 1,
            can_enter=can_enter,
        )
        if intent is not None:
            transition.pending_intent = intent

    def _snapshot(
        self,
        *,
        accepted: bool,
        entry_fill: PaperSpotEntryFill | None = None,
        take_profit_fill: PaperSpotExitFill | None = None,
        closed_basket: ClosedBasket | None = None,
    ) -> PaperSpotSessionSnapshot:
        if self._basket is not None:
            basket_id = self._basket.basket_id
        elif closed_basket is not None:
            basket_id = closed_basket.basket_id
        else:
            basket_id = None
        return PaperSpotSessionSnapshot(
            accepted=accepted,
            state=self._state,
            failure_reason=self._failure_reason,
            pending_intent=self._pending_intent,
            entry_fill=entry_fill,
            take_profit_fill=take_profit_fill,
            closed_basket=closed_basket,
            closed_basket_count=self._closed_basket_count,
            basket_id=basket_id,
            basket_entry_count=0 if self._basket is None else self._basket.entry_count,
            take_profit_price=(
                None if self._basket is None else self._basket.take_profit_price
            ),
        )
