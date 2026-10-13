"""Source snapshot identity and typed, fenced STAGING writes."""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast
from uuid import UUID

from tiewtrade.core.indicators import IndicatorStream
from tiewtrade.core.market_data import CandleWindow, align_ceil, align_floor
from tiewtrade.infra.db.errors import IndicatorBuildOwnershipError
from tiewtrade.infra.indicators.claims import BuildClaim
from tiewtrade.infra.indicators.codec import CODEC_VERSION, encode_checkpoint
from tiewtrade.infra.indicators.pinned import PinnedIndicatorWriter
from tiewtrade.infra.indicators.session import (
    IndicatorSourceSession,
    require_indicator_source_session,
)
from tiewtrade.infra.indicators.source import SourceFence

IDENTITY = ":epoch,:fence,:owner,:job,:generation,:token"


@dataclass(frozen=True, slots=True)
class StagingSnapshot:
    as_of: datetime
    fence: SourceFence
    calculation: CandleWindow


async def capture_snapshot(session: IndicatorSourceSession, claim: BuildClaim) -> StagingSnapshot:
    session = require_indicator_source_session(session)
    await session.execute("""SELECT set_config('statement_timeout','500ms',true),
        set_config('lock_timeout','200ms',true)""")
    row = (
        (
            await session.execute("""SELECT clock_timestamp() AS as_of,g.epoch,g.revision,
        c.rollout_epoch,c.mode,c.codec_version,c.protocol_version,c.retention_policy,
        c.source_proof_state,public.indicator_source_triggers_valid() AS triggers_valid
        FROM indicator_source_guard g CROSS JOIN indicator_rollout_control c
        WHERE g.id=1 AND c.id=1""")
        )
        .mappings()
        .one()
    )
    if (
        row["rollout_epoch"] != claim.rollout_epoch
        or row["mode"] not in ("PREPARING", "PREPARED")
        or row["codec_version"] != CODEC_VERSION
        or row["protocol_version"] != 1
        or row["retention_policy"] != "GRACE"
        or row["source_proof_state"] != "READY"
        or not row["triggers_valid"]
    ):
        raise IndicatorBuildOwnershipError("indicator source snapshot unavailable")
    as_of = cast(datetime, row["as_of"])
    return StagingSnapshot(
        as_of,
        SourceFence(cast(UUID, row["epoch"]), int(row["revision"])),
        CandleWindow(
            align_ceil(as_of - timedelta(days=365), claim.timeframe),
            align_floor(as_of, claim.timeframe),
        ),
    )


async def initialize(
    writer: PinnedIndicatorWriter, claim: BuildClaim, snapshot: StagingSnapshot
) -> None:
    writer.require_claim(claim)
    async with writer.transaction() as session:
        await session.execute(
            f"SELECT public.initialize_indicator_staging({IDENTITY},"
            ":as_of,:source_epoch,:source_fence)",
            claim.parameters()
            | {
                "as_of": snapshot.as_of,
                "source_epoch": snapshot.fence.epoch,
                "source_fence": snapshot.fence.revision,
            },
        )


async def append_checkpoint(
    writer: PinnedIndicatorWriter,
    claim: BuildClaim,
    snapshot: StagingSnapshot,
    stream: IndicatorStream,
    next_open_at: datetime,
) -> None:
    writer.require_claim(claim)
    if (
        stream.as_of != snapshot.as_of
        or stream.base != claim.base
        or stream.quote != claim.quote
        or stream.timeframe != claim.timeframe
    ):
        raise IndicatorBuildOwnershipError("indicator checkpoint identity differs")
    payload = encode_checkpoint(
        stream,
        generation_id=str(claim.generation_id),
        source=claim.source,
        calculation=snapshot.calculation,
        next_open_at=next_open_at,
    )
    async with writer.transaction() as session:
        await session.execute(
            f"SELECT public.append_indicator_checkpoint({IDENTITY},:next,CAST(:payload AS jsonb))",
            claim.parameters() | {"next": next_open_at, "payload": json.dumps(payload)},
        )


async def seal(writer: PinnedIndicatorWriter, claim: BuildClaim, digest: str) -> None:
    writer.require_claim(claim)
    async with writer.transaction() as session:
        await session.execute(
            f"SELECT public.seal_indicator_staging({IDENTITY},:digest)",
            claim.parameters() | {"digest": digest},
        )
