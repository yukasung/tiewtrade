"""Paper Fill Model: simulated fill prices and Bracket triggers (calculation spec §4.1-4.3).

Pure computation, which is why it lives in the core (ADR-0001, architecture §4.3). Not to
be confused with the ``tiewtrade_execution`` service, the Phase 2 Live gateway that holds
decrypted API secrets (P-10); the two share a word, nothing else.
"""

from tiewtrade_core.execution.book import TopOfBook
from tiewtrade_core.execution.fills import (
    PaperFill,
    is_marketable,
    limit_fill_on_submit,
    market_fill,
    resting_limit_fill,
    resting_limit_fills,
)
from tiewtrade_core.execution.triggers import (
    BracketLeg,
    closing_side,
    stop_loss_triggered,
    take_profit_triggered,
    triggered_leg,
)

__all__ = [
    "BracketLeg",
    "PaperFill",
    "TopOfBook",
    "closing_side",
    "is_marketable",
    "limit_fill_on_submit",
    "market_fill",
    "resting_limit_fill",
    "resting_limit_fills",
    "stop_loss_triggered",
    "take_profit_triggered",
    "triggered_leg",
]
