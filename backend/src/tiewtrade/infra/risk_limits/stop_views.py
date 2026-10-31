"""Bounded stop snapshots with stable keyset pages at an immutable effect watermark."""

import base64
import json
from typing import Any
from uuid import UUID

from tiewtrade.core.orders import TradingMode
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.risk_limits.records import RiskConflictError


async def stop_summary(session: UserSession, mode: TradingMode) -> dict[str, Any] | None:
    checked = require_user_session(session)
    row = (
        (
            await checked.execute(
                """SELECT r.risk_revision,p.* FROM risk_stop_requests r
        JOIN risk_stop_progress p ON p.stop_id=r.id WHERE r.mode=:mode
        ORDER BY r.recorded_at DESC,r.id DESC LIMIT 1""",
                {"mode": mode.value},
            )
        )
        .mappings()
        .one_or_none()
    )
    return None if row is None else dict(row)


async def effect_page(
    session: UserSession,
    mode: TradingMode,
    stop_id: UUID,
    *,
    limit: int = 20,
    cursor: str | None = None,
    state_filter: str = "ALL",
) -> dict[str, Any] | None:
    checked = require_user_session(session)
    if (
        type(limit) is not int
        or not 1 <= limit <= 100
        or state_filter not in {"ALL", "PENDING", "FAILED"}
    ):
        raise RiskConflictError("invalid risk effects page")
    summary = (
        await checked.execute(
            """SELECT p.effects_revision FROM risk_stop_progress p
        WHERE p.stop_id=:stop AND p.mode=:mode""",
            {"stop": stop_id, "mode": mode.value},
        )
    ).one_or_none()
    if summary is None:
        return None
    watermark, last = int(summary.effects_revision), 0
    if cursor is not None:
        try:
            if len(cursor) > 512:
                raise ValueError
            value = json.loads(base64.urlsafe_b64decode(cursor.encode()))
            if type(value) is not list or len(value) != 7:
                raise ValueError
            owner, bound_mode, stop, watermark, last, bound_filter, order = value
            if any(type(item) is not str for item in (owner, bound_mode, stop, bound_filter)):
                raise ValueError
            if order != "TARGET_SEQUENCE_ASC_V1":
                raise ValueError
            if (UUID(owner), bound_mode, UUID(stop), bound_filter) != (
                checked.user_id,
                mode.value,
                stop_id,
                state_filter,
            ) or (
                type(watermark) is not int
                or type(last) is not int
                or not 0 < last <= 2**63 - 1
                or not 0 <= watermark <= summary.effects_revision
            ):
                raise ValueError
            anchor = (
                await checked.execute(
                    """SELECT 1 FROM risk_stop_targets t
                WHERE stop_id=:stop AND enrolled_sequence=:last
                AND EXISTS(SELECT 1 FROM risk_stop_effects e WHERE e.stop_id=t.stop_id
                  AND e.target_kind=t.target_kind AND e.target_id=t.target_id
                  AND sequence<=:watermark)""",
                    {"stop": stop_id, "last": last, "watermark": watermark},
                )
            ).first()
            if anchor is None:
                raise ValueError
        except (ValueError, TypeError, UnicodeError):
            raise RiskConflictError("invalid risk effects cursor") from None
    snapshot_at = (
        (
            await checked.execute(
                """SELECT coalesce((SELECT max(recorded_at) FROM risk_stop_effects
        WHERE stop_id=:stop AND sequence<=:watermark),r.recorded_at)
        FROM risk_stop_requests r WHERE r.id=:stop""",
                {"stop": stop_id, "watermark": watermark},
            )
        )
        .scalar_one()
        .isoformat()
    )
    rows = (
        (
            await checked.execute(
                """SELECT t.enrolled_sequence,t.target_kind,t.target_id,t.order_id,
          e.sequence,e.state,e.attempt,e.details,e.recorded_at
        FROM risk_stop_targets t JOIN LATERAL(
          SELECT * FROM risk_stop_effects e WHERE e.stop_id=t.stop_id
            AND e.target_kind=t.target_kind
            AND e.target_id=t.target_id AND e.sequence<=:watermark
          ORDER BY sequence DESC LIMIT 1) e ON true
        WHERE t.stop_id=:stop AND t.mode=:mode AND t.enrolled_sequence>:last
          AND (:filter='ALL' OR (:filter='FAILED' AND e.state='FAILED')
            OR (:filter='PENDING' AND e.state IN ('PENDING','CANCEL_PENDING','FAILED')))
        ORDER BY t.enrolled_sequence LIMIT :limit""",
                {
                    "stop": stop_id,
                    "mode": mode.value,
                    "watermark": watermark,
                    "last": last,
                    "filter": state_filter,
                    "limit": limit + 1,
                },
            )
        )
        .mappings()
        .all()
    )
    page = rows[:limit]
    token = None
    if len(rows) > limit:
        token = base64.urlsafe_b64encode(
            json.dumps(
                [
                    str(checked.user_id),
                    mode.value,
                    str(stop_id),
                    watermark,
                    int(page[-1]["enrolled_sequence"]),
                    state_filter,
                    "TARGET_SEQUENCE_ASC_V1",
                ],
                separators=(",", ":"),
            ).encode()
        ).decode()
    return {
        "stop_id": stop_id,
        "mode": mode.value,
        "effects_revision": watermark,
        "snapshot_at": snapshot_at,
        "next_cursor": token,
        "items": [
            {
                "target_kind": row["target_kind"],
                "target_id": row["target_id"],
                "order_id": row["order_id"],
                "state": row["state"],
                "attempt": row["attempt"],
                "details": row["details"],
                "recorded_at": row["recorded_at"].isoformat(),
            }
            for row in page
        ],
    }
