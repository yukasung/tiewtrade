"""F-21 approved BUY predicate; all execution and storage remain outside strategy."""

from dataclasses import dataclass
from uuid import uuid5

from tiewtrade.core.market_data import CandleFinality
from tiewtrade.core.money import Money, Quantity, Scalar, basket_take_profit
from tiewtrade.core.orders import OrderIntent, OrderOrigin, OrderType, QuoteBudget
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.core.protections import ProtectionPrices
from tiewtrade.core.strategies import (
    StrategyContractError,
    StrategyDecision,
    StrategyDescriptor,
    StrategyDocument,
    StrategyInput,
)
from tiewtrade.core.strategy_config import STRATEGY_NAME
from tiewtrade.core.strategy_config import RsiStepGridConfig as RsiStepGridConfig
from tiewtrade.core.strategy_config import initial_state as initial_state

NAME = STRATEGY_NAME
INDICATORS = frozenset({"ema20", "ema50", "rsi14", "atr14"})


@dataclass(frozen=True, slots=True)
class RsiStepGridStrategy:
    config: RsiStepGridConfig

    @property
    def descriptor(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            NAME,
            1,
            1,
            1,
            frozenset({self.config.pair}),
            self.config.timeframe.value,
            INDICATORS,
            True,
            quote_trigger=True,
            execution_feedback_trigger=True,
            feedback_requires_indicators=False,
        )

    def evaluate(
        self, snapshot: StrategyInput, configuration: StrategyDocument, state: StrategyDocument
    ) -> StrategyDecision:
        if RsiStepGridConfig.from_document(configuration) != self.config:
            raise StrategyContractError("strategy configuration pin differs")
        self.config.validate_checkpoint(state)
        values = dict(state.fields)
        reset, pending = values["reset_close"], values["pending_id"]
        sequence, last = values["entry_sequence"], values["last_candle"]
        assert type(sequence) is int

        def checkpoint() -> StrategyDocument:
            return StrategyDocument(1, tuple((key, values[key]) for key, _ in state.fields))

        feedback = snapshot.feedback
        if feedback is not None:
            if pending is None or str(feedback.order_id) != pending:
                return StrategyDecision(state)
            if feedback.execution is not None:
                if feedback.execution.side is not ExecutionSide.BUY:
                    raise StrategyContractError("pending entry feedback must be a BUY")
                values["pending_filled"] = True
                values["reset_close"] = None
                values["reset_open_at"] = None
            if feedback.status is not None and feedback.status.terminal:
                if values["pending_filled"] or feedback.status.value == "FILLED":
                    values["reset_close"] = None
                    values["reset_open_at"] = None
                values["pending_id"] = None
                values["pending_filled"] = False
            return StrategyDecision(checkpoint())

        capability = snapshot.candle_input
        if capability is None or pending is not None:
            return StrategyDecision(state)
        candle = capability.candle
        if (
            candle.finality is not CandleFinality.CLOSED
            or capability.contiguous_count < 250
            or capability.backfilled
            or (candle.base, candle.quote, candle.timeframe)
            != (self.config.pair.base, self.config.pair.quote, self.config.timeframe)
            or candle.end_at > snapshot.observed_at
        ):
            return StrategyDecision(state)
        candle_key = candle.open_at.isoformat()
        if isinstance(last, str) and candle_key <= last:
            return StrategyDecision(state)
        indicators = {name: value.value for name, value in snapshot.indicators}
        ema20, ema50, atr = (indicators.get(key) for key in ("ema20", "ema50", "atr14"))
        rsi = indicators.get("rsi14")
        if (
            not all(type(value) is Money for value in (ema20, ema50, atr))
            or type(rsi) is not Scalar
        ):
            raise StrategyContractError("typed strategy indicators required")
        assert isinstance(ema20, Money) and isinstance(ema50, Money) and isinstance(atr, Money)
        assert isinstance(rsi, Scalar)
        if atr.amount < 0 or not 0 <= rsi.amount <= 100:
            raise StrategyContractError("invalid strategy indicator range")
        values["last_candle"] = candle_key
        if rsi.amount < 30:
            values["reset_close"] = candle.close
            values["reset_open_at"] = candle_key
            return StrategyDecision(checkpoint())
        if (
            type(reset) is not Money
            or not capability.arm_validated
            or rsi.amount <= 60
            or not ema20 > ema50
            or not candle.close > candle.open
            or not candle.close > reset
            or not candle.close > ema20
            or not candle.close > ema50
            or capability.exit_on_candle
            or capability.basket_triggered
            or capability.open_entries >= self.config.max_entries
            or snapshot.available_quote < self.config.capital_per_entry
        ):
            return StrategyDecision(checkpoint())
        order_id = uuid5(snapshot.run_id, f"{NAME}:entry:{sequence + 1}:{candle_key}")
        intent = OrderIntent(
            order_id,
            order_id,
            snapshot.scope,
            snapshot.pair,
            OrderOrigin.BOT,
            ExecutionSide.BUY,
            OrderType.MARKET,
            QuoteBudget(self.config.capital_per_entry),
        )
        levels = ProtectionPrices(
            snapshot.pair,
            take_profit=basket_take_profit(
                ((snapshot.price, Quantity.of(1, snapshot.pair.base)),),
                atr,
                capability.price_tick,
            ),
        )
        values["pending_id"] = str(order_id)
        values["pending_filled"] = False
        values["entry_sequence"] = sequence + 1
        return StrategyDecision(checkpoint(), (intent,), ((order_id, levels),))
