"""F-21 bounded suffix reads from authoritative F-11 checkpoint state."""

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from sqlalchemy import RowMapping

from tiewtrade.core.indicators import IndicatorStream
from tiewtrade.core.market_data import CandleWindow, slot_count
from tiewtrade.core.money import Money, Scalar
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.indicators.codec import CODEC_VERSION, decode_checkpoint
from tiewtrade.infra.indicators.prepared import (
    PreparedNotReadyError,
    fresh_proof_valid,
    read_generation_authority,
    read_prepared,
)
from tiewtrade.infra.indicators.read_contract import CursorClaims
from tiewtrade.infra.indicators.source import PROOF_SQL, SourceFence, proof_parameters
from tiewtrade.infra.market_data.indicator_reader import (
    IndicatorRead,
    query_budget,
    read_indicators,
)


@dataclass(frozen=True, slots=True)
class IndicatorTailProof:
    fence: SourceFence
    start: datetime
    end: datetime
    prefix_end: datetime | None = None


@dataclass(frozen=True, slots=True)
class BotIndicatorPage:
    generation: RowMapping
    result: IndicatorRead
    tail: IndicatorTailProof | None = None


async def require_tail_proof(
    session: UserSession, generation: RowMapping, proof: IndicatorTailProof
) -> bool:
    return bool(
        (
            await session.execute(
                PROOF_SQL,
                proof_parameters(
                    proof.fence,
                    source=generation["source"],
                    base=generation["base"],
                    quote=generation["quote"],
                    timeframe=generation["timeframe"],
                    start=proof.start,
                    end=proof.end,
                ),
            )
        ).scalar_one()
    )


async def read_bot_indicator_page(
    session: UserSession,
    claims: CursorClaims,
    control: RowMapping,
    now: datetime,
    deadline: float,
    *,
    allow_tail: bool,
) -> BotIndicatorPage:
    try:
        page = await read_prepared(
            session, claims, control, now, deadline, continuation=False, explicit_range=True
        )
        return BotIndicatorPage(page.generation, page.result)
    except PreparedNotReadyError:
        if not allow_tail:
            raise
    await query_budget(session, deadline)
    if (
        control["mode"] != "PREPARED"
        or control["protocol_version"] != 1
        or control["codec_version"] != CODEC_VERSION
        or control["source_proof_state"] != "READY"
        or control["retention_policy"] != "GRACE"
    ):
        raise PreparedNotReadyError()
    generation, failure = await read_generation_authority(
        session, claims.base, claims.quote, claims.timeframe, claims.formula_version
    )
    if generation is None or failure is not None:
        raise PreparedNotReadyError()
    # Restore before the first changed candle, including a finality promotion
    # inside the published head. Never certify a stale checkpoint with a new fence.
    changed = (
        await session.execute(
            "SELECT min(open_at) FROM indicator_source_changes WHERE epoch=:epoch "
            "AND revision>:fence AND source=:source AND base=:base AND quote=:quote "
            "AND timeframe=:timeframe AND open_at>=:lo AND open_at<:hi",
            {
                "epoch": generation["source_epoch"],
                "fence": generation["source_fence"],
                "source": claims.source,
                "base": claims.base,
                "quote": claims.quote,
                "timeframe": claims.timeframe.value,
                "lo": generation["calculation_start"],
                "hi": claims.result_end,
            },
        )
    ).scalar_one_or_none()
    boundary = min(
        generation["calculation_end"],
        claims.result_start,
        changed if changed is not None else claims.result_start,
    )
    checkpoint = (
        (
            await session.execute(
                "SELECT next_open_at,payload FROM indicator_ready_checkpoints "
                "WHERE generation_id=:id AND next_open_at<=:boundary "
                "ORDER BY next_open_at DESC LIMIT 1",
                {"id": generation["id"], "boundary": boundary},
            )
        )
        .mappings()
        .one_or_none()
    )
    if checkpoint is None:
        raise PreparedNotReadyError()
    replay_start = checkpoint["next_open_at"]
    if replay_start >= claims.result_end:
        raise PreparedNotReadyError()
    tail_window = CandleWindow(replay_start, claims.result_end)
    if slot_count(tail_window, claims.timeframe) >= 1000:
        raise PreparedNotReadyError()
    restored = decode_checkpoint(
        checkpoint["payload"],
        generation_id=str(generation["id"]),
        source=claims.source,
        base=claims.base,
        quote=claims.quote,
        timeframe=claims.timeframe,
        as_of=generation["as_of"],
        calculation=CandleWindow(generation["calculation_start"], generation["calculation_end"]),
        next_open_at=replay_start,
    )
    stream = IndicatorStream(claims.base, claims.quote, claims.timeframe, now)
    stream.restore_state(restored.export_state())
    source = (
        await session.execute("SELECT epoch,revision FROM indicator_source_guard WHERE id=1")
    ).one()
    proof = IndicatorTailProof(
        SourceFence(UUID(str(source.epoch)), source.revision),
        generation["calculation_start"],
        claims.result_end,
        replay_start,
    )
    # Recheck the old prefix AFTER capturing the new fence. A correction in
    # between must never certify an outdated checkpoint with a newer fence.
    if not await fresh_proof_valid(session, generation, now, through=replay_start):
        raise PreparedNotReadyError()
    result = await read_indicators(
        session,
        claims.base,
        claims.quote,
        claims.timeframe,
        tail_window,
        CandleWindow(claims.result_start, claims.result_end),
        now,
        deadline,
        restored=stream,
        prepared_revision=generation["dataset_revision"],
    )
    if not await require_tail_proof(session, generation, proof):
        raise PreparedNotReadyError()
    # Source-fence changes outside this calculation do not change a pure input.
    payload = [
        {
            "at": p.open_at.isoformat(),
            "seed": None if p.seed_open_at is None else p.seed_open_at.isoformat(),
            "values": {
                name: {
                    "status": value.status.value,
                    "value": value.value.as_parts()
                    if isinstance(value.value, Money)
                    else value.value.as_text()
                    if isinstance(value.value, Scalar)
                    else None,
                }
                for name, value in sorted(p.values.items())
            },
        }
        for p in result.points
    ]
    revision = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    return BotIndicatorPage(
        generation, replace(result, revision=f"{result.revision}:tail:{revision}"), proof
    )
