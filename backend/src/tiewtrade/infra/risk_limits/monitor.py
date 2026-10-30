"""Bounded chronological risk replay under the existing owner financial lock."""

import json
from dataclasses import replace
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from tiewtrade.infra.risk_limits.monitor_snapshot import MonitorSnapshot

from tiewtrade.core.money import MoneyError
from tiewtrade.core.orders import TradingMode
from tiewtrade.core.positions import PositionError
from tiewtrade.core.risk_limits import (
    RiskBook,
    RiskEvaluation,
    RiskReason,
    RiskScope,
    RiskSetting,
    RiskUnavailableError,
    apply_risk_execution,
    evaluate_risk,
    iter_risk_evaluations,
    latch_risk,
)
from tiewtrade.infra.audit import (
    ActorKind,
    AuditAction,
    AuditEvent,
    AuditMode,
    AuditOutcome,
    RiskLimitDetails,
    SubjectKind,
    record_event,
)
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.positions import PositionIntegrityError, read_position_snapshot
from tiewtrade.infra.positions.records import PositionEventKind
from tiewtrade.infra.positions.storage import read_position_revision
from tiewtrade.infra.risk_limits.books import (
    authoritative_book,
    book_from_payload,
    book_payload,
    marker_positions,
    reconstruct_book,
)
from tiewtrade.infra.risk_limits.dispatch import lock_risk_owner
from tiewtrade.infra.risk_limits.prices import (
    RiskPriceFrame,
    price_watermark,
    read_frame,
    read_frames,
)


async def persist_evaluation(
    session: UserSession,
    setting: RiskSetting,
    evaluation: RiskEvaluation,
    *,
    watermark: int,
    replay_pending: bool,
) -> RiskSetting:
    updated = latch_risk(setting, evaluation)
    params = {
        "owner": setting.scope.owner_id,
        "mode": setting.scope.mode.value,
        "revision": updated.revision,
        "source": evaluation.source_revision,
        "watermark": watermark,
        "reason": evaluation.reason.value,
        "loss": None if evaluation.loss is None else evaluation.loss.amount,
        "latched": updated.latched,
        "pending": replay_pending,
        "at": evaluation.evaluated_at,
    }
    if evaluation.new_breach:
        identity = uuid4()
        await session.execute(
            """UPDATE risk_limit_settings SET latched=true,revision=:revision,
            updated_at=clock_timestamp() WHERE user_id=:owner AND mode=:mode""",
            params,
        )
        await session.execute(
            """INSERT INTO risk_limit_events
            (id,user_id,mode,revision,kind,amount,latched,source_revision,details)
            VALUES(:id,:owner,:mode,:revision,'BREACH',:amount,true,:source,
              jsonb_build_object('price_watermark',CAST(:watermark AS bigint)))""",
            {**params, "id": identity, "amount": setting.limit.amount if setting.limit else None},
        )
        if setting.scope.mode is TradingMode.PAPER:
            await session.execute(
                """INSERT INTO risk_stop_requests
                (id,user_id,mode,event_id,wallet_id,episode_id,risk_revision)
                VALUES(:id,:owner,'PAPER',:id,:wallet,:episode,:revision)""",
                {
                    **params,
                    "id": identity,
                    "wallet": setting.scope.wallet_id,
                    "episode": setting.scope.episode_id,
                },
            )
            await session.execute(
                """INSERT INTO risk_stop_progress(stop_id,user_id,mode)
                VALUES(:id,:owner,'PAPER')""",
                {"id": identity, "owner": session.user_id},
            )
        await record_event(
            session,
            AuditEvent(
                owner_user_id=session.user_id,
                action=AuditAction.RISK_LIMIT_BREACHED,
                actor_kind=ActorKind.SYSTEM,
                subject_kind=SubjectKind.RISK_LIMIT,
                subject_id=str(session.user_id),
                outcome=AuditOutcome.SUCCEEDED,
                details=RiskLimitDetails(identity, None, updated.revision, updated.limit),
                mode=AuditMode(setting.scope.mode.value),
            ),
        )
    await session.execute(
        """INSERT INTO risk_limit_evaluations
        (user_id,mode,setting_revision,source_revision,price_watermark,reason,loss,latched,
          evaluated_at,input_ready_at,replay_pending,unavailable_since,pause_alert_due)
        VALUES(:owner,:mode,:revision,:source,:watermark,CAST(:reason AS text),
          CAST(:loss AS numeric),:latched,clock_timestamp(),
          CASE WHEN CAST(:loss AS numeric) IS NOT NULL THEN CAST(:at AS timestamptz) END,:pending,
          CASE WHEN CAST(:reason AS text)='RISK_PRICE_UNAVAILABLE'
            THEN CAST(:at AS timestamptz) END,false)
        ON CONFLICT(user_id,mode) DO UPDATE SET setting_revision=EXCLUDED.setting_revision,
          source_revision=EXCLUDED.source_revision,price_watermark=EXCLUDED.price_watermark,
          reason=EXCLUDED.reason,loss=EXCLUDED.loss,latched=EXCLUDED.latched,
          evaluated_at=EXCLUDED.evaluated_at,input_ready_at=EXCLUDED.input_ready_at,
          replay_pending=EXCLUDED.replay_pending,
          unavailable_since=CASE WHEN EXCLUDED.reason='RISK_PRICE_UNAVAILABLE'
            THEN coalesce(risk_limit_evaluations.unavailable_since,EXCLUDED.unavailable_since) END,
          pause_alert_due=EXCLUDED.reason='RISK_PRICE_UNAVAILABLE' AND
            coalesce(risk_limit_evaluations.unavailable_since,EXCLUDED.unavailable_since)
            <=EXCLUDED.evaluated_at-interval '5 minutes'""",
        params,
    )
    return updated


