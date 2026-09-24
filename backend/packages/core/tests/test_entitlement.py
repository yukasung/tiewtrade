from decimal import Decimal as D

import pytest

from tiewtrade_core.entitlement import (
    Entitlement,
    FuturesSymbolExposure,
    SpotSymbolExposure,
    effective_max_leverage,
    open_notional,
    projected_notional,
    within_leverage,
    within_limit,
)
from tiewtrade_core.margin import PendingOrder
from tiewtrade_core.market import LeverageBrackets, OrderSide, TradingMode

BUY, SELL = OrderSide.BUY, OrderSide.SELL
PAPER, LIVE = TradingMode.PAPER, TradingMode.LIVE

# The MVP defaults of FR-PLN-03 (D-11). Admin can change every one of them.
FREE = Entitlement(
    max_leverage=5,
    paper_notional_limit=D(10_000),
    live_enabled=False,
    live_notional_limit=D(0),
    max_paper_portfolios=2,
    max_live_portfolios=0,
)
PRO = Entitlement(
    max_leverage=20,
    paper_notional_limit=D(50_000),
    live_enabled=True,
    live_notional_limit=D(50_000),
    max_paper_portfolios=5,
    max_live_portfolios=3,
)


def order(side: OrderSide, quantity: str, price: str) -> PendingOrder:
    return PendingOrder(
        side=side,
        quantity=D(quantity),
        assuming_price=D(price),
        order_price=D(price),
    )


# --- the Plan's values (FR-PLN-03) ---------------------------------------


def test_each_trading_mode_has_its_own_limit() -> None:
    """FR-PLN-04: Paper and Live never share a budget."""
    assert PRO.notional_limit(PAPER) == D(50_000)
    assert FREE.notional_limit(LIVE) == D(0)


def test_free_cannot_trade_live_at_all() -> None:
    assert FREE.allows(PAPER) is True
    assert FREE.allows(LIVE) is False
    assert PRO.allows(LIVE) is True


def test_a_portfolio_may_be_created_until_the_plan_runs_out() -> None:
    assert FREE.allows_another_portfolio(PAPER, existing=1) is True
    assert FREE.allows_another_portfolio(PAPER, existing=2) is False
    assert FREE.allows_another_portfolio(LIVE, existing=0) is False  # limit is zero


def test_being_over_the_portfolio_limit_is_not_an_error() -> None:
    """FR-PLN-11: a downgrade leaves the extra Portfolios in place; it only stops more."""
    assert FREE.allows_another_portfolio(PAPER, existing=7) is False


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"max_leverage": 0}, "max leverage"),
        ({"max_leverage": 126}, "max leverage"),
        ({"paper_notional_limit": D(-1)}, "notional limit"),
        ({"max_live_portfolios": -1}, "portfolio limit"),
    ],
)
def test_an_impossible_entitlement_is_refused(changes: dict[str, object], message: str) -> None:
    fields: dict[str, object] = {
        "max_leverage": 5,
        "paper_notional_limit": D(10_000),
        "live_enabled": False,
        "live_notional_limit": D(0),
        "max_paper_portfolios": 2,
        "max_live_portfolios": 0,
    }
    fields.update(changes)

    with pytest.raises(ValueError, match=message):
        Entitlement(**fields)  # type: ignore[arg-type]


# --- Open Notional (§5.1) ------------------------------------------------


def test_open_notional_values_futures_at_the_mark_price() -> None:
    """0.5 BTC at a mark of 60,000 = 30,000."""
    assert open_notional(futures=[FuturesSymbolExposure(D("0.5"), D(60_000))]) == D(30_000)


def test_a_short_counts_the_same_as_a_long() -> None:
    """Exposure is size, not direction, so the sign drops out."""
    short = FuturesSymbolExposure(D("-0.5"), D(60_000))

    assert open_notional(futures=[short]) == D(30_000)


def test_open_notional_values_spot_at_the_last_price() -> None:
    assert open_notional(spot=[SpotSymbolExposure(D(2), D(3_000))]) == D(6_000)


def test_open_notional_adds_every_portfolio_of_the_workspace() -> None:
    """FR-PLN-04: the limit is per Workspace, not per Portfolio."""
    total = open_notional(
        futures=[
            FuturesSymbolExposure(D("0.5"), D(60_000)),  # 30,000
            FuturesSymbolExposure(D(-10), D(3_000)),  # 30,000
        ],
        spot=[SpotSymbolExposure(D(2), D(3_000))],  # 6,000
    )

    assert total == D(66_000)


def test_an_empty_workspace_has_no_open_notional() -> None:
    assert open_notional() == D(0)


def test_open_notional_ignores_resting_orders() -> None:
    """§5.1 measures positions; reserving for orders is §5.2's job."""
    with_orders = FuturesSymbolExposure(D("0.5"), D(60_000), orders=(order(BUY, "1", "60000"),))

    assert open_notional(futures=[with_orders]) == D(30_000)


# --- Projected Notional (§5.2, C-08) -------------------------------------


def test_a_resting_buy_reserves_headroom() -> None:
    """Long 0.5 at 60,000 plus a resting buy of 1 at 60,000: 30,000 + 60,000."""
    exposure = FuturesSymbolExposure(D("0.5"), D(60_000), orders=(order(BUY, "1", "60000"),))

    assert projected_notional(futures=[exposure]) == D(90_000)


