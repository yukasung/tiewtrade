from dataclasses import dataclass
from decimal import Decimal

from tiewtrade_core._decimal import ONE, calc
from tiewtrade_core.execution.book import TopOfBook
from tiewtrade_core.market import LiquidityRole, OrderSide, Rounding, round_to_increment


def _require_slippage_rate(slippage_rate: Decimal) -> None:
    """Reject a Paper slippage rate outside ``0 <= s < 1`` (Decided C-15).

    A negative rate would fill better than the touch, contradicting D-05. A rate of 1 or
    more drives a sell price to zero or below. ``s == 0`` is allowed: FR-ORD-07 fixes only
    the default (0.02%) and leaves the value to the Platform Admin.
    """
    if not 0 <= slippage_rate < 1:
        raise ValueError("slippage rate must satisfy 0 <= s < 1")


@dataclass(frozen=True, slots=True)
class PaperFill:
    """A simulated fill: the price and which fee rate applies (calculation spec §2.8).

    The type owns the positivity rule of C-18, so only a final price can become a fill.
    Intermediate §4.1 values stay plain ``Decimal`` and may legitimately round down to
    zero before §4.2 caps them to the limit; every new producer of a fill (§4.4, §4.5)
    then gets the check without having to remember it.
    """

    price: Decimal
    liquidity: LiquidityRole

    def __post_init__(self) -> None:
        if self.price <= 0:
            raise ValueError("fill price must be positive")


@calc
def _market_fill_price(
    side: OrderSide, book: TopOfBook, *, slippage_rate: Decimal, tick_size: Decimal
) -> Decimal:
    """Raw §4.1 price, before §4.2 may cap it — see ``PaperFill`` for why it is unchecked.

    Rounding goes against the user on purpose so Paper never looks better than reality
    (Decided C-11): a buy rounds up, a sell rounds down.
    """
    if side is OrderSide.BUY:
        return round_to_increment(book.best_ask * (ONE + slippage_rate), tick_size, Rounding.UP)
    return round_to_increment(book.best_bid * (ONE - slippage_rate), tick_size, Rounding.DOWN)


@calc
def market_fill(
    side: OrderSide, book: TopOfBook, *, slippage_rate: Decimal, tick_size: Decimal
) -> PaperFill:
    """Fill price of a Paper Market Order (calculation spec §4.1). Always Taker.

    ``slippage_rate`` and ``tick_size`` come from the caller: the rate is a Platform
    Admin setting (FR-ORD-07) and the core never reads configuration.
    """
    _require_slippage_rate(slippage_rate)
    price = _market_fill_price(side, book, slippage_rate=slippage_rate, tick_size=tick_size)
    return PaperFill(price=price, liquidity=LiquidityRole.TAKER)


def is_marketable(side: OrderSide, limit_price: Decimal, book: TopOfBook) -> bool:
    """Whether a Limit Order fills immediately at submission (calculation spec §4.2).

    Compared against the raw book, not against the slippage-adjusted §4.1 price, exactly
    as the spec states. A buy limit resting exactly on the ask is therefore marketable.
    """
    if side is OrderSide.BUY:
        return limit_price >= book.best_ask
    return limit_price <= book.best_bid


def _cap_to_limit(side: OrderSide, price: Decimal, limit_price: Decimal) -> Decimal:
    """Never fill worse than the limit (FR-ORD-08)."""
    return min(price, limit_price) if side is OrderSide.BUY else max(price, limit_price)


@calc
def limit_fill_on_submit(
    side: OrderSide,
    limit_price: Decimal,
    book: TopOfBook,
    *,
    slippage_rate: Decimal,
    tick_size: Decimal,
) -> PaperFill | None:
    """Immediate fill of a marketable Limit Order, or None when the order rests (§4.2).

    Round first, then cap (Decided C-18). The cap is what makes FR-ORD-08 hold when tick
    rounding pushes the §4.1 price past the limit; re-rounding afterwards would move the
    price against the user again and undo it.

    ``limit_price`` is assumed to already sit on the tick grid — upstream order validation
    rejects anything else through ``SymbolFilters.violations`` (``FilterViolation.TICK``).
    Given that, the min/max of two tick multiples is itself a tick multiple.
    """
    _require_slippage_rate(slippage_rate)
    if not is_marketable(side, limit_price, book):
        return None
    raw = _market_fill_price(side, book, slippage_rate=slippage_rate, tick_size=tick_size)
    return PaperFill(price=_cap_to_limit(side, raw, limit_price), liquidity=LiquidityRole.TAKER)


def resting_limit_fills(side: OrderSide, limit_price: Decimal, last_price: Decimal) -> bool:
    """Whether a resting Limit Order fills at ``last_price`` (calculation spec §4.2).

    The price must go **through** the limit; touching it does not fill (FR-ORD-08). Note
    the deliberate contrast with ``triggers.py``, where TP and SL fire on a touch.
    """
    if side is OrderSide.BUY:
        return last_price < limit_price
    return last_price > limit_price


def resting_limit_fill(
    side: OrderSide, limit_price: Decimal, last_price: Decimal
) -> PaperFill | None:
    """Fill of a resting Limit Order at its own price, as Maker, or None (§4.2).

    Delegates the comparison so the strictness cannot drift from ``resting_limit_fills``.
    Maker fills take no slippage: the price is the limit itself.
    """
    if not resting_limit_fills(side, limit_price, last_price):
        return None
    return PaperFill(price=limit_price, liquidity=LiquidityRole.MAKER)