async def initialize_monitor(
    session: UserSession,
    setting: RiskSetting,
) -> RiskEvaluation:
    """Initialize in the SET transaction, so no post-setting price is skipped."""
    await lock_risk_owner(session, setting.scope.mode)
    if not (
        await session.execute("SELECT publication_enabled FROM risk_protocol_control")
    ).scalar_one():
        raise RiskUnavailableError("price publication protocol is disabled")
    watermark = int((await session.execute("SELECT risk_financial_fence()")).scalar_one())
    book, proof = await authoritative_book(session, setting.scope)
    frame = await read_frame(session, watermark) if watermark else None
    boundary = int(
        (
            await session.execute(
                "SELECT coalesce(max(sequence),0) FROM risk_financial_boundaries WHERE mode='PAPER'"
            )
        ).scalar_one()
    )
    now: datetime = (await session.execute("SELECT clock_timestamp()")).scalar_one()
    evaluation = evaluate_risk(
        setting,
        book,
        () if frame is None else frame.prices,
        now=now,
        source_ready=True,
    )
    await _save_cursor(session, book, proof, watermark, boundary, pending=False)
    await persist_evaluation(
        session, setting, evaluation, watermark=watermark, replay_pending=False
    )
    return evaluation


async def _save_cursor(
    session: UserSession,
    book: RiskBook,
    proof: str,
    cursor: int,
    boundary_cursor: int,
    *,
    pending: bool,
) -> None:
    document = book_payload(book)
    saved = await session.execute(
        """WITH previous AS MATERIALIZED (
          SELECT book,source_revision,episode_id FROM risk_owner_state WHERE mode=:mode
        ), saved AS (
        INSERT INTO risk_owner_state
        (user_id,mode,wallet_id,episode_id,cursor,source_revision,source_proof,book,
          replay_pending,boundary_cursor)
        VALUES(:owner,:mode,:wallet,:episode,:cursor,:revision,:proof,CAST(:book AS jsonb),
          :pending,:boundary)
        ON CONFLICT(user_id,mode) DO UPDATE SET wallet_id=EXCLUDED.wallet_id,
          episode_id=EXCLUDED.episode_id,cursor=EXCLUDED.cursor,source_revision=EXCLUDED.source_revision,
          source_proof=EXCLUDED.source_proof,book=EXCLUDED.book,replay_pending=EXCLUDED.replay_pending,
          boundary_cursor=EXCLUDED.boundary_cursor,observed_at=clock_timestamp(),
          due_at=clock_timestamp()+CASE WHEN EXCLUDED.replay_pending
            THEN interval '0 seconds' ELSE interval '200 milliseconds' END
        RETURNING mode)
        SELECT NOT EXISTS(SELECT 1 FROM previous) OR EXISTS(
          SELECT 1 FROM previous WHERE book IS DISTINCT FROM CAST(:book AS jsonb)
            OR source_revision IS DISTINCT FROM :revision
            OR episode_id IS DISTINCT FROM CAST(:episode AS uuid)) AS changed FROM saved""",
        {
            "owner": session.user_id,
            "mode": book.scope.mode.value,
            "wallet": book.scope.wallet_id,
            "episode": book.scope.episode_id,
            "cursor": cursor,
            "revision": book.source_revision,
            "proof": proof,
            "book": json.dumps(document),
            "pending": pending,
            "boundary": boundary_cursor,
        },
    )
    changed = bool(saved.scalar_one())
    if changed:
        # This table is a replaceable projection. Immutable financial/baseline
        # facts remain untouched; price-only ticks do not rewrite pair rows.
        await session.execute(
            "DELETE FROM risk_limit_pairs WHERE mode=:mode", {"mode": book.scope.mode.value}
        )
        await session.execute(
            """INSERT INTO risk_limit_pairs
            (user_id,mode,base,quote,allowance,adjusted_realized,source_sequence,source_revision)
            SELECT :owner,:mode,r.base,r.quote,r.allowance,r.adjusted,r.sequence,:revision
            FROM jsonb_to_recordset(CAST(:rows AS jsonb)) AS r(
              base text,quote text,allowance numeric,adjusted numeric,sequence bigint)""",
            {
                "owner": session.user_id,
                "mode": book.scope.mode.value,
                "revision": book.source_revision,
                "rows": json.dumps(document["pairs"]),
            },
        )


