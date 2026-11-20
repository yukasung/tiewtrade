"""Bounded ownership hints and fenced control-request leases."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from tiewtrade.core.orders import TradingMode
from tiewtrade.infra.db.session import ScanSession, UserSession, require_user_session
from tiewtrade.infra.risk_limits.dispatch import lock_risk_owner
from tiewtrade.infra.trading_stops.storage import global_shared_lock


class BotClaimLostError(ValueError):
    """The worker no longer owns the control request."""


@dataclass(frozen=True, slots=True)
class BotRequestHint:
    request_id: UUID
    user_id: UUID
    mode: TradingMode


@dataclass(frozen=True, slots=True)
class BotRequestClaim:
    hint: BotRequestHint
    token: UUID
    revision: int


async def due_controls(session: ScanSession, *, limit: int = 20) -> tuple[BotRequestHint, ...]:
    if not isinstance(session, ScanSession) or type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("bounded scan session required")
    rows = (
        await session.execute(
            """WITH ranked AS (
              SELECT r.id,r.user_id,r.mode,r.requested_at,
                row_number() OVER (PARTITION BY r.user_id ORDER BY r.requested_at,r.id) AS rank
              FROM bot_control_requests r
              LEFT JOIN bot_control_results x ON x.request_id=r.id
              LEFT JOIN bot_control_dispatch d ON d.request_id=r.id
              WHERE x.request_id IS NULL
                AND (d.request_id IS NULL OR d.lease_until<=clock_timestamp()))
              SELECT id,user_id,mode FROM ranked WHERE rank=1
              ORDER BY requested_at,id LIMIT :limit""",
            {"limit": limit},
        )
    ).all()
    return tuple(BotRequestHint(row.id, row.user_id, TradingMode(row.mode)) for row in rows)


def _claim_params(hint: BotRequestHint, token: UUID) -> dict[str, object]:
    return {"id": hint.request_id, "owner": hint.user_id, "mode": hint.mode.value, "token": token}


async def _lock(session: UserSession, hint: BotRequestHint) -> None:
    if require_user_session(session).user_id != hint.user_id:
        raise BotClaimLostError("control claim scope mismatch")
    await global_shared_lock(session)
    await lock_risk_owner(session, hint.mode)


async def claim_control(session: UserSession, hint: BotRequestHint) -> BotRequestClaim | None:
    await _lock(session, hint)
    token = uuid4()
    row = (
        await session.execute(
            """INSERT INTO bot_control_dispatch
              (request_id,user_id,mode,claim_id,claim_revision,lease_until)
              SELECT r.id,r.user_id,r.mode,:token,1,clock_timestamp()+interval '30 seconds'
              FROM bot_control_requests r WHERE r.id=:id AND r.user_id=:owner AND r.mode=:mode
                AND NOT EXISTS (SELECT 1 FROM bot_control_results x WHERE x.request_id=r.id)
                AND NOT EXISTS (
                  SELECT 1 FROM bot_control_dispatch b
                  WHERE b.user_id=:owner AND b.mode=:mode AND b.lease_until>clock_timestamp()
                    AND NOT EXISTS (
                      SELECT 1 FROM bot_control_results x WHERE x.request_id=b.request_id))
              ON CONFLICT(request_id) DO UPDATE SET claim_id=EXCLUDED.claim_id,
                claim_revision=bot_control_dispatch.claim_revision+1,
                lease_until=EXCLUDED.lease_until
              WHERE bot_control_dispatch.lease_until<=clock_timestamp()
              RETURNING claim_revision""",
            _claim_params(hint, token),
        )
    ).one_or_none()
    return None if row is None else BotRequestClaim(hint, token, row.claim_revision)


async def require_control_claim(session: UserSession, claim: BotRequestClaim) -> None:
    await _lock(session, claim.hint)
    row = (
        await session.execute(
            """SELECT 1 FROM bot_control_dispatch d WHERE request_id=:id
              AND user_id=:owner AND mode=:mode AND claim_id=:token AND claim_revision=:revision
              AND lease_until>clock_timestamp()
              AND NOT EXISTS (SELECT 1 FROM bot_control_results x WHERE x.request_id=d.request_id)
              FOR UPDATE""",
            {**_claim_params(claim.hint, claim.token), "revision": claim.revision},
        )
    ).first()
    if row is None:
        raise BotClaimLostError("control claim expired, completed or replaced")


async def finish_control(
    session: UserSession,
    claim: BotRequestClaim,
    *,
    run_id: UUID | None = None,
    failure_code: str | None = None,
) -> None:
    if (run_id is None) == (failure_code is None):
        raise ValueError("provide exactly one control outcome")
    await require_control_claim(session, claim)
    await session.execute(
        """INSERT INTO bot_control_results(request_id,user_id,mode,run_id,failure_code)
          VALUES(:id,:owner,:mode,:run,:failure)""",
        {**_claim_params(claim.hint, claim.token), "run": run_id, "failure": failure_code},
    )
