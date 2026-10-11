"""Fixed builder claim protocol; no direct derived-table mutation."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import cast
from uuid import UUID

from tiewtrade.core.market_data import Timeframe
from tiewtrade.infra.indicators.session import (
    IndicatorWriterSession,
    require_indicator_writer_session,
)


class AttemptOutcome(StrEnum):
    TRANSIENT = "TRANSIENT"
    SOURCE_CHANGED = "SOURCE_CHANGED"
    OWNERSHIP_LOST = "OWNERSHIP_LOST"
    OPERATIONAL = "OPERATIONAL"


class PublicationResult(StrEnum):
    READY = "READY"
    FAILED_NUMERIC = "FAILED_NUMERIC"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True, slots=True)
class BuildClaim:
    job_id: UUID
    generation_id: UUID
    token: UUID
    slot_epoch: UUID
    fence: int
    owner_instance: UUID
    backend_pid: int
    attempt_deadline: datetime
    lease_until: datetime
    source: str
    base: str
    quote: str
    timeframe: Timeframe
    formula_version: str
    candidate_sequence: int
    rollout_epoch: UUID
    codec_version: int
    dispatch_round: int

    def parameters(self) -> dict[str, object]:
        return {
            "epoch": self.slot_epoch,
            "fence": self.fence,
            "owner": self.owner_instance,
            "job": self.job_id,
            "generation": self.generation_id,
            "token": self.token,
        }


_IDENTITY = ":epoch,:fence,:owner,:job,:generation,:token"


async def _timeouts(session: IndicatorWriterSession) -> None:
    await session.execute("""SELECT set_config('lock_timeout','200ms',true),
        set_config('statement_timeout','500ms',true)""")


async def seed_jobs(session: IndicatorWriterSession) -> int:
    session = require_indicator_writer_session(session)
    await _timeouts(session)
    return int((await session.execute("SELECT public.seed_indicator_build_jobs()")).scalar_one())


async def claim_next(session: IndicatorWriterSession, owner: UUID) -> BuildClaim | None:
    session = require_indicator_writer_session(session)
    if type(owner) is not UUID:
        raise ValueError("builder owner UUID required")
    await _timeouts(session)
    row = (
        (
            await session.execute(
                "SELECT * FROM public.claim_indicator_build_job(:owner)", {"owner": owner}
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return BuildClaim(
        cast(UUID, row["job_id"]),
        cast(UUID, row["generation_id"]),
        cast(UUID, row["claim_token"]),
        cast(UUID, row["slot_epoch"]),
        int(row["fence"]),
        owner,
        int(row["owner_backend_pid"]),
        cast(datetime, row["attempt_deadline"]),
        cast(datetime, row["lease_until"]),
        str(row["source"]),
        str(row["base"]),
        str(row["quote"]),
        Timeframe(row["timeframe"]),
        str(row["formula_version"]),
        int(row["candidate_sequence"]),
        cast(UUID, row["build_rollout_epoch"]),
        int(row["codec_version"]),
        int(row["dispatch_round"]),
    )


async def heartbeat(session: IndicatorWriterSession, claim: BuildClaim) -> datetime:
    session = require_indicator_writer_session(session)
    await _timeouts(session)
    return cast(
        datetime,
        (
            await session.execute(
                f"SELECT public.heartbeat_indicator_build_claim({_IDENTITY})", claim.parameters()
            )
        ).scalar_one(),
    )


async def release(
    session: IndicatorWriterSession, claim: BuildClaim, outcome: AttemptOutcome
) -> None:
    """Caller must stop/join build work and close the source snapshot before release."""
    session = require_indicator_writer_session(session)
    if type(outcome) is not AttemptOutcome:
        raise ValueError("fixed builder outcome required")
    await _timeouts(session)
    await session.execute(
        f"SELECT public.release_indicator_build_claim({_IDENTITY},:reason)",
        claim.parameters() | {"reason": outcome.value},
    )


async def publish(
    session: IndicatorWriterSession, claim: BuildClaim, *, numeric: bool
) -> PublicationResult:
    """Publish stored attempt metadata; never pass exception text or partial results."""
    session = require_indicator_writer_session(session)
    await _timeouts(session)
    function = "publish_indicator_numeric_failure" if numeric else "publish_indicator_ready"
    return PublicationResult(
        (
            await session.execute(f"SELECT public.{function}({_IDENTITY})", claim.parameters())
        ).scalar_one()
    )
