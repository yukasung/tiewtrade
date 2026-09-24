from dataclasses import dataclass
from decimal import Decimal

from tiewtrade_core.market import TradingMode


@dataclass(frozen=True, slots=True)
class Entitlement:
    """What a Plan allows, as the Admin has it configured (FR-PLN-03, D-11).

    A snapshot the caller reads from ``plan_entitlements`` (data model §6.2) and passes
    in; the core holds no defaults of its own, because every value here is one the Admin
    can change and a constant in the code would quietly disagree with the database.

    These are limits a User cannot cross. A Portfolio's own Risk Rules may be stricter
    but never looser (FR-PLN-09), so every check here is the outer bound.
    """

    max_leverage: int
    paper_notional_limit: Decimal
    live_enabled: bool
    live_notional_limit: Decimal
    max_paper_portfolios: int
    max_live_portfolios: int

    def __post_init__(self) -> None:
        # The bounds mirror the CHECK constraints on ``plan_entitlements`` (data model
        # §6.2); they reject a row that could not have been stored, and are not a policy
        # of their own. The *values* still come from the caller.
        if not 1 <= self.max_leverage <= 125:
            raise ValueError("max leverage must be between 1 and 125")
        if self.paper_notional_limit < 0 or self.live_notional_limit < 0:
            raise ValueError("a notional limit must not be negative")
        if self.max_paper_portfolios < 0 or self.max_live_portfolios < 0:
            raise ValueError("a portfolio limit must not be negative")

    def notional_limit(self, mode: TradingMode) -> Decimal:
        """The Workspace notional limit for one Trading Mode (FR-PLN-04)."""
        if mode is TradingMode.PAPER:
            return self.paper_notional_limit
        return self.live_notional_limit

    def portfolio_limit(self, mode: TradingMode) -> int:
        if mode is TradingMode.PAPER:
            return self.max_paper_portfolios
        return self.max_live_portfolios

    def allows(self, mode: TradingMode) -> bool:
        """Whether the Plan may trade in this mode at all (``LIVE_NOT_ENTITLED``).

        Losing Live entitlement does not close anything: reducing and closing positions
        stays possible, and only opening is refused (FR-PLN-11). That distinction is the
        caller's to apply, since it depends on the order.
        """
        return mode is TradingMode.PAPER or self.live_enabled

    def allows_another_portfolio(self, mode: TradingMode, existing: int) -> bool:
        """Whether one more Portfolio may be created (``PORTFOLIO_LIMIT_REACHED``).

        Going over the limit after the fact — an Admin lowering it, or a downgrade — does
        not delete anything; the extra Portfolios stay readable but cannot start a Bot
        (FR-PLN-11).
        """
        if existing < 0:
            raise ValueError("the existing count must not be negative")
        return existing < self.portfolio_limit(mode)
