from decimal import Decimal as D

import pytest

from tiewtrade_core.execution import (
    CancelScope,
    LiquidatablePosition,
    cross_liquidation,
    isolated_liquidation,
)
from tiewtrade_core.margin import FuturesExposure
from tiewtrade_core.market import LeverageBrackets

RATE = D("0.015")  # illustrative clearance rate; the real one is Verify config


def position(
    brackets: LeverageBrackets,
    *,
    symbol: str = "BTCUSDT",
    quantity: str = "1",
    entry: str = "60000",
    mark: str = "60000",
    leverage: int = 10,
    clearance_rate: D = RATE,
) -> LiquidatablePosition:
    return LiquidatablePosition(
        symbol=symbol,
        episode_id=f"ep-{symbol}",
        exposure=FuturesExposure(
            quantity=D(quantity),
            entry_price=D(entry),
            mark_price=D(mark),
            leverage=leverage,
            brackets=brackets,
        ),
        clearance_rate=clearance_rate,
    )


# --- construction --------------------------------------------------------


def test_a_flat_position_cannot_be_liquidated(brackets: LeverageBrackets) -> None:
    with pytest.raises(ValueError, match="flat position"):
        position(brackets, quantity="0")


def test_a_clearance_rate_cannot_be_negative(brackets: LeverageBrackets) -> None:
    with pytest.raises(ValueError, match="clearance rate"):
        position(brackets, clearance_rate=D("-0.01"))


@pytest.mark.parametrize(("field", "message"), [("symbol", "symbol"), ("episode_id", "episode_id")])
def test_a_liquidation_records_which_position_it_closed(
    brackets: LeverageBrackets, field: str, message: str
) -> None:
    """The ledger entry needs both (data model §6.6), so neither may be blank."""
    fields = {
        "symbol": "BTCUSDT",
        "episode_id": "ep-1",
        "exposure": position(brackets).exposure,
        "clearance_rate": RATE,
    }
    fields[field] = ""

    with pytest.raises(ValueError, match=message):
        LiquidatablePosition(**fields)  # type: ignore[arg-type]


# --- the condition is §2.4, not the liquidation price --------------------


def test_a_healthy_portfolio_is_not_liquidated(brackets: LeverageBrackets) -> None:
    """Margin Balance is far above maintenance, so nothing happens."""
    assert cross_liquidation(D("10000"), [position(brackets)]) is None


def test_a_portfolio_with_no_position_is_not_liquidated(brackets: LeverageBrackets) -> None:
    assert cross_liquidation(D("10000"), []) is None


def test_a_fee_can_liquidate_without_the_price_moving(brackets: LeverageBrackets) -> None:
    """§4.4: the check runs after every margin event, because funding or a fee alone can
    exhaust the wallet while the mark price stands still."""
    flat_price = position(brackets, entry="60000", mark="60000")
    maintenance = flat_price.exposure.maintenance_margin

    assert cross_liquidation(maintenance * 2, [flat_price]) is None  # before the fee
    assert cross_liquidation(maintenance, [flat_price]) is not None  # the fee took it to MM


# --- isolated (§4.4) -----------------------------------------------------


def test_an_isolated_liquidation_closes_at_the_mark_price(brackets: LeverageBrackets) -> None:
    """Long 1 BTC from 60,000, mark 55,000, isolated wallet 250.

    Unrealized PnL = 1 * (55,000 - 60,000) = -5,000, which the 250 wallet cannot cover,
    so the position is liquidated at the mark price of this event.
    """
    long = position(brackets, quantity="1", entry="60000", mark="55000")

    result = isolated_liquidation(D("250"), long)

    assert result is not None
    closed = result.positions[0]
    assert closed.close_price == D("55000")
    assert closed.realized_pnl == D("-5000")
    assert closed.clearance_fee == D("55000") * RATE  # notional * rate = 825
    assert closed.episode_id == "ep-BTCUSDT"


def test_an_isolated_wallet_ends_at_zero_and_the_shortfall_is_absorbed(
    brackets: LeverageBrackets,
) -> None:
    """The loss runs past the wallet, so the user is not charged the difference."""
    long = position(brackets, quantity="1", entry="60000", mark="55000")

    result = isolated_liquidation(D("250"), long)

    assert result is not None
    # 250 - 5000 - 825 = -5575
    assert result.insurance_absorbed == D("5575")
    assert result.wallet_balance == D(0)
    assert result.forfeited == D(0)


