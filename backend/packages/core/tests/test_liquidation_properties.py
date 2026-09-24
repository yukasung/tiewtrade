from decimal import Decimal as D

from hypothesis import assume, given
from hypothesis import strategies as st

from tiewtrade_core.execution import LiquidatablePosition, cross_liquidation, isolated_liquidation
from tiewtrade_core.margin import FuturesExposure
from tiewtrade_core.market import LeverageBrackets

quantities = st.decimals(min_value="0.001", max_value="50", places=3).filter(lambda q: q != 0)
prices = st.decimals(min_value="100", max_value="90000", places=2)
wallets = st.decimals(min_value="0", max_value="5000", places=2)
rates = st.decimals(min_value="0", max_value="0.05", places=4)
signs = st.sampled_from([D(1), D(-1)])
symbols = st.sampled_from(["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"])


def build(
    brackets: LeverageBrackets, symbol: str, quantity: D, entry: D, mark: D, rate: D
) -> LiquidatablePosition:
    return LiquidatablePosition(
        symbol=symbol,
        episode_id=f"ep-{symbol}",
        exposure=FuturesExposure(
            quantity=quantity,
            entry_price=entry,
            mark_price=mark,
            leverage=10,
            brackets=brackets,
        ),
        clearance_rate=rate,
    )


@given(
    quantity=quantities,
    sign=signs,
    entry=prices,
    mark=prices,
    wallet=wallets,
    rate=rates,
)
def test_a_cross_wallet_never_ends_negative(
    brackets: LeverageBrackets,
    quantity: D,
    sign: D,
    entry: D,
    mark: D,
    wallet: D,
    rate: D,
) -> None:
    """§4.4: the shortfall is the Insurance Fund's, never a debt charged to the user."""
    result = cross_liquidation(
        wallet, [build(brackets, "BTCUSDT", sign * quantity, entry, mark, rate)]
    )
    assume(result is not None)
    assert result is not None

    assert result.wallet_balance >= 0
    assert result.insurance_absorbed >= 0


@given(
    quantity=quantities,
    sign=signs,
    entry=prices,
    mark=prices,
    wallet=wallets,
    rate=rates,
)
def test_the_money_a_cross_liquidation_moves_adds_up(
    brackets: LeverageBrackets,
    quantity: D,
    sign: D,
    entry: D,
    mark: D,
    wallet: D,
    rate: D,
) -> None:
    """Nothing is created or lost: what the wallet keeps plus what was absorbed is exactly
    the balance after the positions closed and the fees came off."""
    position = build(brackets, "BTCUSDT", sign * quantity, entry, mark, rate)
    result = cross_liquidation(wallet, [position])
    assume(result is not None)
    assert result is not None

    expected = wallet + result.realized_pnl - result.clearance_fee

    assert result.wallet_balance - result.insurance_absorbed == expected


@given(
    quantity=quantities,
    sign=signs,
    entry=prices,
    mark=prices,
    wallet=wallets,
    rate=rates,
)
def test_an_isolated_wallet_always_ends_empty(
    brackets: LeverageBrackets,
    quantity: D,
    sign: D,
    entry: D,
    mark: D,
    wallet: D,
    rate: D,
) -> None:
    """Verify: the remainder is forfeited, so the wallet is zero whatever happened, and
    only one of forfeited / absorbed can be non-zero."""
    position = build(brackets, "BTCUSDT", sign * quantity, entry, mark, rate)
    result = isolated_liquidation(wallet, position)
    assume(result is not None)
    assert result is not None

    assert result.wallet_balance == 0
    assert not (result.forfeited > 0 and result.insurance_absorbed > 0)
    assert result.forfeited - result.insurance_absorbed == (
        wallet + result.realized_pnl - result.clearance_fee
    )


@given(
    data=st.data(),
    names=st.lists(symbols, min_size=2, max_size=4, unique=True),
    wallet=wallets,
    rate=rates,
)
def test_a_cross_liquidation_does_not_depend_on_the_order_of_its_positions(
    brackets: LeverageBrackets,
    data: st.DataObject,
    names: list[str],
    wallet: D,
    rate: D,
) -> None:
    """C-09, the reason cross closes everything from one snapshot.

    An order-dependent result could not be reproduced by replay (§4.5), where the engine
    rebuilds the same liquidation from a candle rather than from live events.
    """
    positions = [
        build(
            brackets,
            name,
            data.draw(signs) * data.draw(quantities),
            data.draw(prices),
            data.draw(prices),
            rate,
        )
        for name in names
    ]
    result = cross_liquidation(wallet, positions)
    assume(result is not None)
    assert result is not None

    reversed_result = cross_liquidation(wallet, list(reversed(positions)))

    assert reversed_result is not None
    assert reversed_result.realized_pnl == result.realized_pnl
    assert reversed_result.clearance_fee == result.clearance_fee
    assert reversed_result.wallet_balance == result.wallet_balance
    assert reversed_result.insurance_absorbed == result.insurance_absorbed
    assert {c.symbol for c in reversed_result.positions} == {c.symbol for c in result.positions}
