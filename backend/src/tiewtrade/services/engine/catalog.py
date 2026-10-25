"""Engine-owned conditional activation coordinator for prepared catalog pairs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole, InfraError, user_session
from tiewtrade.infra.db.session import presented_session
from tiewtrade.infra.platform import (
    ConstraintEvidence,
    activate,
    fail_preparation,
    prepare,
    preparing_symbols,
    read_catalog,
    reconcile_maintenance_proofs,
    requested_symbols,
)
from tiewtrade.venues import Symbol, VenueError, VenueRateLimitedError, VenueUnavailableError
from tiewtrade.venues.order_books import ExecutionCapabilitySource


async def activate_ready_symbols(
    engine: AsyncEngine,
    source: ExecutionCapabilitySource,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    """Activate every currently ready pair after a new exact venue check."""
    async with presented_session(engine, role=DatabaseRole.ENGINE) as session:
        await reconcile_maintenance_proofs(session)
        requested = await requested_symbols(session)
    for base, quote, pair_revision, requester in requested:
        try:
            async with user_session(engine, requester, role=DatabaseRole.ENGINE) as session:
                current = await read_catalog(session)
                if not any(
                    entry.base == base and entry.quote == quote and entry.revision == pair_revision
                    for entry in current.entries
                ):
                    continue
                await prepare(
                    session,
                    base=base,
                    quote=quote,
                    expected_revision=current.snapshot.revision,
                )
        except InfraError:
            # Another coordinator may have advanced the same request. Every retry
            # rebuilds state from PostgreSQL instead of reusing a stale revision.
            continue
    async with presented_session(engine, role=DatabaseRole.ENGINE) as session:
        pending = await preparing_symbols(session)
    activated = 0
    for base, quote, pair_revision, requester in pending:
        try:
            async with user_session(engine, requester, role=DatabaseRole.ENGINE) as session:
                current = await read_catalog(session)
        except InfraError:
            # No venue result may transition a command without its original revision.
            continue
        if not any(
            entry.base == base and entry.quote == quote and entry.revision == pair_revision
            for entry in current.entries
        ):
            continue
        expected_revision = current.snapshot.revision
        symbol = Symbol(base, quote)
        started_at = clock()
        try:
            capability = await source.capability(symbol)
        except (VenueRateLimitedError, VenueUnavailableError):
            continue
        except VenueError as error:
            await _fail_preparation(engine, requester, base, quote, expected_revision, error.code)
            continue
        completed_at = clock()
        invalid = (
            capability.symbol != symbol
            or capability.observed_at < started_at
            or capability.observed_at > completed_at
            or capability.market.unsupported_rules
            or capability.limit.unsupported_rules
        )
        if invalid:
            await _fail_preparation(
                engine, requester, base, quote, expected_revision, "VENUE_PROTOCOL"
            )
            continue
        try:
            async with user_session(engine, requester, role=DatabaseRole.ENGINE) as session:
                await activate(
                    session,
                    base=base,
                    quote=quote,
                    expected_revision=expected_revision,
                    validation_started_at=started_at,
                    evidence=ConstraintEvidence(
                        venue_symbol=f"{base}{quote}",
                        observed_at=capability.observed_at,
                        source_document=capability.source_document,
                        digest=capability.version,
                    ),
                )
            activated += 1
        except InfraError:
            # Readiness/revision may change concurrently; the next round rebuilds
            # state from PostgreSQL and retries without reusing an old decision.
            continue
    return activated


async def _fail_preparation(
    engine: AsyncEngine,
    requester: UUID,
    base: str,
    quote: str,
    expected_revision: int,
    failure_code: str,
) -> None:
    try:
        async with user_session(engine, requester, role=DatabaseRole.ENGINE) as session:
            await fail_preparation(
                session,
                base=base,
                quote=quote,
                expected_revision=expected_revision,
                failure_code=failure_code,
            )
    except InfraError:
        # A concurrent transition won. The next pass reads its result.
        pass