async def replay_monitor(
    session: UserSession,
    setting: RiskSetting,
    *,
    frame_budget: int = 100,
    boundary_budget: int = 20,
    publication_fence: bool = True,
    final_publication_fence: bool = False,
    snapshot: "MonitorSnapshot | None" = None,
) -> RiskEvaluation:
    """A later source gap must not roll back a breach already found in this round."""
    checked = require_user_session(session)
    if not 1 <= frame_budget <= 100 or not 1 <= boundary_budget <= 100:
        raise ValueError("bounded risk replay required")
    if snapshot is not None and (
        publication_fence
        or final_publication_fence
        or boundary_budget > 20
        or snapshot.owner_id != checked.user_id
    ):
        raise ValueError("captured snapshot is only for standalone replay")
    await lock_risk_owner(checked, setting.scope.mode)
    try:
        return await _replay_monitor(
            checked,
            setting,
            frame_budget=frame_budget,
            boundary_budget=boundary_budget,
            publication_fence=publication_fence,
            final_publication_fence=final_publication_fence,
            snapshot=snapshot,
        )
    except (
        RiskUnavailableError,
        PositionIntegrityError,
        MoneyError,
        PositionError,
        ValueError,
        KeyError,
        TypeError,
    ):
        row = (
            await checked.execute(
                "SELECT revision,latched FROM risk_limit_settings WHERE mode=:mode",
                {"mode": setting.scope.mode.value},
            )
        ).one()
        current = replace(setting, revision=int(row.revision), latched=bool(row.latched))
        now: datetime = (await checked.execute("SELECT clock_timestamp()")).scalar_one()
        result = RiskEvaluation(
            current.scope,
            current.revision,
            0,
            now,
            RiskReason.SOURCE_UNAVAILABLE,
            None,
            current.latched,
            False,
        )
        await persist_evaluation(
            checked, current, result, watermark=await price_watermark(checked), replay_pending=True
        )
        await checked.execute(
            """UPDATE risk_owner_state SET replay_pending=true,
            due_at=clock_timestamp()+interval '200 milliseconds' WHERE mode=:mode""",
            {"mode": setting.scope.mode.value},
        )
        return result


