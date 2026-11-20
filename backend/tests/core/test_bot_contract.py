from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID, uuid5

import pytest

from tiewtrade.core.bots import BotLifecycleError, BotStatus, BotTransition, transition_bot
from tiewtrade.core.indicators import IndicatorStatus, IndicatorValue
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import (
    OrderIntent,
    OrderOrigin,
    OrderScope,
    OrderType,
    QuoteBudget,
    TradingMode,
)
from tiewtrade.core.positions import ExecutionSide, PositionPair
from tiewtrade.core.protections import ProtectionPrices
from tiewtrade.core.strategies import (
    StrategyContractError,
    StrategyDecision,
    StrategyDescriptor,
    StrategyDocument,
    StrategyInput,
    document_from_payload,
    document_payload,
    evaluate_strategy,
)

PAIR = PositionPair("BTC", "USDT")
SCOPE = OrderScope(UUID(int=1), UUID(int=2), TradingMode.PAPER)
DOC = StrategyDocument(1, (("funds", Money.of("123.00000001", "USDT")),))
SNAPSHOT = StrategyInput(
    PAIR,
    datetime(2026, 11, 19, tzinfo=UTC),
    1,
    2,
    Money.of("12.34567890", "USDT"),
    Money.of("100", "USDT"),
    Quantity.of(0, "BTC"),
    SCOPE,
    UUID(int=99),
    "fixture-market-input:1",
    (("ema20", IndicatorValue(Money.of("12", "USDT"), IndicatorStatus.READY)),),
)


DESCRIPTOR = StrategyDescriptor(
    "fixture", 1, 1, 1, frozenset({PAIR}), "1m", frozenset({"ema20"}), False
)


@dataclass(frozen=True)
class FixtureStrategy:
    intent: OrderIntent
    descriptor: StrategyDescriptor = DESCRIPTOR
    brackets: tuple[tuple[UUID, ProtectionPrices], ...] = ()

    def evaluate(
        self, snapshot: StrategyInput, configuration: StrategyDocument, state: StrategyDocument
    ) -> StrategyDecision:
        return StrategyDecision(state, (self.intent,), self.brackets)


def test_exact_versioned_document_roundtrip() -> None:
    document = StrategyDocument(1, (*DOC.fields, ("held", Quantity.of("0.00000001", "BTC"))))
    wire = document_payload(document)
    assert document_from_payload(wire, expected_version=1) == document
    with pytest.raises(StrategyContractError):
        document_from_payload(wire, expected_version=2)


@pytest.mark.parametrize(
    "payload",
    [
        {"version": True, "fields": []},
        {"version": 0, "fields": []},
        {"version": 2, "fields": []},
        {"version": 1, "fields": [], "unknown": None},
        {"version": 1, "fields": [["float", 1.5]]},
        {"version": 1, "fields": [["nested", []]]},
        {"version": 1, "fields": [["x", 1], ["x", 2]]},
        {"version": 1, "fields": [["x", {"unknown_numeric": "1"}]]},
        {"version": 1, "fields": [["", None]]},
    ],
)
def test_unsupported_documents_never_fall_back(payload: object) -> None:
    with pytest.raises(StrategyContractError):
        document_from_payload(payload, expected_version=1)


@pytest.mark.parametrize(
    "event", [BotTransition.READY, BotTransition.RESUME, BotTransition.REPLACE]
)
def test_lifecycle_requires_each_authorization_guard(event: BotTransition) -> None:
    status = BotStatus.STARTING if event is BotTransition.READY else BotStatus.STOPPED
    with pytest.raises(BotLifecycleError):
        transition_bot(status, event)
    if event is BotTransition.READY:
        for readiness, cleared in ((False, True), (True, False)):
            with pytest.raises(BotLifecycleError):
                transition_bot(status, event, readiness_proven=readiness, stop_cleared=cleared)
    if event is BotTransition.REPLACE:
        for cleared, flat in ((False, True), (True, False)):
            with pytest.raises(BotLifecycleError):
                transition_bot(status, event, stop_cleared=cleared, flatness_proven=flat)


def test_strategy_rejects_unready_indicator_and_foreign_scope() -> None:
    intent = OrderIntent(
        UUID(int=3),
        UUID(int=4),
        SCOPE,
        PAIR,
        OrderOrigin.BOT,
        ExecutionSide.BUY,
        OrderType.MARKET,
        QuoteBudget(Money.of("10", "USDT")),
    )
    strategy = FixtureStrategy(intent)
    result = evaluate_strategy(strategy, SNAPSHOT, DOC, DOC, scope=SCOPE)
    assert result == evaluate_strategy(strategy, SNAPSHOT, DOC, DOC, scope=SCOPE)
    assert result.intents == (intent,)
    required = replace(strategy, descriptor=replace(strategy.descriptor, requires_protection=True))
    with pytest.raises(StrategyContractError, match="requires a bracket"):
        evaluate_strategy(required, SNAPSHOT, DOC, DOC, scope=SCOPE)
    levels = ProtectionPrices(PAIR, stop_loss=Money.of("9", "USDT"))
    protected = replace(required, brackets=((intent.order_id, levels),))
    assert (
        evaluate_strategy(protected, SNAPSHOT, DOC, DOC, scope=SCOPE).brackets == protected.brackets
    )

    with pytest.raises(StrategyContractError, match="not ready"):
        evaluate_strategy(strategy, replace(SNAPSHOT, indicators=()), DOC, DOC, scope=SCOPE)
    with pytest.raises(StrategyContractError, match="scope"):
        evaluate_strategy(strategy, SNAPSHOT, DOC, DOC, scope=replace(SCOPE, mode=TradingMode.LIVE))


