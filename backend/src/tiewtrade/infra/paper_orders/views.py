"""Read-only owner-scoped intake/command outcome snapshots and bounded discovery."""

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast
from uuid import UUID

from tiewtrade.core.orders import OrderConflictError
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.paper_orders.codec import object_payload
from tiewtrade.infra.paper_orders.requests import (
    ManualRequest,
    RequestIntegrityError,
    decode_request,
)


@dataclass(frozen=True, slots=True)
class RequestView:
    request: ManualRequest
    intake_state: Literal["PENDING", "TRANSFERRED", "REJECTED"]
    intake_failure_code: str | None
    command_id: UUID | None
    command_state: Literal["PENDING", "SUCCEEDED", "REJECTED"] | None
    command_failure_code: str | None
    command_snapshot: dict[str, Any] | None
    order_state: str | None
    snapshot_at: datetime


@dataclass(frozen=True, slots=True)
class RequestPage:
    requests: tuple[RequestView, ...]
    next_cursor: str | None


_JOIN = """SELECT i.*,r.state intake_state,r.failure_code intake_failure_code,r.command_id,
 c.id linked_command_id,cr.state command_state,cr.failure_code command_failure_code,
 cr.snapshot command_snapshot,p.status order_state,clock_timestamp() snapshot_at
 FROM paper_order_requests i
 LEFT JOIN paper_order_request_results r ON r.request_id=i.id
 LEFT JOIN paper_order_commands c ON c.id=r.command_id
 LEFT JOIN paper_order_command_results cr ON cr.command_id=c.id
 LEFT JOIN paper_order_projections p ON p.order_id=i.order_id
 """


def _view(row: Any) -> RequestView:
    state = cast(Literal["PENDING", "TRANSFERRED", "REJECTED"], row.intake_state or "PENDING")
    if state == "TRANSFERRED" and row.linked_command_id is None:
        raise RequestIntegrityError("transferred command is unavailable")
    return RequestView(
        decode_request(row),
        state,
        row.intake_failure_code,
        row.command_id,
        (row.command_state or "PENDING") if row.command_id is not None else None,
        row.command_failure_code,
        None if row.command_snapshot is None else object_payload(row.command_snapshot),
        row.order_state,
        row.snapshot_at,
    )


async def request_view(session: UserSession, request_id: UUID) -> RequestView | None:
    session = require_user_session(session)
    row = (await session.execute(_JOIN + " WHERE i.id=:id", {"id": request_id})).one_or_none()
    return None if row is None else _view(row)


def _cursor(owner: UUID, view: RequestView) -> str:
    data = [
        str(owner),
        "unresolved",
        view.request.recorded_at.isoformat(),
        str(view.request.request_id),
    ]
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()


def _read_cursor(value: str, owner: UUID) -> tuple[datetime, UUID]:
    try:
        if len(value) > 512:
            raise ValueError
        data = json.loads(base64.b64decode(value, altchars=b"-_", validate=True))
        if (
            not isinstance(data, list)
            or len(data) != 4
            or not all(isinstance(part, str) for part in data)
            or data[:2] != [str(owner), "unresolved"]
        ):
            raise ValueError
        timestamp, identity = datetime.fromisoformat(data[2]), UUID(data[3])
        if timestamp.tzinfo is None:
            raise ValueError
        return timestamp, identity
    except (TypeError, ValueError, UnicodeError) as error:
        raise OrderConflictError("invalid request cursor") from error


async def unresolved_requests(
    session: UserSession, *, cursor: str | None = None, limit: int = 20
) -> RequestPage:
    session = require_user_session(session)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise OrderConflictError("invalid request page size")
    params: dict[str, object] = {"owner": session.user_id, "limit": limit + 1}
    after = ""
    if cursor is not None:
        timestamp, identity = _read_cursor(cursor, session.user_id)
        params.update({"time": timestamp, "id": identity})
        after = " AND (i.recorded_at,i.id)>(:time,:id)"
    rows = (
        await session.execute(
            _JOIN
            + """ WHERE i.user_id=:owner AND (r.request_id IS NULL
          OR (r.state='TRANSFERRED' AND (c.id IS NULL OR cr.command_id IS NULL)))"""
            + after
            + " ORDER BY i.recorded_at,i.id LIMIT :limit",
            params,
        )
    ).all()
    views = tuple(_view(row) for row in rows[:limit])
    return RequestPage(views, _cursor(session.user_id, views[-1]) if len(rows) > limit else None)
