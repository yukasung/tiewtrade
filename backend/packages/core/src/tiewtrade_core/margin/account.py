from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from tiewtrade_core._decimal import ZERO, calc
from tiewtrade_core.margin.exposure import FuturesExposure


@dataclass(frozen=True, slots=True)
class MarginRatio:
    """Margin Ratio for display and warnings only (calculation spec §2.4).

    ``value`` is None when there is no maintenance margin (no position) or when the
    margin balance is zero or negative; in the latter case ``insolvent`` is True and
    the UI shows ">= 100%".
    """

    value: Decimal | None
    insolvent: bool


@dataclass(frozen=True, slots=True)
class MarginState:
    margin_balance: Decimal
    maintenance_margin: Decimal

    @property
    def is_liquidatable(self) -> bool:
        """Authoritative liquidation condition: MM > 0 and Margin Balance <= MM.

        Never derived from the ratio, so a zero or negative balance cannot escape it.
        """
        return self.maintenance_margin > 0 and self.margin_balance <= self.maintenance_margin

    @property
    @calc
    def margin_ratio(self) -> MarginRatio:
        if self.maintenance_margin <= 0:
            return MarginRatio(value=None, insolvent=False)
        if self.margin_balance <= 0:
            return MarginRatio(value=None, insolvent=True)
        return MarginRatio(value=self.maintenance_margin / self.margin_balance, insolvent=False)


@calc
def cross_margin_state(
    cross_wallet_balance: Decimal, positions: Iterable[FuturesExposure]
) -> MarginState:
    """Margin state of all cross positions of a Portfolio together."""
    upnl = ZERO
    maintenance = ZERO
    for position in positions:
        upnl += position.unrealized_pnl
        maintenance += position.maintenance_margin
    return MarginState(margin_balance=cross_wallet_balance + upnl, maintenance_margin=maintenance)


@calc
def isolated_margin_state(isolated_wallet: Decimal, position: FuturesExposure) -> MarginState:
    """Margin state of one isolated position, backed only by its own isolated wallet."""
    return MarginState(
        margin_balance=isolated_wallet + position.unrealized_pnl,
        maintenance_margin=position.maintenance_margin,
    )
