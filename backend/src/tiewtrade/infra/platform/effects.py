"""Durable aggregate reconciliation for supported-symbol removal effects."""

from collections.abc import Mapping
from typing import Any, Protocol

from sqlalchemy import Result


class _Executor(Protocol):
    async def execute(
        self, statement: str, parameters: Mapping[str, object] | None = None
    ) -> Result[Any]: ...


async def reconcile_removal_effects(session: _Executor) -> int:
    result = await session.execute("SELECT reconcile_supported_symbol_effects()")
    return int(result.scalar_one())


async def reconcile_maintenance_proofs(session: _Executor) -> int:
    """Persist zero-exposure evidence before removed-pair feeds may stop."""
    result = await session.execute("SELECT reconcile_supported_symbol_maintenance()")
    return int(result.scalar_one())
