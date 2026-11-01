"""Immutable stop inbox, admission fences, and historical execution checks."""

import hashlib
import json
from typing import Any
from uuid import UUID, uuid4

from tiewtrade.core.orders import OrderOrigin, TradingMode
from tiewtrade.core.trading_stops import StopAction, StopCause
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.trading_stops.records import StopConflictError, StopReceipt


async def global_shared_lock(session: UserSession) -> None:
    checked = require_user_session(session)
    await checked.execute(
        "SELECT pg_advisory_xact_lock_shared(hashtextextended('trading-stop:global',0))"
    )


async def global_exclusive_lock(session: UserSession) -> None:
    checked = require_user_session(session)
    await checked.execute("SELECT pg_advisory_xact_lock(hashtextextended('trading-stop:global',0))")


async def admission_revisions(session: UserSession, mode: TradingMode) -> tuple[int, int]:
    checked = require_user_session(session)
    row = (
        await checked.execute(
            """SELECT
          coalesce(max(revision) FILTER(
            WHERE cause='PLATFORM' AND action='STOP'),0) global_revision,
          coalesce(max(revision) FILTER(WHERE scope_owner_id=:owner AND mode=:mode
            AND action='STOP'),0) owner_revision
        FROM trading_stop_requests""",
            {"owner": checked.user_id, "mode": mode.value},
        )
    ).one()
    return int(row.global_revision), int(row.owner_revision)


_ACTIVE = """WITH latest AS (
 SELECT DISTINCT ON (cause,coalesce(scope_owner_id,'00000000-0000-0000-0000-000000000000'::uuid),
   coalesce(mode,'PLATFORM')) id,cause,scope_owner_id,mode,revision
 FROM trading_stop_requests WHERE action='STOP'
 ORDER BY cause,coalesce(scope_owner_id,'00000000-0000-0000-0000-000000000000'::uuid),
   coalesce(mode,'PLATFORM'),revision DESC)
 SELECT cause,revision FROM latest s WHERE
   (s.cause='PLATFORM' OR (s.scope_owner_id=:owner AND s.mode=:mode))
   AND NOT EXISTS(SELECT 1 FROM trading_stop_requests r JOIN trading_stop_results x
     ON x.request_id=r.id AND x.state='APPLIED'
     WHERE r.action='RESUME' AND r.expected_stop_id=s.id)"""


async def current_opening_blocked(
    session: UserSession, mode: TradingMode, origin: OrderOrigin
) -> bool:
    checked = require_user_session(session)
    rows = await checked.execute(_ACTIVE, {"owner": checked.user_id, "mode": mode.value})
    return any(
        row.cause == "PLATFORM" or row.cause != "USER" or origin is OrderOrigin.BOT for row in rows
    )


async def opening_interrupted(
    session: UserSession,
    *,
    mode: TradingMode,
    origin: OrderOrigin,
    admitted_global_revision: int,
    admitted_owner_revision: int,
) -> bool:
    checked = require_user_session(session)
    historical = (
        await checked.execute(
            """SELECT 1 FROM trading_stop_requests WHERE action='STOP' AND
          ((cause='PLATFORM' AND revision>:global_revision) OR
           (scope_owner_id=:owner AND mode=:mode AND revision>:owner_revision)) LIMIT 1""",
            {
                "global_revision": admitted_global_revision,
                "owner_revision": admitted_owner_revision,
                "owner": checked.user_id,
                "mode": mode.value,
            },
        )
    ).first()
    return historical is not None or await current_opening_blocked(checked, mode, origin)


def _fingerprint(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _receipt(row: Any) -> StopReceipt:
    return StopReceipt(
        UUID(str(row.id)),
        UUID(str(row.user_id)),
        None if row.mode is None else TradingMode(str(row.mode)),
        StopAction(str(row.action)),
        StopCause(str(row.cause)),
        UUID(str(row.idempotency_key)),
        int(row.generation),
        int(row.revision),
        UUID(str(row.expected_stop_id or row.id)),
        row.recorded_at,
        str(row.state or "REQUEST_PENDING"),
        None if row.failure_code is None else str(row.failure_code),
    )


async def submit_request(
    session: UserSession,
    *,
    mode: TradingMode | None,
    action: StopAction,
    key: UUID,
    expected_stop_id: UUID | None = None,
    expected_revision: int | None = None,
    expected_summary_revision: int | None = None,
    expected_reconciliation_revision: int | None = None,
    reason_code: str,
    reason_text: str | None = None,
    platform: bool = False,
) -> StopReceipt:
    checked = require_user_session(session)
    payload: dict[str, object] = {
        "mode": None if mode is None else mode.value,
        "action": action.value,
        "expected_stop_id": None if expected_stop_id is None else str(expected_stop_id),
        "expected_revision": expected_revision,
        "expected_summary_revision": expected_summary_revision,
        "expected_reconciliation_revision": expected_reconciliation_revision,
        "reason_code": reason_code,
        "reason_text": reason_text,
        "platform": platform,
    }
    try:
        row = (
            await checked.execute(
                """SELECT r.*,x.state,x.failure_code FROM submit_trading_stop_request(
              :id,:owner,:mode,:action,:key,:fingerprint,:expected_stop,:expected_revision,
              :expected_summary,:expected_reconciliation,:reason_code,:reason_text,:platform) r
              LEFT JOIN trading_stop_results x ON x.request_id=r.id""",
                {
                    "id": uuid4(),
                    "owner": checked.user_id,
                    "mode": None if mode is None else mode.value,
                    "action": action.value,
                    "key": key,
                    "fingerprint": _fingerprint(payload),
                    "expected_stop": expected_stop_id,
                    "expected_revision": expected_revision,
                    "expected_summary": expected_summary_revision,
                    "expected_reconciliation": expected_reconciliation_revision,
                    "reason_code": reason_code,
                    "reason_text": reason_text,
                    "platform": platform,
                },
            )
        ).one()
    except Exception as error:
        if getattr(error, "code", None) == "DUPLICATE_VALUE":
            raise StopConflictError("stop idempotency conflict") from None
        raise
    return _receipt(row)


async def receipt_by_key(
    session: UserSession, *, mode: TradingMode | None, action: StopAction, key: UUID
) -> StopReceipt | None:
    checked = require_user_session(session)
    row = (
        await checked.execute(
            """SELECT r.*,x.state,x.failure_code FROM trading_stop_requests r
          LEFT JOIN trading_stop_results x ON x.request_id=r.id
          WHERE r.user_id=:owner AND r.action=:action
            AND coalesce(r.mode,'PLATFORM')=coalesce(:mode,'PLATFORM')
            AND r.idempotency_key=:key""",
            {
                "owner": checked.user_id,
                "action": action.value,
                "mode": None if mode is None else mode.value,
                "key": key,
            },
        )
    ).one_or_none()
    return None if row is None else _receipt(row)


async def receipt_by_id(session: UserSession, request_id: UUID) -> StopReceipt | None:
    checked = require_user_session(session)
    row = (
        await checked.execute(
            """SELECT r.*,x.state,x.failure_code FROM trading_stop_requests r
          LEFT JOIN trading_stop_results x ON x.request_id=r.id
          WHERE r.id=:id AND (r.user_id=:owner OR r.scope_owner_id=:owner)""",
            {"id": request_id, "owner": checked.user_id},
        )
    ).one_or_none()
    return None if row is None else _receipt(row)
