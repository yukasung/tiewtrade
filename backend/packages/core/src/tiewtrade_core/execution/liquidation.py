"""Paper Liquidation, the reduced model of calculation spec §4.4 (FR-MRG-05, C-09).

Checked after **every event that moves margin** — a Mark Price update, a fill, a fee,
funding, a transfer out, a leverage change — and not only after a price move, because
funding or a fee can exhaust the margin while the price stands still. The condition is
``MarginState.is_liquidatable`` from §2.4, never a comparison against the Liquidation
Price: that price is an estimate for display, and it says nothing about a liquidation the
price did not cause.

Each function returns the outcome, or None when the Portfolio is not liquidatable. The
caller writes the ledger entries, cancels the orders and emits the notification; the core
only works out what happens (ADR-0001).

Not simulated: the Insurance Fund, ADL and Binance's partial "smart" liquidation, which
would close only part of a position (FR-MRG-05). Paper therefore closes everything and
comes out worse than Binance would, which is the direction D-05 requires.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from tiewtrade_core._decimal import ZERO, calc
from tiewtrade_core.margin.account import cross_margin_state, isolated_margin_state
from tiewtrade_core.margin.exposure import FuturesExposure


class CancelScope(StrEnum):
    """Which resting orders a liquidation takes with it (calculation spec §4.4, step 1).

    Cross cancels everything in the Portfolio, matching Binance; an isolated liquidation
    reaches only the symbol it happened on.
    """

    SYMBOL = "SYMBOL"
    PORTFOLIO = "PORTFOLIO"


@dataclass(frozen=True, slots=True)
class LiquidatablePosition:
    """A position as the liquidation sees it: an exposure plus what the ledger needs.

    ``clearance_rate`` is per symbol and is **Verify** — it is config read from the
    caller, not a constant the core may invent.
    """

    symbol: str
    episode_id: str
    exposure: FuturesExposure
    clearance_rate: Decimal

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if not self.episode_id:
            raise ValueError("episode_id must not be empty")
        if self.clearance_rate < 0:
            raise ValueError("clearance rate must not be negative")
        if self.exposure.quantity == 0:
            raise ValueError("a flat position cannot be liquidated")


@dataclass(frozen=True, slots=True)
class ClosedPosition:
    """One position closed by a liquidation, priced at the Mark Price of the event."""

    symbol: str
    episode_id: str
    quantity: Decimal  # signed, as the position stood
    entry_price: Decimal
    close_price: Decimal
    realized_pnl: Decimal  # gross, before the clearance fee
    clearance_fee: Decimal


@dataclass(frozen=True, slots=True)
class Liquidation:
    """What a liquidation does to a Portfolio (calculation spec §4.4).

    ``realized_pnl`` and ``clearance_fee`` are the totals of ``positions``, kept here so a
    caller does not re-add them in its own Decimal context and get a different number.

    ``forfeited`` is whatever was left in an isolated wallet after the position closed:
    Binance keeps it, so the wallet ends at zero (**Verify**). ``insurance_absorbed`` is
    the shortfall the Insurance Fund covers when the loss runs past the balance; it is
    recorded but never charged to the user, which is why ``wallet_balance`` cannot go
    below zero.
    """

    positions: tuple[ClosedPosition, ...]
    realized_pnl: Decimal
    clearance_fee: Decimal
    wallet_balance: Decimal
    forfeited: Decimal
    insurance_absorbed: Decimal
    cancel_scope: CancelScope


@calc
def _close(position: LiquidatablePosition) -> ClosedPosition:
    """Close one position at its Mark Price and charge the clearance fee."""
    exposure = position.exposure
    return ClosedPosition(
        symbol=position.symbol,
        episode_id=position.episode_id,
        quantity=exposure.quantity,
        entry_price=exposure.entry_price,
        close_price=exposure.mark_price,
        realized_pnl=exposure.unrealized_pnl,
        clearance_fee=exposure.notional * position.clearance_rate,
    )


@calc
def cross_liquidation(
    cross_wallet_balance: Decimal, positions: Iterable[LiquidatablePosition]
) -> Liquidation | None:
    """Liquidate every cross position of a Portfolio at once, or None (§4.4, C-09).

    All of them close together, at each symbol's Mark Price from the **same event**, and
    every clearance fee is taken from that one snapshot. The result therefore does not
    depend on the order the positions are processed in, which is what makes a liquidation
    reproducible in replay (§4.5).

    The wallet cannot end below zero: a loss that runs past the balance is recorded as
    ``insurance_absorbed`` rather than charged on to the user.
    """
    candidates = tuple(positions)
    if not candidates:
        return None
    state = cross_margin_state(cross_wallet_balance, [p.exposure for p in candidates])
    if not state.is_liquidatable:
        return None

    closed = tuple(_close(p) for p in candidates)
    realized = sum((c.realized_pnl for c in closed), ZERO)
    fees = sum((c.clearance_fee for c in closed), ZERO)
    remaining = cross_wallet_balance + realized - fees
    return Liquidation(
        positions=closed,
        realized_pnl=realized,
        clearance_fee=fees,
        wallet_balance=max(ZERO, remaining),
        forfeited=ZERO,  # a cross wallet keeps whatever survives
        insurance_absorbed=max(ZERO, -remaining),
        cancel_scope=CancelScope.PORTFOLIO,
    )


@calc
def isolated_liquidation(
    isolated_wallet: Decimal, position: LiquidatablePosition
) -> Liquidation | None:
    """Liquidate one isolated position, backed only by its own wallet, or None (§4.4).

    Whatever is left in the isolated wallet once the position is closed is forfeited, so
    the wallet ends at zero either way (**Verify**). Only this symbol's resting orders are
    cancelled: an isolated position is walled off from the rest of the Portfolio, and
    taking unrelated orders with it would close positions the loss never touched.
    """
    state = isolated_margin_state(isolated_wallet, position.exposure)
    if not state.is_liquidatable:
        return None

    closed = _close(position)
    remaining = isolated_wallet + closed.realized_pnl - closed.clearance_fee
    return Liquidation(
        positions=(closed,),
        realized_pnl=closed.realized_pnl,
        clearance_fee=closed.clearance_fee,
        wallet_balance=ZERO,
        forfeited=max(ZERO, remaining),
        insurance_absorbed=max(ZERO, -remaining),
        cancel_scope=CancelScope.SYMBOL,
    )