def test_stop_cannot_be_reopened_by_market_readiness() -> None:
    stopped = transition_bot(BotStatus.RUNNING, BotTransition.STOP)
    with pytest.raises(BotLifecycleError):
        transition_bot(stopped, BotTransition.READY, readiness_proven=True, stop_cleared=True)
    with pytest.raises(BotLifecycleError):
        transition_bot(stopped, BotTransition.REPLACE, stop_cleared=True)
    assert transition_bot(stopped, BotTransition.RESUME, stop_cleared=True) is BotStatus.RECOVERING
    assert (
        transition_bot(stopped, BotTransition.REPLACE, stop_cleared=True, flatness_proven=True)
        is BotStatus.RETIRED
    )


@pytest.mark.parametrize("mode", [TradingMode.PAPER, TradingMode.LIVE])
def test_shared_strategy_uses_only_caller_identity_in_both_modes(mode: TradingMode) -> None:
    class ContextStrategy:
        descriptor = DESCRIPTOR

        def evaluate(
            self, snapshot: StrategyInput, configuration: StrategyDocument, state: StrategyDocument
        ) -> StrategyDecision:
            return StrategyDecision(
                state,
                (
                    OrderIntent(
                        uuid5(snapshot.run_id, snapshot.input_identity + ":order"),
                        uuid5(snapshot.run_id, snapshot.input_identity + ":key"),
                        snapshot.scope,
                        snapshot.pair,
                        OrderOrigin.BOT,
                        ExecutionSide.BUY,
                        OrderType.MARKET,
                        QuoteBudget(Money.of("10", "USDT")),
                    ),
                ),
            )

    strategy = ContextStrategy()
    scope = replace(SCOPE, mode=mode)
    snapshot = replace(SNAPSHOT, scope=scope)
    first = evaluate_strategy(strategy, snapshot, DOC, DOC, scope=scope)
    assert first == evaluate_strategy(strategy, snapshot, DOC, DOC, scope=scope)
    paper = evaluate_strategy(strategy, SNAPSHOT, DOC, DOC, scope=SCOPE)
    assert first.state == paper.state
    assert first.intents == tuple(replace(value, scope=scope) for value in paper.intents)
    new_snapshot = replace(snapshot, run_id=UUID(int=100))
    assert (
        evaluate_strategy(strategy, new_snapshot, DOC, DOC, scope=scope).intents[0].idempotency_key
        != first.intents[0].idempotency_key
    )


@pytest.mark.parametrize("status", list(BotStatus))
@pytest.mark.parametrize("event", list(BotTransition))
def test_lifecycle_table_cannot_skip_readiness_or_revive_a_stop(
    status: BotStatus, event: BotTransition
) -> None:
    expected = {
        (BotStatus.STARTING, BotTransition.READY): BotStatus.RUNNING,
        (BotStatus.PAUSED, BotTransition.READY): BotStatus.RUNNING,
        (BotStatus.RECOVERING, BotTransition.READY): BotStatus.RUNNING,
        (BotStatus.STOPPED, BotTransition.RESUME): BotStatus.RECOVERING,
        (BotStatus.STOPPED, BotTransition.REPLACE): BotStatus.RETIRED,
    }
    expected[BotStatus.STARTING, BotTransition.SOURCE_UNAVAILABLE] = BotStatus.PAUSED
    for value in (BotStatus.RUNNING, BotStatus.PAUSED, BotStatus.RECOVERING):
        expected[value, BotTransition.SOURCE_UNAVAILABLE] = BotStatus.PAUSED
        expected[value, BotTransition.RECOVER] = BotStatus.RECOVERING
    for value in (
        BotStatus.STARTING,
        BotStatus.RUNNING,
        BotStatus.PAUSED,
        BotStatus.RECOVERING,
        BotStatus.STOPPED,
    ):
        expected[value, BotTransition.STOP] = BotStatus.STOPPED
    result = expected.get((status, event))
    if result is None:
        with pytest.raises(BotLifecycleError):
            transition_bot(
                status, event, readiness_proven=True, stop_cleared=True, flatness_proven=True
            )
    else:
        assert (
            transition_bot(
                status, event, readiness_proven=True, stop_cleared=True, flatness_proven=True
            )
            is result
        )
