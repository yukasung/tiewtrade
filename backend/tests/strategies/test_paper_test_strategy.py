"""Independent entry/first-fill oracles for the gated Paper acceptance strategy."""

from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.strategies.fixtures import money, snapshot
from tiewtrade.core.market_data import CandleFinality, Timeframe
from tiewtrade.core.money import MoneyError, Quantity
from tiewtrade.core.orders import OrderStatus, QuoteBudget
from tiewtrade.core.protections import EntryAtrProtection, ProtectionError
from tiewtrade.core.strategies import (
    ExecutionFeedback,
    StrategyContractError,
    StrategyDocument,
    StrategyInput,
    evaluate_strategy,
)
from tiewtrade.core.strategy_config import PaperTestConfig, paper_test_initial_state
from tiewtrade.strategies.paper_test.strategy import PaperTestStrategy


def configured() -> PaperTestStrategy:
    source = snapshot()
    return PaperTestStrategy(PaperTestConfig(source.pair, Timeframe.M5, money("100")))


def source() -> StrategyInput:
    value = snapshot()
    assert value.candle_input is not None
    return replace(
        value,
        indicators=tuple(v for v in value.indicators if v[0] == "atr14"),
        candle_input=replace(value.candle_input, arm_validated=False),
    )


def test_green_needs_only_atr_and_declares_first_fill_policy_not_quote_targets() -> None:
    strategy, value = configured(), source()
    result = evaluate_strategy(
        strategy, value, strategy.config.document(), paper_test_initial_state(), scope=value.scope
    )
    assert len(result.intents) == 1
    assert isinstance(result.intents[0].size, QuoteBudget)
    assert result.intents[0].size.amount == money("100")
    policy = result.brackets[0][1]
    assert isinstance(policy, EntryAtrProtection)
    assert policy.atr == money("2")
    levels = policy.resolve(money("100"), money("0.01"))
    assert levels.take_profit == money("106") and levels.stop_loss == money("94")
    assert dict(result.state.fields)["pending_id"] == str(result.intents[0].order_id)
    assert (
        evaluate_strategy(
            strategy,
            value,
            strategy.config.document(),
            paper_test_initial_state(),
            scope=value.scope,
        )
        == result
    )
    assert not strategy.evaluate(value, strategy.config.document(), result.state).intents


@pytest.mark.parametrize(
    "kind",
    [
        "red",
        "doji",
        "open",
        "unconfirmed",
        "warmup",
        "backfill",
        "exit",
        "triggered",
        "entries",
        "held",
        "balance",
    ],
)
def test_no_unintended_entry(kind: str) -> None:
    strategy, value = configured(), source()
    cap = value.candle_input
    assert cap is not None
    if kind in ("red", "doji"):
        cap = replace(
            cap, candle=replace(cap.candle, close=money("99" if kind == "red" else "100"))
        )
    elif kind in ("open", "unconfirmed"):
        cap = replace(
            cap,
            candle=replace(
                cap.candle,
                finality=CandleFinality.OPEN if kind == "open" else CandleFinality.UNCONFIRMED,
            ),
        )
    elif kind == "warmup":
        cap = replace(cap, contiguous_count=249)
    elif kind == "backfill":
        cap = replace(cap, backfilled=True)
    elif kind == "exit":
        cap = replace(cap, exit_on_candle=True)
    elif kind == "triggered":
        cap = replace(cap, basket_triggered=True)
    elif kind == "entries":
        cap = replace(cap, open_entries=1)
    elif kind == "held":
        value = replace(value, held_base=Quantity.of("0.00001", "BTC"))
    elif kind == "balance":
        value = replace(value, available_quote=money("99"))
    assert not strategy.evaluate(
        replace(value, candle_input=cap), strategy.config.document(), paper_test_initial_state()
    ).intents


@pytest.mark.parametrize(
    "status", [OrderStatus.REJECTED, OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.FILLED]
)
def test_terminal_feedback_clears_pending_without_replaying_same_candle(
    status: OrderStatus,
) -> None:
    strategy, value = configured(), source()
    first = strategy.evaluate(value, strategy.config.document(), paper_test_initial_state())
    feedback = ExecutionFeedback(first.intents[0].order_id, revision=1, status=status)
    after = strategy.evaluate(
        replace(value, feedback=feedback, indicators=()), strategy.config.document(), first.state
    )
    assert dict(after.state.fields)["pending_id"] is None
    assert not strategy.evaluate(value, strategy.config.document(), after.state).intents
    assert (
        len(strategy.evaluate(snapshot(offset=1), strategy.config.document(), after.state).intents)
        == 1
    )


@pytest.mark.parametrize("timeframe", list(Timeframe))
def test_config_exact_codec_timeframe_and_no_max_entries_parameter(timeframe: Timeframe) -> None:
    strategy = configured()
    config = replace(strategy.config, timeframe=timeframe)
    assert PaperTestConfig.from_document(config.document()) == config
    with pytest.raises(StrategyContractError):
        PaperTestConfig.from_document(
            StrategyDocument(1, (*config.document().fields, ("max_entries", 1)))
        )


@pytest.mark.parametrize("price,atr", [("5", "2"), ("100", "0"), ("100", "-1")])
def test_invalid_stop_or_atr_cannot_be_installed(price: str, atr: str) -> None:
    with pytest.raises((ProtectionError, MoneyError)):
        EntryAtrProtection(source().pair, money(atr)).resolve(money(price), money("0.01"))


def test_registry_defaults_closed_even_with_f21_enabled() -> None:
    from tiewtrade.core.strategy_config import PAPER_TEST_STRATEGY
    from tiewtrade.services.engine.bot import StrategyRegistry

    document = configured().config.document()
    assert (
        StrategyRegistry(enable_f21=True).configured_implementation(
            PAPER_TEST_STRATEGY, 1, 1, 1, document
        )
        is None
    )
    assert isinstance(
        StrategyRegistry(enable_paper_test=True).configured_implementation(
            PAPER_TEST_STRATEGY, 1, 1, 1, document
        ),
        PaperTestStrategy,
    )


def test_existing_tick_floor_and_exact_stop_boundary() -> None:
    levels = EntryAtrProtection(source().pair, money("2.123")).resolve(
        money("100.001"), money("0.05")
    )
    assert levels.take_profit == money("106.35")
    assert levels.stop_loss == money("93.632")


@given(
    atr=st.integers(min_value=1, max_value=100), price=st.integers(min_value=301, max_value=10000)
)
def test_resolved_levels_bracket_the_fill_and_have_equal_atr_distance(atr: int, price: int) -> None:
    fill = money(str(price))
    levels = EntryAtrProtection(source().pair, money(str(atr))).resolve(fill, money("0.01"))
    assert levels.stop_loss is not None and levels.take_profit is not None
    assert levels.stop_loss < fill < levels.take_profit
    assert fill - levels.stop_loss == levels.take_profit - fill
