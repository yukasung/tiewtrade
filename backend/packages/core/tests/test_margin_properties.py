from collections.abc import Callable
from decimal import Decimal as D

from hypothesis import assume, given
from hypothesis import strategies as st

from tiewtrade_core.margin import MarginState, liquidation_price
from tiewtrade_core.market import LeverageBrackets

MarginGap = Callable[..., D]

quantities = st.decimals(min_value="0.001", max_value="200", places=3)
prices = st.decimals(min_value="1", max_value="200000", places=2)
leverages = st.integers(min_value=2, max_value=125)


wallet_fractions = st.decimals(min_value="0.001", max_value="1.5", places=3)


def assert_solution_or_no_root(
    margin_gap: MarginGap,
    price: D | None,
    quantity: D,
    entry: D,
    wallet: D,
    other_mm: D,
    other_upnl: D,
) -> None:
    """A price must solve Margin Balance = MM; None only when no positive root exists."""
    if price is None:
        # The gap is monotonic in price (rising for a Long, falling for a Short) and
        # continuous, so there is no positive root exactly when its value at price zero
        # already has the sign it keeps forever:
        #   Long:  gap(0) >= 0 -> never liquidated by price
        #   Short: gap(0) <= 0 -> liquidatable at every price
        at_zero = margin_gap(D(0), quantity, entry, wallet, other_mm, other_upnl)
        assert at_zero >= 0 if quantity > 0 else at_zero <= 0
        return
    assert price > 0
    scale = max(D(1), abs(quantity) * entry, abs(wallet))
    residual = margin_gap(price, quantity, entry, wallet, other_mm, other_upnl)
    assert abs(residual) <= scale * D("1e-40")


@given(quantities, prices, wallet_fractions, st.booleans())
def test_isolated_liquidation_price_is_the_solution_or_none_only_without_root(
    brackets: LeverageBrackets,
    margin_gap: MarginGap,
    size: D,
    entry: D,
    fraction: D,
    is_long: bool,
) -> None:
    # Wallet from 0.1% to 150% of notional reaches solutions in every bracket, including
    # lower brackets than the one at entry.
    quantity = size if is_long else -size
    wallet = size * entry * fraction
    price = liquidation_price(quantity, entry, wallet, brackets)
    assert_solution_or_no_root(margin_gap, price, quantity, entry, wallet, D(0), D(0))


@given(quantities, prices, leverages)
def test_isolated_long_liquidates_below_entry_and_short_above(
    brackets: LeverageBrackets, size: D, entry: D, leverage: int
) -> None:
    # Leverage is capped by the bracket (calculation spec §5.3); above the cap the initial
    # margin can be below maintenance, so the position would be liquidatable at entry.
    assume(leverage <= brackets.for_notional(size * entry).max_leverage)
    wallet = size * entry / leverage
    long_price = liquidation_price(size, entry, wallet, brackets)
    short_price = liquidation_price(-size, entry, wallet, brackets)
    if long_price is not None:
        assert long_price < entry
    assert short_price is not None
    assert short_price > entry


@given(
    quantities,
    prices,
    wallet_fractions,
    st.booleans(),
    st.decimals(min_value="0", max_value="5000", places=2),
    st.decimals(min_value="-5000", max_value="5000", places=2),
)
def test_cross_liquidation_price_is_the_solution_or_none_only_without_root(
    brackets: LeverageBrackets,
    margin_gap: MarginGap,
    size: D,
    entry: D,
    fraction: D,
    is_long: bool,
    other_mm: D,
    other_upnl: D,
) -> None:
    quantity = size if is_long else -size
    wallet = size * entry * fraction
    price = liquidation_price(
        quantity,
        entry,
        wallet,
        brackets,
        other_maintenance_margin=other_mm,
        other_unrealized_pnl=other_upnl,
    )
    assert_solution_or_no_root(margin_gap, price, quantity, entry, wallet, other_mm, other_upnl)


@given(
    st.decimals(min_value="-1000", max_value="0", places=2),
    st.decimals(min_value="0.01", max_value="1000", places=2),
)
def test_non_positive_balance_with_open_position_is_always_liquidatable(
    balance: D, maintenance: D
) -> None:
    assert MarginState(balance, maintenance).is_liquidatable
