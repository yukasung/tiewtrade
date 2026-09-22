"""fasttrade Trading Core.

Pure Python: no I/O, no wall-clock reads, Decimal for all money values
(ADR-0001, docs/specs/calculation.md). Must not import services, infra,
Binance clients, FastAPI, SQLAlchemy, or Redis (enforced by import-linter).
"""

from fasttrade_core._decimal import CALC as DECIMAL_CONTEXT

__version__ = "0.1.0"

__all__ = ["DECIMAL_CONTEXT", "__version__"]
