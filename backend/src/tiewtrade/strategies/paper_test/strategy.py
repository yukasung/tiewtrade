"""One protected entry per CLOSED green candle, while completely flat."""

from dataclasses import dataclass
from uuid import uuid5

from tiewtrade.core.market_data import CandleFinality
from tiewtrade.core.money import Money
from tiewtrade.core.orders import OrderIntent, OrderOrigin, OrderType, QuoteBudget
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.core.protections import EntryAtrProtection
from tiewtrade.core.strategies import (
    StrategyContractError,
    StrategyDecision,
    StrategyDescriptor,
    StrategyDocument,
    StrategyInput,
)
from tiewtrade.core.strategy_config import PAPER_TEST_STRATEGY, PaperTestConfig


@dataclass(frozen=True, slots=True)
class PaperTestStrategy:
    config: PaperTestConfig

    @property
    def descriptor(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            PAPER_TEST_STRATEGY,
            1,
            1,
            1,
            frozenset({self.config.pair}),
            self.config.timeframe.value,
            frozenset({"atr14"}),
            True,
            quote_trigger=True,
            execution_feedback_trigger=True,
            feedback_requires_indicators=False,
        )

    def evaluate(
        self, snapshot: StrategyInput, configuration: StrategyDocument, state: StrategyDocument
    ) -> StrategyDecision:
        if PaperTestConfig.from_document(configuration) != self.config:
            raise StrategyContractError("test configuration pin differs")
        self.config.validate_checkpoint(state)
        values = dict(state.fields)
        pending = values["pending_id"]
        if snapshot.feedback is not None:
            feedback = snapshot.feedback
            if pending != str(feedback.order_id):
                return StrategyDecision(state)
            if feedback.execution is not None:
                if feedback.execution.side is not ExecutionSide.BUY:
                    raise StrategyContractError("entry feedback must be BUY")
                values["pending_filled"] = True
            if feedback.status is not None and feedback.status.terminal:
                values["pending_id"] = None
                values["pending_filled"] = False
            return StrategyDecision(StrategyDocument(1, tuple(values.items())))
        capability = snapshot.candle_input
        if capability is None or pending is not None:
            return StrategyDecision(state)
        candle = capability.candle
        last = values["last_candle"]
        if (
            candle.finality is not CandleFinality.CLOSED
            or capability.contiguous_count < 250
            or capability.backfilled
            or candle.end_at > snapshot.observed_at
            or (candle.base, candle.quote, candle.timeframe)
            != (self.config.pair.base, self.config.pair.quote, self.config.timeframe)
            or (isinstance(last, str) and candle.open_at.isoformat() <= last)
        ):
            return StrategyDecision(state)
        atr = dict(snapshot.indicators).get("atr14")
        if atr is None or type(atr.value) is not Money or atr.value.amount <= 0:
            raise StrategyContractError("positive signal ATR required")
        values["last_candle"] = candle.open_at.isoformat()
        if (
            not candle.close > candle.open
            or capability.exit_on_candle
            or capability.basket_triggered
            or capability.open_entries
            or snapshot.held_base.amount > 0
            or snapshot.available_quote < self.config.capital_per_entry
        ):
            return StrategyDecision(StrategyDocument(1, tuple(values.items())))
        sequence = values["entry_sequence"]
        assert type(sequence) is int
        order = uuid5(
            snapshot.run_id, f"{PAPER_TEST_STRATEGY}:{sequence + 1}:{candle.open_at.isoformat()}"
        )
        intent = OrderIntent(
            order,
            order,
            snapshot.scope,
            snapshot.pair,
            OrderOrigin.BOT,
            ExecutionSide.BUY,
            OrderType.MARKET,
            QuoteBudget(self.config.capital_per_entry),
        )
        values.update(pending_id=str(order), pending_filled=False, entry_sequence=sequence + 1)
        return StrategyDecision(
            StrategyDocument(1, tuple(values.items())),
            (intent,),
            ((order, EntryAtrProtection(snapshot.pair, atr.value)),),
        )
