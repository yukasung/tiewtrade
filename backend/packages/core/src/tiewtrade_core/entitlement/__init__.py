"""Plan Entitlement: the limits a User cannot cross (FR-PLN-03..12, D-11).

The values come from the caller, read out of ``plan_entitlements`` (data model §6.2),
because an Admin can change every one of them and a constant here would drift from the
database. What this module owns is the arithmetic of deciding whether something is over
the line (architecture §4.2).

The Portfolio Risk Rules of FR-RSK-02 are **not** here: that set is still **Proposed**,
and several of its rules (order rate limit, max daily loss) need a clock, which the core
does not have. Entitlement is the outer bound, and a Portfolio's own rules may only be
stricter (FR-PLN-09).
"""

from tiewtrade_core.entitlement.leverage import effective_max_leverage, within_leverage
from tiewtrade_core.entitlement.notional import (
    FuturesSymbolExposure,
    SpotSymbolExposure,
    open_notional,
    projected_notional,
    within_limit,
)
from tiewtrade_core.entitlement.plan import Entitlement

__all__ = [
    "Entitlement",
    "FuturesSymbolExposure",
    "SpotSymbolExposure",
    "effective_max_leverage",
    "open_notional",
    "projected_notional",
    "within_leverage",
    "within_limit",
]