async def _replay_monitor(
    session: UserSession,
    setting: RiskSetting,
    *,
    frame_budget: int = 100,
    boundary_budget: int = 20,
    publication_fence: bool = True,
    final_publication_fence: bool = False,
    snapshot: "MonitorSnapshot | None" = None,
) -> RiskEvaluation:
    checked = require_user_session(session)
    if not 1 <= frame_budget <= 100 or not 1 <= boundary_budget <= 100:
        raise ValueError("bounded risk replay required")

    async def frame_page(after: int, through: int, limit: int = 100) -> tuple[RiskPriceFrame, ...]:
        if snapshot is not None:
            return snapshot.read_frames(after=after, through=through, limit=limit)
        return await read_frames(checked, after=after, through=through, limit=limit)

    # Public replay_monitor holds this owner lock across replay and its error handler.
    if publication_fence:
        await checked.execute("SELECT risk_financial_fence()")
    # A standalone monitor needs only the owner lock: financial markers and
    # holdings cannot change under it, and the captured publication watermark
    # includes only committed immutable frames. Later frames remain for the next
    # round. A publishing monitor uses a short final drain below, so a READY
    # projection can commit at the current watermark. Financial callers retain
    # their initial fence through their final commit; reduction callers do not
    # opt into the final fence.
    state = (
        snapshot.state
        if snapshot is not None
        else (
            (
                await checked.execute(
                    """SELECT o.*,e.reason previous_reason,p.watermark captured_watermark
                FROM risk_owner_state o
                CROSS JOIN (SELECT watermark FROM risk_price_publication LIMIT 1) p
                LEFT JOIN risk_limit_evaluations e ON (e.user_id,e.mode)=(o.user_id,o.mode)
                WHERE o.mode=:mode""",
                    {"mode": setting.scope.mode.value},
                )
            )
            .mappings()
            .one_or_none()
        )
    )
    if state is None:
        raise RiskUnavailableError("risk monitor has not been initialized")
    scope = RiskScope(
        setting.scope.owner_id,
        TradingMode.PAPER,
        UUID(str(state["wallet_id"])),
        UUID(str(state["episode_id"])),
    )
    expected_scope = setting.scope
    setting = replace(setting, scope=scope)
    book = book_from_payload(scope, int(state["source_revision"]), state["book"])
    proof = str(state["source_proof"])
    cursor = int(state["cursor"])
    boundary_cursor = int(state["boundary_cursor"])
    watermark = int(state["captured_watermark"])
    latest_frame = None
    boundaries = (
        snapshot.boundaries
        if snapshot is not None
        else (
            (
                await checked.execute(
                    """SELECT * FROM risk_financial_boundaries
        WHERE mode='PAPER' AND sequence>:cursor
        ORDER BY sequence LIMIT :limit""",
                    {"cursor": boundary_cursor, "limit": boundary_budget + 1},
                )
            )
            .mappings()
            .all()
        )
    )
    # Preserve breach and price-pause transitions, including historical recovery
    # followed by another outage. Ordinary ticks only need the final projection.
    paused = state["previous_reason"] == RiskReason.PRICE_UNAVAILABLE.value
    used = 0
    blocked = False
    for marker in boundaries[:boundary_budget]:
        target = int(marker["price_watermark"])
        if target < cursor or marker["episode_id"] != scope.episode_id:
            raise RiskUnavailableError("financial marker order or scope is inconsistent")
        count = min(target - cursor, frame_budget - used)
        if count:
            frames = await frame_page(cursor, cursor + count, count)
            setting, paused = await _evaluate_frames(checked, setting, book, frames, paused)
            latest_frame = frames[-1]
            cursor += count
            used += count
        if cursor != target:
            blocked = True
            break
        before, after = marker["before_state"], marker["after_state"]
        if int(before["revision"]) != book.source_revision or marker_positions(before) != tuple(
            item.position for item in book.pairs
        ):
            raise RiskUnavailableError("financial marker before-state mismatch")
        if marker["kind"] == "EPISODE":
            scope = RiskScope(
                scope.owner_id,
                TradingMode.PAPER,
                scope.wallet_id,
                UUID(str(marker["after_episode_id"])),
            )
            setting = replace(setting, scope=scope)
            proof = str(after["source_proof"])
        if after["availability"] != "READY" or after["source_proof"] != proof:
            raise RiskUnavailableError("financial marker source is unavailable")
        assert scope.episode_id is not None
        positions = marker_positions(after)
        revision = int(after["revision"])
        if (
            book.scope == scope
            and revision == book.source_revision
            and tuple(item.position for item in book.pairs) == positions
        ):
            pass
        elif marker["kind"] == "FILL" and revision == book.source_revision + 1:
            _, kind, fact = await read_position_revision(checked, scope.episode_id, revision)
            if kind is not PositionEventKind.RECORD or fact is None:
                raise RiskUnavailableError("fill boundary has no exact execution")
            book = apply_risk_execution(book, fact, source_revision=revision)
        elif marker["kind"] == "CORRECTION" and revision == book.source_revision + 1:
            pair, kind, _ = await read_position_revision(checked, scope.episode_id, revision)
            if kind is PositionEventKind.RECORD:
                raise RiskUnavailableError("correction boundary has no exact correction")
            changed = next((position for position in positions if position.pair == pair), None)
            if changed is None:
                raise RiskUnavailableError("corrected projection missing")
            rebuilt = await reconstruct_book(
                checked,
                scope,
                positions=(changed,),
                revision=revision,
                sequence=int(after["source_sequence"]),
            )
            book = RiskBook(
                scope,
                revision,
                tuple(
                    rebuilt.pairs[0] if item.position.pair == pair else item for item in book.pairs
                ),
            )
        else:
            book = await reconstruct_book(
                checked,
                scope,
                positions=positions,
                revision=revision,
                sequence=int(after["source_sequence"]),
            )
        if tuple(item.position for item in book.pairs) != positions:
            raise RiskUnavailableError("risk replay disagrees with the financial marker")
        frame = (
            latest_frame
            if latest_frame is not None and latest_frame.watermark == cursor
            else (await frame_page(cursor - 1, cursor))[0]
        )
        latest_frame = frame
        decision = evaluate_risk(
            setting, book, frame.prices, now=marker["recorded_at"], source_ready=True
        )
        price_pause = decision.reason is RiskReason.PRICE_UNAVAILABLE
        if decision.new_breach or price_pause != paused:
            setting = await persist_evaluation(
                checked, setting, decision, watermark=cursor, replay_pending=True
            )
        paused = price_pause
        boundary_cursor = int(marker["sequence"])
    pending = blocked or len(boundaries) > boundary_budget
    if not pending:
        count = min(watermark - cursor, frame_budget - used)
        if count:
            frames = await frame_page(cursor, cursor + count, count)
            setting, paused = await _evaluate_frames(checked, setting, book, frames, paused)
            latest_frame = frames[-1]
            cursor += count
            used += count
        pending = cursor != watermark
    assert scope.episode_id is not None
    position_snapshot = (
        (
            snapshot.position(scope.episode_id)
            if snapshot is not None and scope.episode_id == snapshot.owner["active_episode_id"]
            else await read_position_snapshot(checked, scope.episode_id)
        )
        if not pending
        else None
    )
    ready = (
        position_snapshot is not None
        and scope == expected_scope
        and position_snapshot.activity.revision == book.source_revision
        and (
            position_snapshot.activity.availability.value == "READY"
            and position_snapshot.activity.source_proof == proof
        )
    )
    if final_publication_fence and not pending:
        # Do the expensive historical replay/source proof without blocking the
        # producer. Only the bounded tail and commit hold this shared fence.
        # Otherwise a monitor taking longer than one tick can *always* commit
        # behind the publisher, leaving API intake permanently unavailable.
        await checked.execute("SELECT risk_financial_fence()")
        watermark = await price_watermark(checked)
        if watermark < cursor:
            raise RiskUnavailableError("risk publication watermark moved backwards")
        count = min(watermark - cursor, frame_budget - used)
        if count:
            frames = await frame_page(cursor, cursor + count, count)
            setting, paused = await _evaluate_frames(checked, setting, book, frames, paused)
            latest_frame = frames[-1]
            cursor += count
        pending = cursor != watermark
    now: datetime = (await checked.execute("SELECT clock_timestamp()")).scalar_one()
    if cursor and (latest_frame is None or latest_frame.watermark != cursor):
        latest_frame = (await frame_page(cursor - 1, cursor))[0]
    decision = evaluate_risk(
        setting,
        book,
        () if latest_frame is None else latest_frame.prices,
        now=now,
        source_ready=ready,
    )
    if pending:
        decision = replace(
            decision, reason=RiskReason.SOURCE_UNAVAILABLE, loss=None, new_breach=False
        )
    await persist_evaluation(checked, setting, decision, watermark=cursor, replay_pending=pending)
    await _save_cursor(checked, book, proof, cursor, boundary_cursor, pending=pending)
    return decision


