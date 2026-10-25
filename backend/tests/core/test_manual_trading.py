from dataclasses import replace
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tiewtrade.core.manual_trading import (
    ManualAccountPolicy,
    ManualUseRequiredError,
    available_base,
    available_quote,
)
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import (
    BaseSize,
    OrderIntent,
    OrderOrigin,
    OrderScope,
    OrderType,
    QuoteBudget,
    SafetyUnavailableError,
    TradingMode,
)
from tiewtrade.core.positions import ExecutionSide, PositionPair
from tiewtrade.core.trading_account import AccountUse


class RecordingPolicy:
    def __init__(self) -> None:
        self.calls = 0

    def check(self, intent: OrderIntent) -> None:
        self.calls += 1


def test_exact_available_funds_examples() -> None:
    assert available_quote(
        Money.of(150, "USDT"), (Money.of(100, "USDT"), Money.of(25, "USDT"))
    ) == (Money.of(125, "USDT"), Money.of(25, "USDT"))
    assert available_base(
        Quantity.of("1.2", "BTC"), (Quantity.of(".2", "BTC"), Quantity.of(".3", "BTC"))
    ) == (Quantity.of(".5", "BTC"), Quantity.of(".7", "BTC"))
    with pytest.raises(SafetyUnavailableError):
        available_quote(Money.of(99, "USDT"), (Money.of(100, "USDT"),))


@given(
    total=st.integers(min_value=1, max_value=10**10),
    seed=st.integers(min_value=0, max_value=10**10),
)
def test_reservations_conserve_available_funds(total: int, seed: int) -> None:
    reserved = seed % (total + 1)
    r, available = available_quote(Money.of(total, "USDT"), (Money.of(reserved, "USDT"),))
    assert r == Money.of(reserved, "USDT")
    assert available == Money.of(total - reserved, "USDT")
    qr, qa = available_base(Quantity.of(total, "BTC"), (Quantity.of(reserved, "BTC"),))
    assert qr == Quantity.of(reserved, "BTC") and qa == Quantity.of(total - reserved, "BTC")


@pytest.mark.parametrize("mode", [TradingMode.PAPER, TradingMode.LIVE])
def test_manual_bot_policy_parity_and_true_reduction(mode: TradingMode) -> None:
    value = OrderIntent(
        uuid4(),
        uuid4(),
        OrderScope(uuid4(), uuid4(), mode),
        PositionPair("BTC", "USDT"),
        OrderOrigin.MANUAL,
        ExecutionSide.SELL,
        OrderType.MARKET,
        BaseSize(Quantity.of(1, "BTC")),
    )
    delegate = RecordingPolicy()
    policy = ManualAccountPolicy(
        AccountUse.BOT, Quantity.of(2, "BTC"), Quantity.of(1, "BTC"), delegate
    )
    policy.check(value)
    assert delegate.calls == 1
    with pytest.raises(ManualUseRequiredError):
        policy.check(replace(value, size=BaseSize(Quantity.of("1.000000000000000001", "BTC"))))
    opening = replace(value, side=ExecutionSide.BUY, size=QuoteBudget(Money.of(100, "USDT")))
    with pytest.raises(ManualUseRequiredError):
        policy.check(opening)
    manual = replace(policy, use=AccountUse.MANUAL)
    manual.check(opening)
    with pytest.raises(SafetyUnavailableError):
        replace(manual, delegate=None).check(opening)
