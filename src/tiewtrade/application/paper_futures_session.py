from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid5

from tiewtrade.execution.paper_futures import (
    PaperFuturesEntryFill,
    PaperFuturesExecutor,
    PaperFuturesExitFill,
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
from tiewtrade.trading.capital import FuturesCapitalPlan
from tiewtrade.trading.entry_pair import EntryPairLifecycle
from tiewtrade.trading.futures_margin import FuturesMarginModel
from tiewtrade.trading.position import PositionSide
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.symbol_rules import SymbolRules


class PaperFuturesSessionState(StrEnum):
    ACTIVE = "active"
    LIQUIDATED = "liquidated"
    FAILED_CLOSED = "failed_closed"


class PaperFuturesFailureReason(StrEnum):
    EXECUTION_ERROR = "execution_error"


class PaperFuturesSessionError(RuntimeError):
    """Paper Futures stopped because an execution invariant failed."""


@dataclass(frozen=True, slots=True)
class PaperFuturesSessionSnapshot:
    accepted: bool
    state: PaperFuturesSessionState
    pending_intent: EntryIntent | None
    entry_fill: PaperFuturesEntryFill | None
    exit_fill: PaperFuturesExitFill | None
    closed_basket: ClosedBasket | None
    basket_id: UUID | None
    basket_entry_count: int
    position_side: PositionSide | None
    take_profit_price: Decimal | None
    liquidation_price: Decimal | None
    account_equity: Decimal
    capital_plan: FuturesCapitalPlan
    failure_reason: PaperFuturesFailureReason | None


class PaperFuturesSession:
    def __init__(
        self,
        session: SessionConfig,
        market_data: MarketDataConfig,
        symbol_rules: SymbolRules,
        preset: RsiStepGridPreset,
    ) -> None:
        if (
            session.trade_mode is not TradeMode.PAPER
            or session.market_type is not MarketType.FUTURES
            or session.futures_policy is None
        ):
            raise ValueError(
                "PaperFuturesSession requires a Paper Futures configuration"
            )
        if session.preset_version != preset.version:
            raise ValueError("session preset version does not match the preset")

        self._session = session
        self._symbol_rules = symbol_rules
        self._preset = preset
        self._candles = CompletedCandleStream(market_data)
        self._executor = PaperFuturesExecutor(session, symbol_rules)
        self._margin = FuturesMarginModel(session.futures_policy)
        self._capital_plan = FuturesCapitalPlan.from_available(
            session.available_capital,
            session.futures_policy,
            session.entry_policy,
        )
        self._indicators = WilderIndicators(preset)
        self._strategy = RsiStepGridStrategy(session.session_id, preset)
        self._lifecycle = EntryPairLifecycle(session.entry_policy)
        self._state = PaperFuturesSessionState.ACTIVE
        self._failure_reason: PaperFuturesFailureReason | None = None
        self._basket: Basket | None = None
        self._pending_intent: EntryIntent | None = None
        self._liquidation_price: Decimal | None = None
        self._wallet_balance = session.available_capital
        self._account_equity = session.available_capital
        self._latest_mark_price: Decimal | None = None
        self._closed_basket_count = 0
        self._terminal_exit_fill: PaperFuturesExitFill | None = None
        self._terminal_closed_basket: ClosedBasket | None = None

    @property
    def snapshot(self) -> PaperFuturesSessionSnapshot:
        return self._snapshot(accepted=self._state is PaperFuturesSessionState.ACTIVE)

    def process_completed_candle(
        self,
        candle: Candle,
        *,
        received_at: datetime,
    ) -> PaperFuturesSessionSnapshot:
        if self._state is not PaperFuturesSessionState.ACTIVE:
            return self._snapshot(accepted=False)
        if not self._candles.accept(candle, received_at):
            return self._snapshot(accepted=False)

        self._latest_mark_price = candle.close
        basket_existed_at_open = self._basket is not None
        closed: ClosedBasket | None
        try:
            entry_fill = self._fill_pending_intent(candle)
            exit_fill = self._fill_liquidation(candle)
            if exit_fill is not None:
                closed = self._close_basket(exit_fill)
                self._state = PaperFuturesSessionState.LIQUIDATED
                self._pending_intent = None
                self._terminal_exit_fill = exit_fill
                self._terminal_closed_basket = closed
                return self._snapshot(
                    accepted=True,
                    entry_fill=entry_fill,
                    exit_fill=exit_fill,
                    closed_basket=closed,
                )

            take_profit_fill: PaperFuturesExitFill | None = None
            closed = None
            if basket_existed_at_open and entry_fill is None:
                take_profit_fill = self._fill_take_profit(candle)
                if take_profit_fill is not None:
                    closed = self._close_basket(take_profit_fill)
                    self._lifecycle.reset()

            indicators = self._indicators.update(candle)
            self._evaluate_strategy(candle, indicators)
            if entry_fill is None:
                self._mark_open_basket()
            return self._snapshot(
                accepted=True,
                entry_fill=entry_fill,
                exit_fill=take_profit_fill,
                closed_basket=closed,
            )
        except PaperFuturesSessionError:
            raise
        except Exception as error:
            self._fail_closed()
            raise PaperFuturesSessionError("Paper Futures execution failed") from error

    def warm_up_completed_candles(
        self,
        candles: Iterable[Candle],
        *,
        received_at: datetime,
    ) -> None:
        if self._state is not PaperFuturesSessionState.ACTIVE:
            raise PaperFuturesSessionError("Paper Futures session is not active")
        for candle in candles:
            if not self._candles.accept(candle, received_at):
                raise ValueError("warm-up requires new completed candles")
            self._indicators.update(candle)

    def _fill_pending_intent(self, candle: Candle) -> PaperFuturesEntryFill | None:
        if self._pending_intent is None:
            return None

        intent = self._pending_intent
        fill = self._executor.fill_entry(intent, candle)
        if fill is None:
            self._strategy.on_entry_rejected(intent.intent_id)
            self._pending_intent = None
            return None

        if self._basket is None:
            basket_id = uuid5(
                self._session.session_id,
                f"basket:{self._closed_basket_count + 1}",
            )
            candidate_basket = Basket(
                basket_id,
                self._session.entry_policy,
                self._preset.take_profit_atr_multiplier,
                position_side=fill.side,
            )
        else:
            candidate_basket = deepcopy(self._basket)
        candidate_lifecycle = deepcopy(self._lifecycle)
        candidate_strategy = deepcopy(self._strategy)

        candidate_basket.add_entry(
            price=fill.price,
            quantity=fill.quantity,
            fee=fill.fee,
            filled_at=fill.filled_at,
            atr=intent.atr,
            tick_size=self._symbol_rules.tick_size,
            position_side=fill.side,
        )
        margin_snapshot = self._margin.snapshot(
            side=candidate_basket.position_side,
            average_entry_price=candidate_basket.average_entry_price,
            quantity=candidate_basket.total_quantity,
            available_capital=self._wallet_balance,
            accumulated_entry_fees=candidate_basket.entry_fees,
            current_price=candle.close,
        )
        candidate_lifecycle.record_fill(fill.filled_at)
        candidate_strategy.on_entry_filled(intent.intent_id)

        self._basket = candidate_basket
        self._lifecycle = candidate_lifecycle
        self._strategy = candidate_strategy
        self._liquidation_price = margin_snapshot.liquidation_price
        self._account_equity = margin_snapshot.account_equity
        self._pending_intent = None
        return fill

    def _fill_liquidation(self, candle: Candle) -> PaperFuturesExitFill | None:
        if self._basket is None or self._liquidation_price is None:
            return None
        return self._executor.fill_liquidation(
            self._basket,
            candle,
            liquidation_price=self._liquidation_price,
        )

    def _fill_take_profit(self, candle: Candle) -> PaperFuturesExitFill | None:
        assert self._basket is not None
        return self._executor.fill_take_profit(self._basket, candle)

    def _close_basket(self, exit_fill: PaperFuturesExitFill) -> ClosedBasket:
        assert self._basket is not None
        closed = self._basket.close(
            exit_price=exit_fill.price,
            exit_fee=exit_fill.fee,
            closed_at=exit_fill.filled_at,
            close_reason=exit_fill.close_reason,
        )
        self._wallet_balance += closed.net_realized_pnl
        self._account_equity = self._wallet_balance
        self._basket = None
        self._liquidation_price = None
        self._closed_basket_count += 1
        return closed

    def _evaluate_strategy(
        self,
        candle: Candle,
        indicators: IndicatorSnapshot | None,
    ) -> None:
        if indicators is None:
            return
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

    def _mark_open_basket(self) -> None:
        if self._basket is None:
            self._account_equity = self._wallet_balance
            return
        assert self._latest_mark_price is not None
        margin_snapshot = self._margin.snapshot(
            side=self._basket.position_side,
            average_entry_price=self._basket.average_entry_price,
            quantity=self._basket.total_quantity,
            available_capital=self._wallet_balance,
            accumulated_entry_fees=self._basket.entry_fees,
            current_price=self._latest_mark_price,
        )
        self._liquidation_price = margin_snapshot.liquidation_price
        self._account_equity = margin_snapshot.account_equity

    def _fail_closed(self) -> None:
        self._state = PaperFuturesSessionState.FAILED_CLOSED
        self._failure_reason = PaperFuturesFailureReason.EXECUTION_ERROR
        self._pending_intent = None
        self._strategy = RsiStepGridStrategy(self._session.session_id, self._preset)

    def _snapshot(
        self,
        *,
        accepted: bool,
        entry_fill: PaperFuturesEntryFill | None = None,
        exit_fill: PaperFuturesExitFill | None = None,
        closed_basket: ClosedBasket | None = None,
    ) -> PaperFuturesSessionSnapshot:
        if closed_basket is None:
            closed_basket = self._terminal_closed_basket
        if exit_fill is None:
            exit_fill = self._terminal_exit_fill

        basket_id: UUID | None
        position_side: PositionSide | None
        if self._basket is not None:
            basket_id = self._basket.basket_id
            basket_entry_count = self._basket.entry_count
            position_side = self._basket.position_side
            take_profit_price = self._basket.take_profit_price
        else:
            basket_id = None if closed_basket is None else closed_basket.basket_id
            basket_entry_count = 0
            position_side = (
                None if closed_basket is None else closed_basket.position_side
            )
            take_profit_price = None

        return PaperFuturesSessionSnapshot(
            accepted=accepted,
            state=self._state,
            pending_intent=self._pending_intent,
            entry_fill=entry_fill,
            exit_fill=exit_fill,
            closed_basket=closed_basket,
            basket_id=basket_id,
            basket_entry_count=basket_entry_count,
            position_side=position_side,
            take_profit_price=take_profit_price,
            liquidation_price=self._liquidation_price,
            account_equity=self._account_equity,
            capital_plan=self._capital_plan,
            failure_reason=self._failure_reason,
        )
