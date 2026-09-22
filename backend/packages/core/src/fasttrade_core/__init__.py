"""fasttrade Trading Core.

Pure Python: no I/O, no wall-clock reads, Decimal for all money values
(ADR-0001, docs/specs/calculation.md). Must not import services, infra,
Binance clients, FastAPI, SQLAlchemy, or Redis (enforced by import-linter).
"""

__version__ = "0.1.0"
