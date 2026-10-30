"""Bounded owner-fair claims; stale workers cannot finalize risk requests."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from tiewtrade.core.orders import TradingMode
from tiewtrade.infra.db.session import ScanSession, UserSession, require_user_session
from tiewtrade.infra.risk_limits.records import RiskConflictError


class RiskClaimLostError(RiskConflictError):
    code = "RISK_CLAIM_LOST"


@dataclass(frozen=True, slots=True)
class DueRiskRequest:
    request_id: UUID
    user_id: UUID
    mode: TradingMode


@dataclass(frozen=True, slots=True)
class RiskClaim:
    due: DueRiskRequest
    claim_id: UUID
    revision: int


async def lock_risk_owner(
    session: UserSession,
    mode: TradingMode,
    *,
    lock_timeout_ms: int | None = None,
    statement_timeout_ms: int | None = None,
) -> None:
    checked = require_user_session(session)
    prefix = "paper-wallet:" if mode is TradingMode.PAPER else "risk-live:"
    key = prefix + str(checked.user_id)
    if lock_timeout_ms is None and statement_timeout_ms is None:
        await checked.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(:key,0))", {"key": key}
        )
        return
    if (
        type(lock_timeout_ms) is not int
        or type(statement_timeout_ms) is not int
        or lock_timeout_ms <= 0
        or statement_timeout_ms <= 0
    ):
        raise ValueError("paired positive transaction timeouts required")
    # Materialize volatile configuration before waiting for the SAME owner lock.
    # Read owner data in the caller's NEXT statement, after any lock wait.
    await checked.execute(
        """WITH configured AS MATERIALIZED (
          SELECT set_config('lock_timeout',:lock_timeout,true),
            set_config('statement_timeout',:statement_timeout,true)
        ) SELECT pg_advisory_xact_lock(hashtextextended(:key,0)) FROM configured""",
        {
            "key": key,
            "lock_timeout": f"{lock_timeout_ms}ms",
            "statement_timeout": f"{statement_timeout_ms}ms",
        },
    )


async def due_requests(scan: ScanSession, *, limit: int = 20) -> tuple[DueRiskRequest, ...]:
    if not isinstance(scan, ScanSession) or type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("bounded risk scanner required")
    rows = await scan.execute(
        """WITH busy AS MATERIALIZED(
          SELECT DISTINCT user_id FROM risk_limit_dispatch
          WHERE state='CLAIMED' AND lease_until>clock_timestamp()), candidates AS (
          SELECT request_id,user_id,mode,next_attempt_at,
            row_number() OVER(PARTITION BY user_id ORDER BY next_attempt_at,request_id) AS rank
          FROM risk_limit_dispatch d WHERE d.state<>'TERMINAL'
            AND d.next_attempt_at<=clock_timestamp()
            AND (d.lease_until IS NULL OR d.lease_until<=clock_timestamp())
            AND NOT EXISTS(SELECT 1 FROM busy b WHERE b.user_id=d.user_id))
          SELECT request_id,user_id,mode FROM candidates WHERE rank=1
          ORDER BY next_attempt_at,request_id LIMIT :limit""",
        {"limit": limit},
    )
    return tuple(
        DueRiskRequest(UUID(str(r.request_id)), UUID(str(r.user_id)), TradingMode(r.mode))
        for r in rows
    )


async def claim_request(
    session: UserSession, due: DueRiskRequest, *, worker: str
) -> RiskClaim | None:
    checked = require_user_session(session)
    if due.user_id != checked.user_id or not 1 <= len(worker) <= 128:
        raise RiskClaimLostError("invalid risk claim owner or worker")
    await lock_risk_owner(checked, due.mode)
    claim_id = uuid4()
    row = (
        await checked.execute(
            """UPDATE risk_limit_dispatch SET state='CLAIMED',worker=:worker,
              claim_id=:claim,claim_revision=claim_revision+1,
              lease_until=clock_timestamp()+interval '30 seconds',attempts=attempts+1
            WHERE request_id=:id AND user_id=:owner AND mode=:mode AND state<>'TERMINAL'
              AND next_attempt_at<=clock_timestamp()
              AND (lease_until IS NULL OR lease_until<=clock_timestamp())
            RETURNING claim_revision""",
            {
                "worker": worker,
                "claim": claim_id,
                "id": due.request_id,
                "owner": checked.user_id,
                "mode": due.mode.value,
            },
        )
    ).scalar_one_or_none()
    return None if row is None else RiskClaim(due, claim_id, int(row))


async def require_claim(session: UserSession, claim: RiskClaim) -> None:
    checked = require_user_session(session)
    if checked.user_id != claim.due.user_id:
        raise RiskClaimLostError("risk claim owner mismatch")
    await lock_risk_owner(checked, claim.due.mode)
    row = (
        await checked.execute(
            """SELECT 1 FROM risk_limit_dispatch WHERE request_id=:id AND user_id=:owner
              AND mode=:mode
              AND state='CLAIMED' AND claim_id=:claim AND claim_revision=:revision
              AND lease_until>clock_timestamp() FOR UPDATE""",
            {
                "id": claim.due.request_id,
                "owner": checked.user_id,
                "claim": claim.claim_id,
                "revision": claim.revision,
                "mode": claim.due.mode.value,
            },
        )
    ).first()
    if row is None:
        raise RiskClaimLostError("risk request claim expired or replaced")


async def finish_claim(session: UserSession, claim: RiskClaim, *, deferred: bool = False) -> None:
    await require_claim(session, claim)
    await session.execute(
        """UPDATE risk_limit_dispatch SET state=:state,worker=NULL,claim_id=NULL,lease_until=NULL,
          next_attempt_at=CASE WHEN :deferred THEN clock_timestamp()+
            interval '100 milliseconds'*(1<<least(attempts,8)) ELSE next_attempt_at END
          WHERE request_id=:id AND claim_id=:claim AND claim_revision=:revision""",
        {
            "id": claim.due.request_id,
            "claim": claim.claim_id,
            "revision": claim.revision,
            "state": "PENDING" if deferred else "TERMINAL",
            "deferred": deferred,
        },
    )
