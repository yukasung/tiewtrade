"""Durable start-request inbox and receipt recovery for F-20."""

import hashlib
import json
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from tiewtrade.core.orders import TradingMode
from tiewtrade.infra.db.session import UserSession, require_user_session


class BotRequestConflictError(ValueError):
    """The key already identifies a different request in this scope."""


@dataclass(frozen=True, slots=True)
class BotReceipt:
    request_id: UUID
    mode: TradingMode
    key: UUID
    run_id: UUID | None
    failure_code: str | None

    @property
    def pending(self) -> bool:
        return self.run_id is None and self.failure_code is None


async def _lookup(
    session: UserSession,
    mode: TradingMode,
    identity: UUID,
    *,
    by: Literal["id", "idempotency_key"],
) -> tuple[BotReceipt, str] | None:
    checked = require_user_session(session)
    predicate = "r.id=:identity" if by == "id" else "r.idempotency_key=:identity"
    row = (
        await checked.execute(
            f"""SELECT r.id,r.idempotency_key,r.fingerprint,x.run_id,x.failure_code
              FROM bot_control_requests r LEFT JOIN bot_control_results x
                ON (x.request_id,x.user_id,x.mode)=(r.id,r.user_id,r.mode)
              WHERE r.user_id=:owner AND r.mode=:mode AND {predicate}""",
            {"owner": checked.user_id, "mode": mode.value, "identity": identity},
        )
    ).one_or_none()
    if row is None:
        return None
    return (
        BotReceipt(row.id, mode, row.idempotency_key, row.run_id, row.failure_code),
        str(row.fingerprint),
    )


async def receipt_by_id(
    session: UserSession, mode: TradingMode, request_id: UUID
) -> BotReceipt | None:
    result = await _lookup(session, mode, request_id, by="id")
    return None if result is None else result[0]


async def receipt_by_key(session: UserSession, mode: TradingMode, key: UUID) -> BotReceipt | None:
    result = await _lookup(session, mode, key, by="idempotency_key")
    return None if result is None else result[0]


async def submit_start(
    session: UserSession,
    *,
    mode: TradingMode,
    request_id: UUID,
    key: UUID,
    payload: dict[str, object],
) -> BotReceipt:
    """Persist an already validated request in the caller's write transaction."""
    checked = require_user_session(session)
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    fingerprint = hashlib.sha256(body.encode()).hexdigest()
    await checked.execute(
        """INSERT INTO bot_control_requests(id,user_id,mode,idempotency_key,fingerprint,payload)
        VALUES(:id,:owner,:mode,:key,:fingerprint,CAST(:body AS jsonb))
        ON CONFLICT (user_id,mode,idempotency_key) DO NOTHING""",
        {
            "id": request_id,
            "owner": checked.user_id,
            "mode": mode.value,
            "key": key,
            "fingerprint": fingerprint,
            "body": body,
        },
    )
    # A separate statement observes a conflicting insert after its commit.
    existing = await _lookup(checked, mode, key, by="idempotency_key")
    if existing is None or existing[1] != fingerprint:
        raise BotRequestConflictError("start request conflicts with existing key")
    return existing[0]