async def _evaluate_frames(
    session: UserSession,
    setting: RiskSetting,
    book: RiskBook,
    frames: tuple[RiskPriceFrame, ...],
    paused: bool,
) -> tuple[RiskSetting, bool]:
    """Evaluate every verified frame and preserve transient breach/pause changes."""
    evaluations = iter_risk_evaluations(
        setting,
        book,
        tuple((frame.captured_at, frame.prices) for frame in frames),
        source_ready=True,
    )
    for frame, decision in zip(frames, evaluations, strict=True):
        price_pause = decision.reason is RiskReason.PRICE_UNAVAILABLE
        if decision.new_breach or price_pause != paused:
            setting = await persist_evaluation(
                session, setting, decision, watermark=frame.watermark, replay_pending=True
            )
        paused = price_pause
    return setting, paused


async def mark_unavailable_owner(session: UserSession, setting: RiskSetting) -> RiskEvaluation:
    """Schedule an uninitialized source without presenting an empty book as READY."""
    now: datetime = (await session.execute("SELECT clock_timestamp()")).scalar_one()
    await session.execute(
        """INSERT INTO risk_owner_state
        (user_id,mode,wallet_id,episode_id,cursor,source_revision,source_proof,book,replay_pending,due_at)
        VALUES(:owner,:mode,:wallet,:episode,0,0,NULL,'{"pairs":[]}',true,
          clock_timestamp()+interval '200 milliseconds')
        ON CONFLICT(user_id,mode) DO UPDATE SET replay_pending=true,
          due_at=clock_timestamp()+interval '200 milliseconds'""",
        {
            "owner": session.user_id,
            "mode": setting.scope.mode.value,
            "wallet": setting.scope.wallet_id,
            "episode": setting.scope.episode_id,
        },
    )
    result = RiskEvaluation(
        setting.scope,
        setting.revision,
        0,
        now,
        RiskReason.SOURCE_UNAVAILABLE,
        None,
        setting.latched,
        False,
    )
    await persist_evaluation(
        session, setting, result, watermark=await price_watermark(session), replay_pending=True
    )
    return result
