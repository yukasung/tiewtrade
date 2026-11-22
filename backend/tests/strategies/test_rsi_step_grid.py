from dataclasses import replace
from typing import Any

import pytest

from tests.strategies.fixtures import money, snapshot
from tiewtrade.core.market_data import Timeframe
from tiewtrade.core.money import Quantity, basket_take_profit
from tiewtrade.core.orders import OrderStatus, QuoteBudget, TradingMode
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.protections import ProtectionPrices
from tiewtrade.core.strategies import (
    ExecutionFeedback,
    StrategyContractError,
    StrategyDocument,
    evaluate_strategy,
)
from tiewtrade.strategies.rsi_step_grid.strategy import (
    RsiStepGridConfig,
    RsiStepGridStrategy,
    initial_state,
)


def strategy(count: int = 10) -> RsiStepGridStrategy:
    return RsiStepGridStrategy(
        RsiStepGridConfig(PositionPair("BTC", "USDT"), Timeframe.M5, money("100"), count)
    )


def armed() -> StrategyDocument:
    s = strategy()
    source = snapshot(rsi="29")
    assert source.candle_input is not None
    source = replace(
        source,
        candle_input=replace(
            source.candle_input, candle=replace(source.candle_input.candle, close=money("100"))
        ),
    )
    return s.evaluate(source, s.config.document(), initial_state()).state


def test_arm_then_all_filters_fire_with_exact_budget_and_bracket() -> None:
    s = strategy()
    source = snapshot(offset=1)
    assert source.candle_input is not None
    first = evaluate_strategy(s, source, s.config.document(), armed(), scope=source.scope)
    assert first == evaluate_strategy(s, source, s.config.document(), armed(), scope=source.scope)
    assert isinstance(first.intents[0].size, QuoteBudget)
    assert isinstance(first.brackets[0][1], ProtectionPrices)
    assert first.intents[0].size.amount == money("100")
    assert first.brackets[0][1].take_profit == money("111")
    assert not s.evaluate(source, s.config.document(), first.state).intents


def test_pure_domain_uses_identical_rules_for_paper_and_live_inputs() -> None:
    s = strategy()
    paper = snapshot(offset=1)
    live = replace(paper, scope=replace(paper.scope, mode=TradingMode.LIVE))
    paper_decision = s.evaluate(paper, s.config.document(), armed())
    live_decision = s.evaluate(live, s.config.document(), armed())
    assert live_decision.state == paper_decision.state
    assert live_decision.brackets == paper_decision.brackets
    assert replace(live_decision.intents[0], scope=paper.scope) == paper_decision.intents[0]


@pytest.mark.parametrize("count", [1, 2, 3, 9, 10])
def test_all_integer_counts_are_supported(count: int) -> None:
    assert strategy(count).config.max_entries == count


@pytest.mark.parametrize("count", [0, 11, True, 1.5])
def test_invalid_counts_fail_closed(count: Any) -> None:
    with pytest.raises(StrategyContractError):
        strategy(count)


@pytest.mark.parametrize("rsi", ["30", "50", "60"])
def test_entry_threshold_is_strict(rsi: str) -> None:
    s = strategy()
    assert not s.evaluate(snapshot(rsi=rsi, offset=1), s.config.document(), armed()).intents


@pytest.mark.parametrize("flag", ["exit_on_candle", "backfilled", "basket_triggered"])
def test_authority_guards_block_new_buy(flag: str) -> None:
    s = strategy()
    source = snapshot(offset=1)
    assert source.candle_input is not None
    candle_input = source.candle_input
    if flag == "exit_on_candle":
        candle_input = replace(candle_input, exit_on_candle=True)
    elif flag == "backfilled":
        candle_input = replace(candle_input, backfilled=True)
    else:
        candle_input = replace(candle_input, basket_triggered=True)
    source = replace(source, candle_input=candle_input)
    assert not s.evaluate(source, s.config.document(), armed()).intents


def test_unproven_historical_arm_cannot_fire() -> None:
    s = strategy()
    source = snapshot(offset=1)
    assert source.candle_input is not None
    source = replace(source, candle_input=replace(source.candle_input, arm_validated=False))
    assert not s.evaluate(source, s.config.document(), armed()).intents


