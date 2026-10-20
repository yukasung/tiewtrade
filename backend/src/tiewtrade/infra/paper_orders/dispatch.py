"""Durable owner-bound order commands and DB-clock fenced fair dispatch."""

import hashlib
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from tiewtrade.core.orders import OrderConflictError, OrderIntent, TradingMode
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
from tiewtrade.infra.paper_orders.storage import increment_wallet_revision, lock_active_episode


class OrderClaimLostError(OrderConflictError):
    code = "ORDER_CLAIM_LOST"


@dataclass(frozen=True, slots=True)
class DueOrder:
    command_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class ClaimedOrder:
    command_id: UUID
    user_id: UUID
    claim_id: UUID
    revision: int


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


async def _submit(
    session: UserSession,
    *,
    wallet_id: UUID,
    episode_id: UUID,
    order_id: UUID,
    key: UUID,
    action: str,
    payload: dict[str, object],
) -> OrderCommand:
    session = require_user_session(session)
    encoded = canonical({"wallet": str(wallet_id), "episode": str(episode_id), **payload})
    fingerprint = hashlib.sha256(encoded.encode()).hexdigest()
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
        "payload": encoded,
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
    session: UserSession, *, wallet_id: UUID, intent: OrderIntent
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


async def due_orders(session: ScanSession, *, limit: int = 20) -> tuple[DueOrder, ...]:
    if not isinstance(session, ScanSession):
        raise TypeError("scanner session required")
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("bounded order batch required")
    rows = (
        await session.execute(
            """WITH due AS (
      SELECT command_id,user_id,next_attempt_at,
        row_number() OVER(PARTITION BY user_id ORDER BY next_attempt_at,command_id) rank
      FROM paper_order_dispatch WHERE state<>'TERMINAL' AND next_attempt_at<=clock_timestamp()
        AND (lease_until IS NULL OR lease_until<=clock_timestamp()))
      SELECT command_id,user_id FROM due WHERE rank=1
      ORDER BY next_attempt_at,command_id LIMIT :limit""",
            {"limit": limit},
        )
    ).all()
    return tuple(DueOrder(row.command_id, row.user_id) for row in rows)


async def claim_order(session: UserSession, due: DueOrder, *, worker: str) -> ClaimedOrder | None:
    session = require_user_session(session)
    if session.user_id != due.user_id or not worker or len(worker) > 128:
        raise OrderConflictError("invalid claim scope")
    token = uuid4()
    row = (
        await session.execute(
            """UPDATE paper_order_dispatch
      SET state='CLAIMED',worker=:worker,claim_id=:token,claim_revision=claim_revision+1,
        lease_until=clock_timestamp()+interval '30 seconds',attempts=attempts+1
      WHERE command_id=:id AND user_id=:user AND state<>'TERMINAL'
        AND next_attempt_at<=clock_timestamp()
        AND (lease_until IS NULL OR lease_until<=clock_timestamp())
      RETURNING claim_revision""",
            {"id": due.command_id, "user": session.user_id, "worker": worker, "token": token},
        )
    ).first()
    return (
        None
        if row is None
        else ClaimedOrder(due.command_id, due.user_id, token, row.claim_revision)
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


async def finish_claim(session: UserSession, claim: ClaimedOrder, *, terminal: bool) -> None:
    await require_claim(session, claim)
    await session.execute(
        """UPDATE paper_order_dispatch
      SET state=:state,worker=NULL,claim_id=NULL,lease_until=NULL,
        next_attempt_at=clock_timestamp()+interval '20 milliseconds'
      WHERE command_id=:id""",
        {"id": claim.command_id, "state": "TERMINAL" if terminal else "PENDING"},
    )


async def defer_claim(session: UserSession, claim: ClaimedOrder) -> None:
    # CAS prevents an expired worker from changing the new worker's schedule.
    await session.execute(
        """UPDATE paper_order_dispatch
      SET state='PENDING',worker=NULL,claim_id=NULL,lease_until=NULL,
        next_attempt_at=clock_timestamp()+CASE WHEN attempts<=1 THEN interval '1 second'
          WHEN attempts=2 THEN interval '5 seconds' WHEN attempts=3 THEN interval '30 seconds'
          ELSE interval '5 minutes' END
      WHERE command_id=:id AND user_id=:user AND state='CLAIMED'
        AND claim_id=:token AND claim_revision=:revision""",
        {
            "id": claim.command_id,
            "user": claim.user_id,
            "token": claim.claim_id,
            "revision": claim.revision,
        },
    )
