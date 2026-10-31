"""Durable owner-bound order commands and DB-clock fenced fair dispatch."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from tiewtrade.core.orders import (
    OrderConflictError,
    OrderIntent,
    SafetyUnavailableError,
    SourceUnavailableError,
    TradingMode,
    UnsupportedOrderError,
)
from tiewtrade.core.positions import ExecutionSide, PositionPair
from tiewtrade.infra.db.session import (
    ScanSession,
    UserSession,
    require_user_session,
)
from tiewtrade.infra.market_data.order_book_codec import canonical
from tiewtrade.infra.paper_orders.codec import intent_payload, object_payload
from tiewtrade.infra.paper_orders.initialization import (
    enable_financial_writer,
    initialize_order_source,
)
from tiewtrade.infra.paper_orders.routing import (
    ADMISSION_FIRST_DUE_SQL,
    LEGACY_DUE_SQL,
    PREFERENCE_PROOF_SQL,
    SAME_PAIR_DUE_SQL,
    SOURCE_RESUME_PROOF_SQL,
    source_resume_due_sql,
)
from tiewtrade.infra.paper_orders.storage import (
    increment_wallet_revision,
    lock_active_episode,
    lock_pair_catalog,
)


class OrderClaimLostError(OrderConflictError):
    code = "ORDER_CLAIM_LOST"


@dataclass(frozen=True, slots=True)
class DueOrder:
    command_id: UUID
    user_id: UUID
    next_attempt_at: datetime
    anchor_command_id: UUID | None = None
    anchor_due_at: datetime | None = None
    source_resumption: bool = False
    source_wait_revision: int | None = None


@dataclass(frozen=True, slots=True)
class ClaimedOrder:
    command_id: UUID
    user_id: UUID
    claim_id: UUID
    revision: int
    source_resumption: bool = False


@dataclass(frozen=True, slots=True)
class OrderCommand:
    command_id: UUID
    state: str
    snapshot: dict[str, Any] | None = None
    failure_code: str | None = None


async def get_order_command(session: UserSession, command_id: UUID) -> OrderCommand | None:
    session = require_user_session(session)
    row = (
        await session.execute(
            """SELECT c.id,r.state,r.snapshot,r.failure_code
      FROM paper_order_commands c LEFT JOIN paper_order_command_results r ON r.command_id=c.id
      WHERE c.id=:id""",
            {"id": command_id},
        )
    ).first()
    if row is None:
        return None
    return OrderCommand(
        row.id,
        row.state or "PENDING",
        None if row.snapshot is None else object_payload(row.snapshot),
        row.failure_code,
    )


async def complete_command(
    session: UserSession,
    *,
    command_id: UUID,
    episode_id: UUID,
    succeeded: bool,
    snapshot: dict[str, object],
    failure_code: str | None = None,
) -> OrderCommand:
    """Store one immutable terminal admission/cancel response, with exact replay."""
    session = require_user_session(session)
    if succeeded == (failure_code is not None):
        raise OrderConflictError("command outcome shape is invalid")
    encoded = canonical(snapshot)
    await session.execute(
        """INSERT INTO paper_order_command_results
        (command_id,user_id,episode_id,state,failure_code,snapshot)
        VALUES(:id,:user,:episode,:state,:failure,CAST(:snapshot AS jsonb))
        ON CONFLICT(command_id) DO NOTHING""",
        {
            "id": command_id,
            "user": session.user_id,
            "episode": episode_id,
            "state": "SUCCEEDED" if succeeded else "REJECTED",
            "failure": failure_code,
            "snapshot": encoded,
        },
    )
    result = await get_order_command(session, command_id)
    if result is None or result.snapshot != snapshot or result.failure_code != failure_code:
        raise OrderConflictError("command outcome identity conflict")
    return result


async def lock_opening_pair_catalog(session: UserSession, pair: PositionPair) -> int:
    """Hold a row-share lock so removal cannot pass this opening submission."""
    try:
        catalog = await lock_pair_catalog(session, pair)
    except SourceUnavailableError:
        raise SafetyUnavailableError("supported-symbol catalog is unavailable") from None
    if not catalog.snapshot.supports(pair.base, pair.quote):
        raise UnsupportedOrderError("opening pair is not in catalog")
    return catalog.snapshot.revision


async def _submit(
    session: UserSession,
    *,
    wallet_id: UUID,
    episode_id: UUID,
    order_id: UUID,
    key: UUID,
    action: str,
    payload: dict[str, object],
    opening_pair: PositionPair | None = None,
    admitted_catalog_revision: int | None = None,
) -> OrderCommand:
    session = require_user_session(session)
    request_payload = {"wallet": str(wallet_id), "episode": str(episode_id), **payload}
    fingerprint = hashlib.sha256(canonical(request_payload).encode()).hexdigest()
    # Serialize replay lookup with admission, including retries across episode closure.
    await session.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(:key,0))",
        {"key": f"paper-wallet:{session.user_id}"},
    )
    row = (
        await session.execute(
            """SELECT id,request_fingerprint FROM paper_order_commands
      WHERE user_id=:user AND action=:action AND idempotency_key=:key""",
            {"user": session.user_id, "action": action, "key": key},
        )
    ).first()
    if row is not None:
        if row.request_fingerprint != fingerprint:
            raise OrderConflictError("idempotency payload conflict")
        prior = await get_order_command(session, row.id)
        assert prior is not None
        return prior
    await lock_active_episode(session, wallet_id, episode_id)
    catalog_revision = None
    if opening_pair is not None:
        catalog_revision = await lock_opening_pair_catalog(session, opening_pair)
        if admitted_catalog_revision is not None:
            fence = await lock_pair_catalog(session, opening_pair)
            if (
                type(admitted_catalog_revision) is not int
                or admitted_catalog_revision <= 0
                or admitted_catalog_revision > catalog_revision
                or (
                    fence.latest_removed_revision is not None
                    and fence.latest_removed_revision > admitted_catalog_revision
                )
            ):
                raise UnsupportedOrderError("opening catalog revision was invalidated")
            catalog_revision = admitted_catalog_revision
    elif admitted_catalog_revision is not None:
        raise OrderConflictError("catalog revision is only valid for opening orders")
    receipt = await initialize_order_source(
        session,
        wallet_id=wallet_id,
        episode_id=episode_id,
        initialization_id=uuid5(NAMESPACE_URL, f"tiewtrade:paper-order:{episode_id}"),
    )
    ready = (
        await session.execute(
            """SELECT 1 FROM paper_order_activity o JOIN paper_position_activity p
            USING(episode_id) WHERE o.episode_id=:episode
              AND o.availability='READY' AND p.availability='READY'
              AND o.source_proof=:order_proof AND p.source_proof=:position_proof""",
            {
                "episode": episode_id,
                "order_proof": receipt.source_proof,
                "position_proof": receipt.position_proof,
            },
        )
    ).first()
    if ready is None:
        raise OrderConflictError("Paper financial sources are not ready")
    await enable_financial_writer(session)
    stored_payload = dict(request_payload)
    if catalog_revision is not None:
        stored_payload["catalog_revision"] = catalog_revision
    identity = uuid4()
    params = {
        "id": identity,
        "user": session.user_id,
        "wallet": wallet_id,
        "episode": episode_id,
        "order": order_id,
        "key": key,
        "action": action,
        "fingerprint": fingerprint,
        "payload": canonical(stored_payload),
    }
    await session.execute(
        """INSERT INTO paper_order_commands
      (id,user_id,wallet_id,episode_id,action,idempotency_key,order_id,request_fingerprint,payload)
      VALUES(:id,:user,:wallet,:episode,:action,:key,:order,:fingerprint,
             CAST(:payload AS jsonb))""",
        params,
    )
    await session.execute(
        """INSERT INTO paper_order_dispatch(command_id,user_id,episode_id)
      VALUES(:id,:user,:episode)""",
        params,
    )
    await increment_wallet_revision(session, wallet_id)
    return OrderCommand(identity, "PENDING")


async def submit_order(
    session: UserSession,
    *,
    wallet_id: UUID,
    intent: OrderIntent,
    admitted_catalog_revision: int | None = None,
) -> OrderCommand:
    session = require_user_session(session)
    if intent.scope.owner_id != session.user_id or intent.scope.mode is not TradingMode.PAPER:
        raise OrderConflictError("Paper command owner/mode mismatch")
    return await _submit(
        session,
        wallet_id=wallet_id,
        episode_id=intent.scope.episode_id,
        order_id=intent.order_id,
        key=intent.idempotency_key,
        action="NEW",
        payload={"intent": intent_payload(intent)},
        opening_pair=intent.pair if intent.side is ExecutionSide.BUY else None,
        admitted_catalog_revision=admitted_catalog_revision,
    )


async def submit_cancel(
    session: UserSession,
    *,
    wallet_id: UUID,
    episode_id: UUID,
    order_id: UUID,
    idempotency_key: UUID,
) -> OrderCommand:
    return await _submit(
        session,
        wallet_id=wallet_id,
        episode_id=episode_id,
        order_id=order_id,
        key=idempotency_key,
        action="CANCEL",
        payload={"order_id": str(order_id)},
    )


async def due_orders(
    session: ScanSession,
    *,
    limit: int = 20,
    prefer_same_pair: bool = False,
    admission_first: bool = False,
    source_resumption: bool = False,
) -> tuple[DueOrder, ...]:
    if not isinstance(session, ScanSession):
        raise TypeError("scanner session required")
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("bounded order batch required")
    if type(prefer_same_pair) is not bool:
        raise ValueError("explicit same-pair selector option required")
    if type(admission_first) is not bool or (admission_first and not prefer_same_pair):
        raise ValueError("admission priority requires explicit same-pair preference")
    if type(source_resumption) is not bool:
        raise ValueError("explicit source-resumption option required")
    if source_resumption:
        query = source_resume_due_sql(
            prefer_same_pair=prefer_same_pair, admission_first=admission_first
        )
    elif admission_first:
        query = ADMISSION_FIRST_DUE_SQL
    else:
        query = SAME_PAIR_DUE_SQL if prefer_same_pair else LEGACY_DUE_SQL
    rows = await session.execute(query, {"limit": limit})
    return tuple(
        DueOrder(
            row.command_id,
            row.user_id,
            row.next_attempt_at,
            row.anchor_command_id if prefer_same_pair else None,
            row.anchor_due_at if prefer_same_pair else None,
            source_resumption,
            row.probe_revision if source_resumption else None,
        )
        for row in rows
    )


async def claim_order(session: UserSession, due: DueOrder, *, worker: str) -> ClaimedOrder | None:
    session = require_user_session(session)
    if session.user_id != due.user_id or not worker or len(worker) > 128:
        raise OrderConflictError("invalid claim scope")
    if type(due.source_resumption) is not bool or (
        due.source_wait_revision is not None
        and (
            not due.source_resumption
            or type(due.source_wait_revision) is not int
            or due.source_wait_revision < 1
            or due.anchor_command_id is not None
        )
    ):
        raise OrderConflictError("invalid source-resumption hint")
    # Serialize the check with admissions, reset and other claims without waiting
    # behind a financial writer. The scanner's busy-owner filter is only a hint.
    acquired = (
        await session.execute(
            "SELECT pg_try_advisory_xact_lock(hashtextextended(:key,0))",
            {"key": f"paper-wallet:{session.user_id}"},
        )
    ).scalar_one()
    if not acquired:
        return None
    if (due.anchor_command_id is None) != (due.anchor_due_at is None):
        raise OrderConflictError("incomplete same-pair preference anchor")
    if due.anchor_command_id is not None:
        proof = (
            await session.execute(
                PREFERENCE_PROOF_SQL,
                {
                    "user": session.user_id,
                    "id": due.command_id,
                    "expected_due": due.next_attempt_at,
                    "anchor": due.anchor_command_id,
                    "anchor_due": due.anchor_due_at,
                },
            )
        ).first()
        if proof is None:
            return None
    if due.source_wait_revision is not None:
        proof = (
            await session.execute(
                SOURCE_RESUME_PROOF_SQL,
                {
                    "id": due.command_id,
                    "user": session.user_id,
                    "expected_due": due.next_attempt_at,
                    "wait_revision": due.source_wait_revision,
                },
            )
        ).first()
        if proof is None:
            return None
    token = uuid4()
    probe = due.source_wait_revision is not None
    due_predicate = (
        "state='PENDING' AND next_attempt_at>clock_timestamp() "
        "AND source_wait_revision=:wait_revision AND claim_revision=:wait_revision "
        "AND NOT source_resume_used AND NOT source_resume_claim"
        if probe
        else "next_attempt_at<=clock_timestamp()"
    )
    claim_update = (
        "lease_until=least(clock_timestamp()+interval '30 seconds',next_attempt_at),"
        "source_resume_used=true,source_resume_claim=true"
        if probe
        else "lease_until=clock_timestamp()+interval '30 seconds',attempts=attempts+1"
        + (",source_resume_claim=false" if due.source_resumption else "")
    )
    # A delayed batch must not claim the next scheduled round of the same command.
    row = (
        await session.execute(
            f"""WITH candidate AS (
      SELECT command_id FROM paper_order_dispatch
      WHERE command_id=:id AND user_id=:user AND state<>'TERMINAL'
        AND next_attempt_at=:expected_due
        AND {due_predicate}
        AND (lease_until IS NULL OR lease_until<=clock_timestamp())
        AND NOT EXISTS(SELECT 1 FROM paper_order_dispatch busy
          WHERE busy.user_id=:user AND busy.state='CLAIMED'
            AND busy.lease_until>clock_timestamp())
      FOR UPDATE SKIP LOCKED)
      UPDATE paper_order_dispatch
      SET state='CLAIMED',worker=:worker,claim_id=:token,claim_revision=claim_revision+1,
        {claim_update}
      WHERE command_id IN (SELECT command_id FROM candidate)
      RETURNING claim_revision""",
            {
                "id": due.command_id,
                "user": session.user_id,
                "worker": worker,
                "token": token,
                "expected_due": due.next_attempt_at,
                "wait_revision": due.source_wait_revision,
            },
        )
    ).first()
    if row is not None and due.anchor_command_id is not None:
        guarded = (
            await session.execute(
                """UPDATE paper_order_dispatch SET preferred_for_due=:anchor_due
                WHERE command_id=:anchor AND next_attempt_at=:anchor_due
                  AND preferred_for_due IS DISTINCT FROM next_attempt_at RETURNING command_id""",
                {"anchor": due.anchor_command_id, "anchor_due": due.anchor_due_at},
            )
        ).first()
        if guarded is None:
            raise OrderClaimLostError("same-pair preference anchor changed")
    return (
        None
        if row is None
        else ClaimedOrder(
            due.command_id, due.user_id, token, row.claim_revision, due.source_resumption
        )
    )


async def require_claim(session: UserSession, claim: ClaimedOrder) -> None:
    session = require_user_session(session)
    row = (
        await session.execute(
            """SELECT state,claim_id,claim_revision,lease_until
      FROM paper_order_dispatch WHERE command_id=:id FOR UPDATE""",
            {"id": claim.command_id},
        )
    ).first()
    now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
    if (
        row is None
        or session.user_id != claim.user_id
        or row.state != "CLAIMED"
        or (
            row.claim_id != claim.claim_id
            or row.claim_revision != claim.revision
            or row.lease_until <= now
        )
    ):
        raise OrderClaimLostError("order claim expired or replaced")


async def finish_claim(
    session: UserSession,
    claim: ClaimedOrder,
    *,
    terminal: bool,
    retry_delay_ms: int = 20,
) -> None:
    if type(retry_delay_ms) is not int or not 20 <= retry_delay_ms <= 1000:
        raise ValueError("bounded dispatch retry delay required")
    # A healthy poll/decision ends the failure streak. claim_revision remains
    # monotonic and continues to fence stale workers independently of retries.
    await require_claim(session, claim)
    await session.execute(
        """UPDATE paper_order_dispatch
      SET state=:state,worker=NULL,claim_id=NULL,lease_until=NULL,attempts=0,
        next_attempt_at=clock_timestamp()+CAST(:retry_delay AS integer)*interval '1 millisecond'
      WHERE command_id=:id""",
        {
            "id": claim.command_id,
            "state": "TERMINAL" if terminal else "PENDING",
            "retry_delay": retry_delay_ms,
        },
    )


async def defer_claim(
    session: UserSession, claim: ClaimedOrder, *, source_unavailable: bool = False
) -> None:
    session = require_user_session(session)
    if type(source_unavailable) is not bool:
        raise ValueError("explicit source-unavailable outcome required")
    # Only a source exception establishes a wait. A failed early probe retains
    # its original due/attempt count; generic failures never create a wait.
    schedule = """clock_timestamp()+CASE WHEN attempts<=1 THEN interval '1 second'
          WHEN attempts=2 THEN interval '5 seconds' WHEN attempts=3 THEN interval '30 seconds'
          ELSE interval '5 minutes' END"""
    marker = ""
    if claim.source_resumption:
        schedule = f"CASE WHEN source_resume_claim THEN next_attempt_at ELSE {schedule} END"
        marker = """,source_resume_claim=false,
          source_wait_since=CASE WHEN :source_unavailable AND NOT source_resume_used
            THEN clock_timestamp() ELSE NULL END,
          source_wait_revision=CASE WHEN :source_unavailable AND NOT source_resume_used
            THEN claim_revision ELSE NULL END"""
    # CAS prevents an expired/replaced worker from changing a new claim's schedule.
    await session.execute(
        f"""UPDATE paper_order_dispatch
      SET state='PENDING',worker=NULL,claim_id=NULL,lease_until=NULL,
        next_attempt_at={schedule}{marker}
      WHERE command_id=:id AND user_id=:user AND state='CLAIMED'
        AND claim_id=:token AND claim_revision=:revision""",
        {
            "id": claim.command_id,
            "user": claim.user_id,
            "token": claim.claim_id,
            "revision": claim.revision,
            "source_unavailable": source_unavailable,
        },
    )


async def reschedule_processed_orders(
    session: UserSession, claim: ClaimedOrder, *, order_ids: tuple[UUID, ...]
) -> None:
    """Finish the scheduling work already covered by the pair's persisted checkpoint.

    Only admitted NEW commands in PENDING state qualify. New admissions, cancels,
    other pairs and live claims retain their schedules and claim fences.
    """
    session = require_user_session(session)
    await require_claim(session, claim)
    await session.execute(
        """UPDATE paper_order_dispatch AS d
        SET attempts=0,
            state=CASE WHEN p.status IN ('FILLED','CANCELED','EXPIRED','REJECTED')
                       THEN 'TERMINAL' ELSE 'PENDING' END,
            next_attempt_at=clock_timestamp()+interval '200 milliseconds'
        FROM paper_orders o
        JOIN paper_order_projections p ON p.order_id=o.id
        JOIN paper_order_command_results r ON r.command_id=o.command_id
        WHERE d.command_id=o.command_id AND d.command_id<>:claim
          AND d.state='PENDING' AND r.state='SUCCEEDED'
          AND o.id=ANY(CAST(:orders AS uuid[]))""",
        {"claim": claim.command_id, "orders": list(order_ids)},
    )