def test_missing_reset_warmup_or_slot_cannot_buy() -> None:
    s = strategy(1)
    source = snapshot(offset=1)
    assert source.candle_input is not None
    assert not s.evaluate(source, s.config.document(), initial_state()).intents
    for candle_input in (
        replace(source.candle_input, contiguous_count=249),
        replace(source.candle_input, open_entries=1),
    ):
        assert not s.evaluate(
            replace(source, candle_input=candle_input),
            s.config.document(),
            armed(),
        ).intents


def test_rejected_unfilled_entry_retains_reset_but_never_reuses_signal_candle() -> None:
    s = strategy()
    source = snapshot(offset=2)
    assert source.candle_input is not None
    fired = s.evaluate(source, s.config.document(), armed())
    rejected = s.evaluate(
        replace(
            source, feedback=ExecutionFeedback(fired.intents[0].order_id, 1, OrderStatus.REJECTED)
        ),
        s.config.document(),
        fired.state,
    )
    assert dict(rejected.state.fields)["reset_close"] == money("100")
    for replay in (source, snapshot(offset=1)):
        assert s.evaluate(replay, s.config.document(), armed()).intents
        decision = s.evaluate(replay, s.config.document(), rejected.state)
        assert not decision.intents and decision.state == rejected.state


def test_single_basket_oracles_and_held_target() -> None:
    def qty(value: str) -> Quantity:
        return Quantity.of(value, "BTC")

    assert basket_take_profit(
        ((money("100"), qty("1")), (money("80"), qty("1.25"))), money("2"), money("0.01")
    ) == money("94.88")
    assert basket_take_profit(
        ((money("100"), qty("1")), (money("110"), qty("1"))),
        money("10"),
        money("0.01"),
        held=money("130"),
    ) == money("130")
    assert basket_take_profit(
        ((money("100"), qty("1")), (money("90"), qty("1"))),
        money("10"),
        money("0.01"),
        held=money("106"),
    ) == money("106")


@pytest.mark.parametrize(
    "field,value", [("open", "105"), ("close", "102"), ("close", "101"), ("close", "100")]
)
def test_green_close_and_price_filters_are_all_strict(field: str, value: str) -> None:
    s = strategy()
    source = snapshot(offset=1)
    assert source.candle_input is not None
    candle = source.candle_input.candle
    changed = (
        replace(candle, open=money(value))
        if field == "open"
        else replace(candle, close=money(value))
    )
    source = replace(source, candle_input=replace(source.candle_input, candle=changed))
    assert not s.evaluate(source, s.config.document(), armed()).intents


@pytest.mark.parametrize("name,value", [("ema20", "101"), ("ema20", "100"), ("ema50", "102")])
def test_ema_order_filter_is_strict(name: str, value: str) -> None:
    s = strategy()
    source = snapshot(offset=1)
    assert source.candle_input is not None
    source = replace(
        source,
        indicators=tuple(
            (key, replace(indicator, value=money(value))) if key == name else (key, indicator)
            for key, indicator in source.indicators
        ),
    )
    assert not s.evaluate(source, s.config.document(), armed()).intents


def test_latest_reset_replaces_old_and_exit_guard_does_not_add_cooldown() -> None:
    s = strategy()
    source = snapshot(rsi="20", offset=1)
    assert source.candle_input is not None
    updated = s.evaluate(source, s.config.document(), armed()).state
    assert dict(updated.fields)["reset_close"] == money("105")
    guarded = snapshot(offset=1)
    assert guarded.candle_input is not None
    guarded = replace(guarded, candle_input=replace(guarded.candle_input, exit_on_candle=True))
    blocked = s.evaluate(guarded, s.config.document(), armed())
    assert not blocked.intents
    assert s.evaluate(snapshot(offset=2), s.config.document(), blocked.state).intents


@pytest.mark.parametrize(
    "key,value",
    [
        ("reset_close", money("-1")),
        ("pending_id", "not-a-uuid"),
        ("last_candle", "not-a-date"),
        ("last_candle", "2026-11-20T00:01:00+00:00"),
        ("last_candle", "2026-11-20T00:00:00"),
        ("pending_filled", True),
    ],
)
def test_corrupted_checkpoints_cannot_create_orders(key: str, value: Any) -> None:
    s = strategy()
    state = initial_state()
    state = replace(
        state, fields=tuple((name, value if name == key else old) for name, old in state.fields)
    )
    with pytest.raises(StrategyContractError):
        s.evaluate(snapshot(offset=1), s.config.document(), state)
