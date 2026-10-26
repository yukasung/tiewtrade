"""Fair fenced claims for the pre-financial manual inbox."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from tiewtrade.core.orders import OrderConflictError
from tiewtrade.infra.db.session import ScanSession, UserSession, require_user_session
from tiewtrade.infra.paper_orders.requests import wallet_lock


class RequestClaimLostError(OrderConflictError):
    code = "ORDER_REQUEST_CLAIM_LOST"


@dataclass(frozen=True, slots=True)
class DueRequest:
    request_id: UUID
    user_id: UUID
    next_attempt_at: datetime


@dataclass(frozen=True, slots=True)
class ClaimedRequest:
    request_id: UUID
    user_id: UUID
    claim_id: UUID
    revision: int


async def due_requests(session: ScanSession, *, limit: int = 20) -> tuple[DueRequest, ...]:
    if not isinstance(session, ScanSession) or type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("bounded scanner session required")
    rows = (
        await session.execute(
            """WITH busy AS MATERIALIZED (
        SELECT DISTINCT user_id FROM paper_order_request_dispatch
        WHERE state='CLAIMED' AND lease_until>clock_timestamp()), candidates AS (
        SELECT request_id,user_id,next_attempt_at,
          row_number() OVER(PARTITION BY user_id ORDER BY next_attempt_at,request_id) AS rank
        FROM paper_order_request_dispatch d WHERE state<>'TERMINAL'
          AND next_attempt_at<=clock_timestamp()
          AND (lease_until IS NULL OR lease_until<=clock_timestamp())
          AND NOT EXISTS(SELECT 1 FROM busy b WHERE b.user_id=d.user_id))
        SELECT request_id,user_id,next_attempt_at FROM candidates WHERE rank=1
        ORDER BY next_attempt_at,request_id LIMIT :limit""",
            {"limit": limit},
        )
    ).all()
    return tuple(
        DueRequest(UUID(str(r.request_id)), UUID(str(r.user_id)), r.next_attempt_at) for r in rows
    )


async def claim_request(
    session: UserSession, due: DueRequest, *, worker: str
) -> ClaimedRequest | None:
    session = require_user_session(session)
    if session.user_id != due.user_id or not worker or len(worker) > 128:
        raise OrderConflictError("invalid request claim scope")
    acquired = (
        await session.execute(
            "SELECT pg_try_advisory_xact_lock(hashtextextended(:key,0))",
            {"key": f"paper-wallet:{session.user_id}"},
        )
    ).scalar_one()
    if not acquired:
        return None
    token = uuid4()
    row = (
        await session.execute(
            """UPDATE paper_order_request_dispatch d
        SET state='CLAIMED',worker=:worker,claim_id=:token,claim_revision=claim_revision+1,
            lease_until=clock_timestamp()+interval '30 seconds',attempts=attempts+1
        WHERE request_id=:id AND user_id=:owner AND state<>'TERMINAL'
          AND next_attempt_at=:due AND next_attempt_at<=clock_timestamp()
          AND (lease_until IS NULL OR lease_until<=clock_timestamp())
          AND NOT EXISTS(SELECT 1 FROM paper_order_request_dispatch b
            WHERE b.user_id=:owner AND b.state='CLAIMED' AND b.lease_until>clock_timestamp())
        RETURNING claim_revision""",
            {
                "worker": worker,
                "token": token,
                "id": due.request_id,
                "owner": session.user_id,
                "due": due.next_attempt_at,
            },
        )
    ).one_or_none()
    return (
        None
        if row is None
        else ClaimedRequest(due.request_id, due.user_id, token, row.claim_revision)
    )


async def require_request_claim(session: UserSession, claim: ClaimedRequest) -> None:
    session = require_user_session(session)
    if session.user_id != claim.user_id:
        raise RequestClaimLostError("request claim owner mismatch")
    await wallet_lock(session)
    row = (
        await session.execute(
            """SELECT 1 FROM paper_order_request_dispatch
        WHERE request_id=:id AND user_id=:owner AND state='CLAIMED'
          AND claim_id=:token AND claim_revision=:revision AND lease_until>clock_timestamp()
        FOR UPDATE""",
            {
                "id": claim.request_id,
                "owner": session.user_id,
                "token": claim.claim_id,
                "revision": claim.revision,
            },
        )
    ).first()
    if row is None:
        raise RequestClaimLostError("request claim expired or replaced")


async def finish_request_claim(session: UserSession, claim: ClaimedRequest) -> None:
    await require_request_claim(session, claim)
    await session.execute(
        """UPDATE paper_order_request_dispatch SET state='TERMINAL',
        worker=NULL,claim_id=NULL,lease_until=NULL WHERE request_id=:id""",
        {"id": claim.request_id},
    )


async def defer_request_claim(session: UserSession, claim: ClaimedRequest) -> None:
    session = require_user_session(session)
    if session.user_id != claim.user_id:
        raise RequestClaimLostError("request defer owner mismatch")
    await session.execute(
        """UPDATE paper_order_request_dispatch SET state='PENDING',
        worker=NULL,claim_id=NULL,lease_until=NULL,
        next_attempt_at=clock_timestamp()+CASE WHEN attempts<=1 THEN interval '1 second'
          WHEN attempts=2 THEN interval '5 seconds' WHEN attempts=3 THEN interval '30 seconds'
          ELSE interval '5 minutes' END
        WHERE request_id=:id AND state='CLAIMED' AND claim_id=:token
          AND claim_revision=:revision""",
        {"id": claim.request_id, "token": claim.claim_id, "revision": claim.revision},
    )
