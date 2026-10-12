"""One fenced attempt. Scheduling, recovery and polling are separate phases."""

import asyncio
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.money import MoneyError
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.errors import (
    DatabaseRetryableError,
    DatabaseTimeoutError,
    DatabaseUnavailableError,
    IndicatorBuildOwnershipError,
    SourceProofStateError,
)
from tiewtrade.infra.indicators.claims import AttemptOutcome, BuildClaim, PublicationResult
from tiewtrade.infra.indicators.pinned import PinnedIndicatorWriter, pinned_indicator_writer
from tiewtrade.infra.indicators.scan import scan_staging

ATTEMPT_SECONDS = 120.0
CLEANUP_SECONDS = 2.0


class AttemptStatus(StrEnum):
    LOCK_BUSY = "LOCK_BUSY"
    NO_JOB = "NO_JOB"
    READY = "READY"
    FAILED_NUMERIC = "FAILED_NUMERIC"
    SUPERSEDED = "SUPERSEDED"
    RELEASED = "RELEASED"
    ORPHANED = "ORPHANED"


@dataclass(frozen=True, slots=True)
class AttemptResult:
    status: AttemptStatus
    job_id: UUID | None = None
    generation_id: UUID | None = None
    reason: AttemptOutcome | None = None


def create_builder_engine() -> AsyncEngine:
    return create_engine_for(
        DatabaseRole.INDICATOR_BUILDER, pool_size=2, max_overflow=0, pool_timeout=0.25
    )


def _reason(error: Exception) -> AttemptOutcome:
    if isinstance(error, (IndicatorBuildOwnershipError, TimeoutError)):
        return AttemptOutcome.OWNERSHIP_LOST
    if isinstance(error, SourceProofStateError):
        return AttemptOutcome.SOURCE_CHANGED
    if isinstance(error, (DatabaseTimeoutError, DatabaseUnavailableError, DatabaseRetryableError)):
        return AttemptOutcome.TRANSIENT
    return AttemptOutcome.OPERATIONAL


async def _release(writer: PinnedIndicatorWriter, reason: AttemptOutcome) -> bool:
    try:
        async with asyncio.timeout(CLEANUP_SECONDS):
            await writer.finish(reason)
        return True
    except Exception:
        # The pinned context discards the session and retains durable orphan metadata.
        # Only verified process stop + migrator reap may recover this state.
        return False


async def _build(
    engine: AsyncEngine,
    writer: PinnedIndicatorWriter,
    claim: BuildClaim,
    *,
    scheduled: bool = False,
) -> PublicationResult:
    try:
        if scheduled:
            await scan_staging(engine, writer, claim, scheduled=True)
        else:
            await scan_staging(engine, writer, claim)
    except MoneyError as error:
        # scan_staging closes source and joins heartbeat before returning a numeric error.
        return await writer.publish_numeric_failure(claim, error)
    return await writer.publish_ready(claim)


async def run_attempt(
    engine: AsyncEngine,
    owner: UUID,
    *,
    connection_mode: Literal["direct", "session", "transaction", "statement"] = "direct",
    scheduled: bool = False,
) -> AttemptResult:
    """Run at most one pre-seeded job; never reconnect/resume/reap or retry here.

    Cancellation propagates after source/CPU shutdown and compare-identity release.
    A failed/ambiguous cleanup reports ORPHANED; the caller must stop this worker
    and arrange verified operator recovery before accepting further work.
    """
    if type(owner) is not UUID:
        raise ValueError("builder owner UUID required")
    claim: BuildClaim | None = None
    try:
        async with pinned_indicator_writer(engine, connection_mode=connection_mode) as writer:
            if writer is None:
                return AttemptResult(AttemptStatus.LOCK_BUSY)
            # Start before the claim query so client-side budget cannot extend DB's deadline.
            deadline = asyncio.get_running_loop().time() + ATTEMPT_SECONDS
            try:
                async with asyncio.timeout_at(deadline):
                    claim = await writer.claim(owner)
                    if claim is None:
                        return AttemptResult(AttemptStatus.NO_JOB)
                    publication = await _build(engine, writer, claim, scheduled=scheduled)
                result = AttemptResult(
                    AttemptStatus(publication.value), claim.job_id, claim.generation_id
                )
            except asyncio.CancelledError:
                if claim is not None:
                    await _release(writer, AttemptOutcome.OWNERSHIP_LOST)
                raise
            except Exception as error:
                reason = _reason(error)
                # A claim with no confirmed descriptor may already have committed.
                # Discard the pinned session; never manufacture an identity or retry it.
                released = claim is not None and await _release(writer, reason)
                result = AttemptResult(
                    AttemptStatus.RELEASED if released else AttemptStatus.ORPHANED,
                    claim.job_id if claim else None,
                    claim.generation_id if claim else None,
                    reason,
                )
        return result
    except asyncio.CancelledError:
        raise
    except Exception as error:
        # Acquire/claim/commit/physical cleanup may be ambiguous. No unsafe handoff.
        return AttemptResult(
            AttemptStatus.ORPHANED,
            claim.job_id if claim else None,
            claim.generation_id if claim else None,
            _reason(error),
        )