def test_whatever_survives_an_isolated_liquidation_is_forfeited(
    brackets: LeverageBrackets,
) -> None:
    """Verify: Binance keeps the remainder, so the wallet ends at zero either way."""
    long = position(brackets, quantity="1", entry="60000", mark="59000", clearance_rate=D("0"))

    result = isolated_liquidation(D("1010"), long)  # margin balance 10, maintenance 245

    assert result is not None
    # 1010 - 1000 - 0 = 10 left, and it is kept by the venue
    assert result.forfeited == D("10")
    assert result.wallet_balance == D(0)
    assert result.insurance_absorbed == D(0)


def test_an_isolated_liquidation_only_cancels_that_symbol(brackets: LeverageBrackets) -> None:
    """An isolated position is walled off; unrelated orders are not its business."""
    long = position(brackets, quantity="1", entry="60000", mark="55000")

    result = isolated_liquidation(D("250"), long)

    assert result is not None
    assert result.cancel_scope is CancelScope.SYMBOL


def test_a_healthy_isolated_position_is_left_alone(brackets: LeverageBrackets) -> None:
    assert isolated_liquidation(D("10000"), position(brackets)) is None


# --- cross (§4.4, C-09) --------------------------------------------------


def test_a_cross_liquidation_closes_every_position_at_once(brackets: LeverageBrackets) -> None:
    """C-09: cross does not close the worst position first; it closes them all together."""
    losing = position(brackets, symbol="BTCUSDT", quantity="1", entry="60000", mark="55000")
    winning = position(brackets, symbol="ETHUSDT", quantity="10", entry="3000", mark="3100")

    result = cross_liquidation(D("400"), [losing, winning])

    assert result is not None
    assert [c.symbol for c in result.positions] == ["BTCUSDT", "ETHUSDT"]
    assert result.realized_pnl == D("-5000") + D("1000")  # both, netted


def test_a_cross_liquidation_totals_every_clearance_fee(brackets: LeverageBrackets) -> None:
    losing = position(brackets, symbol="BTCUSDT", quantity="1", entry="60000", mark="55000")
    winning = position(brackets, symbol="ETHUSDT", quantity="10", entry="3000", mark="3100")

    result = cross_liquidation(D("400"), [losing, winning])

    assert result is not None
    # 55,000 * 0.015 + 31,000 * 0.015
    assert result.clearance_fee == D("825") + D("465")


def test_a_cross_wallet_never_goes_below_zero(brackets: LeverageBrackets) -> None:
    losing = position(brackets, quantity="1", entry="60000", mark="55000")

    result = cross_liquidation(D("400"), [losing])

    assert result is not None
    # 400 - 5000 - 825 = -5425, absorbed rather than charged on
    assert result.wallet_balance == D(0)
    assert result.insurance_absorbed == D("5425")


def test_a_cross_wallet_keeps_what_survives(brackets: LeverageBrackets) -> None:
    """Unlike isolated, a cross wallet is not forfeited."""
    losing = position(brackets, quantity="1", entry="60000", mark="59000", clearance_rate=D("0"))

    result = cross_liquidation(D("1010"), [losing])

    assert result is not None
    assert result.wallet_balance == D("10")
    assert result.forfeited == D(0)


def test_a_cross_liquidation_cancels_the_whole_portfolio(brackets: LeverageBrackets) -> None:
    """Step 1 of §4.4, matching Binance."""
    result = cross_liquidation(D("400"), [position(brackets, quantity="1", mark="55000")])

    assert result is not None
    assert result.cancel_scope is CancelScope.PORTFOLIO


def test_a_short_is_liquidated_by_a_rising_price(brackets: LeverageBrackets) -> None:
    short = position(brackets, quantity="-1", entry="60000", mark="65000")

    result = cross_liquidation(D("400"), [short])

    assert result is not None
    assert result.positions[0].realized_pnl == D("-5000")  # -1 * (65,000 - 60,000)
    assert result.positions[0].clearance_fee == D("65000") * RATE