def test_the_worse_side_wins_when_orders_sit_on_both() -> None:
    """C-08: bids and asks do not net off, because only one side can fill against it.

    Long 0.5 at 60,000 = 30,000. Bid 0.2 = 12,000, ask 1.0 = 60,000.
    max(|30,000 + 12,000|, |30,000 - 60,000|) = 42,000.
    """
    exposure = FuturesSymbolExposure(
        D("0.5"),
        D(60_000),
        orders=(order(BUY, "0.2", "60000"), order(SELL, "1", "60000")),
    )

    assert projected_notional(futures=[exposure]) == D(42_000)


def test_a_resting_spot_buy_reserves_its_limit_value() -> None:
    holding = SpotSymbolExposure(D(2), D(3_000), resting_buy_value=D(3_000))

    assert projected_notional(spot=[holding]) == D(9_000)


def test_many_small_limits_are_reserved_together() -> None:
    """The point of C-08: each order is within the limit, the pile of them is not."""
    exposures = [
        FuturesSymbolExposure(D(0), D(60_000), orders=(order(BUY, "0.1", "60000"),))
        for _ in range(5)
    ]

    assert projected_notional(futures=exposures) == D(30_000)


# --- the limit check (FR-PLN-05) -----------------------------------------


def test_an_order_that_stays_under_the_limit_passes() -> None:
    assert within_limit(D(50_000), projected_before=D(30_000), projected_after=D(40_000))


def test_an_order_that_crosses_the_limit_is_refused() -> None:
    assert not within_limit(D(50_000), projected_before=D(40_000), projected_after=D(60_000))


def test_an_order_that_reduces_a_position_passes_even_from_over_the_limit() -> None:
    """FR-PLN-05: otherwise a Workspace that went over could never get back under."""
    assert within_limit(
        D(50_000), projected_before=D(70_000), projected_after=D(60_000), reduces=True
    )


def test_a_take_profit_passes_although_it_raises_the_projected_notional() -> None:
    """Regression: a protective leg must never be refused by the notional limit.

    Long 0.1 BTC at a mark of 60,000 is 6,000 of exposure. Its Bracket take profit is a
    reduce-only sell of 0.1 resting at 200,000, and §2.2 values the ask side at the
    order's own price, so the projected number rises to 14,000 even though filling the
    order can only close the position. Reading "reduces" off the falling number would
    reject exactly the order that protects the user (FR-ORD-14).
    """
    long = FuturesSymbolExposure(D("0.1"), D(60_000))
    take_profit = order(SELL, "0.1", "200000")
    protected = FuturesSymbolExposure(D("0.1"), D(60_000), orders=(take_profit,))

    before = projected_notional(futures=[long])
    after = projected_notional(futures=[protected])

    assert after > before  # the premise: the number goes up
    assert not within_limit(D(10_000), before, after)  # what the number alone would say
    assert within_limit(D(10_000), before, after, reduces=True)


def test_drifting_over_the_limit_on_price_alone_is_not_a_breach() -> None:
    """FR-PLN-05: nothing is force-closed; only opening is refused.

    The Workspace is already at 70,000 against a 50,000 limit because the price rose. An
    order that leaves it exactly where it is passes; one that adds to it does not.
    """
    assert within_limit(D(50_000), projected_before=D(70_000), projected_after=D(70_000))
    assert not within_limit(D(50_000), projected_before=D(70_000), projected_after=D(70_001))


def test_sitting_exactly_on_the_limit_is_allowed() -> None:
    """The requirement refuses what goes *over*, so the boundary itself is fine."""
    assert within_limit(D(50_000), projected_before=D(40_000), projected_after=D(50_000))


def test_a_negative_limit_is_impossible() -> None:
    with pytest.raises(ValueError, match="limit"):
        within_limit(D(-1), projected_before=D(0), projected_after=D(0))


# --- Effective Max Leverage (§5.3, FR-PLN-06) ----------------------------


def test_the_plan_caps_a_generous_bracket(brackets: LeverageBrackets) -> None:
    """At a small notional Binance allows 125x, but a Free plan allows 5x."""
    assert effective_max_leverage(FREE.max_leverage, brackets, D(10_000)) == 5


def test_the_bracket_caps_a_generous_plan(brackets: LeverageBrackets) -> None:
    """At 2,000,000 the bracket allows only 20x; a 50x plan cannot lift that."""
    assert effective_max_leverage(50, brackets, D(2_000_000)) == 20


def test_the_notional_that_matters_is_the_one_the_order_would_produce(
    brackets: LeverageBrackets,
) -> None:
    """A bigger position falls into a higher bracket, where Binance itself allows less."""
    assert effective_max_leverage(125, brackets, D(10_000)) == 125
    assert effective_max_leverage(125, brackets, D(20_000_000)) == 10


def test_a_leverage_within_both_caps_is_allowed(brackets: LeverageBrackets) -> None:
    assert within_leverage(5, PRO.max_leverage, brackets, D(10_000))
    assert not within_leverage(21, PRO.max_leverage, brackets, D(10_000))


def test_leverage_must_be_at_least_one(brackets: LeverageBrackets) -> None:
    with pytest.raises(ValueError, match="leverage must be at least 1"):
        within_leverage(0, PRO.max_leverage, brackets, D(10_000))
