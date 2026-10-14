"""API-role prepared reads: proof, strict restore and bounded source suffix."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import RowMapping

from tiewtrade.core.market_data import (
    CandleWindow,
    Timeframe,
    advance,
    align_ceil,
    retention_cutoff,
    slot_count,
)
from tiewtrade.infra.crypto.indicator_cursor import (
    CursorClaims,
    DatasetChangedError,
    PreparedCursorClaims,
)
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.indicators.codec import CODEC_VERSION, decode_checkpoint
from tiewtrade.infra.market_data.indicator_reader import (
    IndicatorRead,
    query_budget,
    read_indicators,
)
from tiewtrade.infra.market_data.storage import parameters


class PreparedNotReadyError(ValueError):
    pass


class PreparedNumericError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PreparedPage:
    claims: PreparedCursorClaims
    generation: RowMapping
    result: IndicatorRead


async def rollout_control(session: UserSession, deadline: float) -> RowMapping:
    await query_budget(session, deadline)
    return (
        (await session.execute("SELECT * FROM indicator_rollout_control WHERE id=1"))
        .mappings()
        .one()
    )


async def proof_valid(session: UserSession, generation: RowMapping, now: datetime) -> bool:
    if generation["expires_at"] <= now or generation["codec_version"] != CODEC_VERSION:
        return False
    return bool(
        (
            await session.execute(
                """SELECT
      public.indicator_source_triggers_valid() AND g.epoch=:epoch
      AND :fence BETWEEN g.journal_floor AND g.revision
      AND NOT EXISTS(SELECT 1 FROM indicator_source_changes e WHERE e.epoch=g.epoch
        AND e.revision>:fence AND (e.kind='RESET' OR (e.source=:source AND e.base=:base
          AND e.quote=:quote AND e.timeframe=:timeframe AND e.open_at>=:lo AND e.open_at<:hi)))
      FROM indicator_source_guard g WHERE g.id=1""",
                {
                    "epoch": generation["source_epoch"],
                    "fence": generation["source_fence"],
                    "source": generation["source"],
                    "base": generation["base"],
                    "quote": generation["quote"],
                    "timeframe": generation["timeframe"],
                    "lo": generation["calculation_start"],
                    "hi": generation["calculation_end"],
                },
            )
        ).scalar_one()
    )


async def read_prepared(
    session: UserSession,
    claims: CursorClaims,
    control: RowMapping,
    now: datetime,
    deadline: float,
    *,
    continuation: bool,
    explicit_range: bool,
) -> PreparedPage:
    await query_budget(session, deadline)
    if (
        control["mode"] != "PREPARED"
        or control["protocol_version"] != 1
        or control["codec_version"] != CODEC_VERSION
        or control["source_proof_state"] != "READY"
        or control["retention_policy"] != "GRACE"
    ):
        if continuation:
            raise DatasetChangedError()
        raise PreparedNotReadyError()
    if continuation:
        if (
            not isinstance(claims, PreparedCursorClaims)
            or claims.rollout_epoch != control["rollout_epoch"]
        ):
            raise DatasetChangedError()
        generation = (
            (
                await session.execute(
                    "SELECT * FROM indicator_ready_generations WHERE id=:id",
                    {"id": claims.generation_id},
                )
            )
            .mappings()
            .first()
        )
        if generation is None:
            raise DatasetChangedError()
        for name in (
            "source",
            "base",
            "quote",
            "formula_version",
            "dataset_revision",
            "as_of",
            "calculation_start",
            "calculation_end",
            "codec_version",
        ):
            if generation[name] != getattr(claims, name):
                raise DatasetChangedError()
        if generation["timeframe"] != claims.timeframe.value or not await proof_valid(
            session, generation, now
        ):
            raise DatasetChangedError()
        selected = claims
    else:
        args = parameters(claims.base, claims.quote, claims.timeframe) | {
            "formula": claims.formula_version
        }
        generation = (
            (
                await session.execute(
                    """SELECT g.* FROM indicator_ready_heads h
            JOIN indicator_ready_generations g ON g.id=h.generation_id
            WHERE h.source=:source AND h.base=:base AND h.quote=:quote
              AND h.timeframe=:timeframe AND h.formula_version=:formula""",
                    args,
                )
            )
            .mappings()
            .first()
        )
        failure = (
            (
                await session.execute(
                    """SELECT * FROM indicator_numeric_failures
            WHERE source=:source AND base=:base AND quote=:quote AND timeframe=:timeframe
              AND formula_version=:formula""",
                    args,
                )
            )
            .mappings()
            .first()
        )
        if failure is not None and (
            generation is None or generation["candidate_sequence"] < failure["candidate_sequence"]
        ):
            if (
                not failure["manifest_available"]
                or failure["desired_start"] != failure["calculation_start"]
                or failure["desired_end"] != failure["calculation_end"]
                or not await proof_valid(session, failure, now)
                or (explicit_range and claims.result_end > failure["calculation_end"])
            ):
                raise PreparedNotReadyError()
            raise PreparedNumericError()
        if (
            generation is None
            or not await proof_valid(session, generation, now)
            or not timedelta(0) <= now - generation["as_of"] <= timedelta(seconds=600)
        ):
            raise PreparedNotReadyError()
        end = claims.result_end if explicit_range else generation["calculation_end"]
        start = (
            claims.result_start
            if explicit_range
            else max(
                align_ceil(retention_cutoff(now, claims.timeframe), claims.timeframe),
                advance(end, claims.timeframe, -1000),
            )
        )
        if (
            end > generation["calculation_end"]
            or start < generation["calculation_start"]
            or start >= end
        ):
            raise PreparedNotReadyError()
        selected = PreparedCursorClaims.model_validate(
            claims.model_dump()
            | {
                "format_version": 2,
                "generation_id": generation["id"],
                "codec_version": CODEC_VERSION,
                "rollout_epoch": control["rollout_epoch"],
                "dataset_revision": generation["dataset_revision"],
                "as_of": generation["as_of"],
                "calculation_start": generation["calculation_start"],
                "calculation_end": generation["calculation_end"],
                "result_start": start,
                "result_end": end,
                "next_open_at": start,
                "expires_at": min(claims.expires_at, generation["expires_at"]),
            }
        )
    page_end = min(
        selected.result_end,
        advance(selected.next_open_at, selected.timeframe, selected.page_size),
    )
    checkpoint = (
        (
            await session.execute(
                """SELECT next_open_at,payload FROM indicator_ready_checkpoints
        WHERE generation_id=:id AND next_open_at<=:start ORDER BY next_open_at DESC LIMIT 1""",
                {"id": selected.generation_id, "start": selected.next_open_at},
            )
        )
        .mappings()
        .first()
    )
    if checkpoint is None:
        if continuation:
            raise DatasetChangedError()
        raise PreparedNotReadyError()
    if (
        checkpoint["next_open_at"] > selected.next_open_at
        or slot_count(
            CandleWindow(checkpoint["next_open_at"], selected.next_open_at),
            selected.timeframe,
        )
        >= 1000
    ):
        if continuation:
            raise DatasetChangedError()
        raise PreparedNotReadyError()
    stream = decode_checkpoint(
        checkpoint["payload"],
        generation_id=str(selected.generation_id),
        source=selected.source,
        base=selected.base,
        quote=selected.quote,
        timeframe=Timeframe(selected.timeframe),
        as_of=selected.as_of,
        calculation=CandleWindow(selected.calculation_start, selected.calculation_end),
        next_open_at=checkpoint["next_open_at"],
    )
    result = await read_indicators(
        session,
        selected.base,
        selected.quote,
        selected.timeframe,
        CandleWindow(checkpoint["next_open_at"], page_end),
        CandleWindow(selected.next_open_at, page_end),
        selected.as_of,
        deadline,
        restored=stream,
        prepared_revision=selected.dataset_revision,
    )
    return PreparedPage(selected, generation, result)
