"""The Execution Adapter port and the Paper Fill Model (calculation spec §4.1-4.3).

Pure computation, which is why it lives in the core (ADR-0001, architecture §4.3). Not to
be confused with the ``tiewtrade_execution`` service, the Phase 2 Live gateway that holds
decrypted API secrets (P-10); the two share a word, nothing else.
"""

from tiewtrade_core.execution.adapter import ExecutionAdapter
from tiewtrade_core.execution.book import TopOfBook
from tiewtrade_core.execution.fills import (
    PaperFill,
    is_marketable,
    limit_fill_on_submit,
    market_fill,
    resting_limit_fill,
    resting_limit_fills,
)
from tiewtrade_core.execution.liquidation import (
    CancelScope,
    ClosedPosition,
    LiquidatablePosition,
    Liquidation,
    cross_liquidation,
    isolated_liquidation,
)
from tiewtrade_core.execution.paper import (
    MarketSnapshot,
    PaperExecutionAdapter,
    ReportSink,
    resting_fill_report,
)
from tiewtrade_core.execution.report import ExecutionReport, ReportKind
from tiewtrade_core.execution.triggers import (
    BracketLeg,
    closing_side,
    stop_loss_triggered,
    take_profit_triggered,
    triggered_leg,
)

__all__ = [
    "BracketLeg",
    "CancelScope",
    "ClosedPosition",
    "ExecutionAdapter",
    "ExecutionReport",
    "LiquidatablePosition",
    "Liquidation",
    "MarketSnapshot",
    "PaperExecutionAdapter",
    "PaperFill",
    "ReportKind",
    "ReportSink",
    "TopOfBook",
    "closing_side",
    "cross_liquidation",
    "is_marketable",
    "isolated_liquidation",
    "limit_fill_on_submit",
    "market_fill",
    "resting_fill_report",
    "resting_limit_fill",
    "resting_limit_fills",
    "stop_loss_triggered",
    "take_profit_triggered",
    "triggered_leg",
]
