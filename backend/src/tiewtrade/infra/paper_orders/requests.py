"""Immutable owner-bound manual inbox. No financial state is written by API intake."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from tiewtrade.core.orders import OrderConflictError, OrderIntent, OrderOrigin, TradingMode
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.infra.audit import (
    ActorKind,
    AuditAction,
    AuditEvent,
    AuditMode,
    AuditOutcome,
    PaperOrderRequestDetails,
    SubjectKind,
    record_event,
)
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.market_data.order_book_codec import canonical
from tiewtrade.infra.paper_orders.codec import intent_from_payload, intent_payload, object_payload
from tiewtrade.infra.paper_orders.dispatch import lock_opening_pair_catalog

RequestAction = Literal["NEW", "CANCEL"]


class RequestEpisodeClosedError(OrderConflictError):
    code = "MANUAL_ORDER_EPISODE_CLOSED"


class RequestIntegrityError(OrderConflictError):
    code = "ORDER_REQUEST_INTEGRITY"


@dataclass(frozen=True, slots=True)
class ManualRequest:
    request_id: UUID
    user_id: UUID
    wallet_id: UUID
    episode_id: UUID
    order_id: UUID
    action: RequestAction
    idempotency_key: UUID
    fingerprint: str
    admitted_catalog_revision: int | None
    payload: dict[str, Any]
    recorded_at: datetime


def decode_request(row: Any) -> ManualRequest:
    if row.action not in ("NEW", "CANCEL"):
        raise RequestIntegrityError("invalid stored request action")
    request = ManualRequest(
        UUID(str(row.id)),
        UUID(str(row.user_id)),
        UUID(str(row.wallet_id)),
        UUID(str(row.episode_id)),
        UUID(str(row.order_id)),
        row.action,
        UUID(str(row.idempotency_key)),
        row.request_fingerprint,
        row.admitted_catalog_revision,
        object_payload(row.payload),
        row.recorded_at,
    )

    if request.action == "NEW":
        intent = intent_from_payload(request.payload)
        if (
            intent.order_id != request.order_id
            or intent.idempotency_key != request.idempotency_key
            or intent.scope.owner_id != request.user_id
            or intent.scope.episode_id != request.episode_id
            or intent.origin is not OrderOrigin.MANUAL
            or intent.scope.mode is not TradingMode.PAPER
        ):
            raise RequestIntegrityError("stored request identity mismatch")
    if request.fingerprint != _fingerprint(
        request.wallet_id, request.episode_id, request.action, request.payload
    ):
        raise RequestIntegrityError("stored request fingerprint mismatch")
    return request


def _fingerprint(
    wallet_id: UUID, episode_id: UUID, action: RequestAction, payload: dict[str, object]
) -> str:
    normalized = dict(payload)
    if action == "NEW":
        normalized.pop("order_id", None)
    return hashlib.sha256(
        canonical(
            {
                "wallet": str(wallet_id),
                "episode": str(episode_id),
                "action": action,
                "payload": normalized,
            }
        ).encode()
    ).hexdigest()


async def wallet_lock(session: UserSession) -> None:
    session = require_user_session(session)
    await session.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(:key,0))",
        {"key": f"paper-wallet:{session.user_id}"},
    )


async def get_request(session: UserSession, request_id: UUID) -> ManualRequest | None:
    session = require_user_session(session)
    row = (
        await session.execute("SELECT * FROM paper_order_requests WHERE id=:id", {"id": request_id})
    ).one_or_none()
    return None if row is None else decode_request(row)


async def get_request_by_key(
    session: UserSession, *, action: RequestAction, key: UUID
) -> ManualRequest | None:
    session = require_user_session(session)
    if action not in ("NEW", "CANCEL"):
        raise OrderConflictError("invalid request action")
    row = (
        await session.execute(
            """SELECT * FROM paper_order_requests WHERE user_id=:owner
            AND action=:action AND idempotency_key=:key""",
            {"owner": session.user_id, "action": action, "key": key},
        )
    ).one_or_none()
    return None if row is None else decode_request(row)


async def request_audit(
    session: UserSession,
    request: ManualRequest,
    *,
    action: AuditAction,
    command_id: UUID | None = None,
    failure_code: str | None = None,
) -> None:
    received = action is AuditAction.PAPER_ORDER_REQUESTED
    await record_event(
        session,
        AuditEvent(
            owner_user_id=session.user_id,
            actor_kind=ActorKind.USER if received else ActorKind.SYSTEM,
            actor_id=session.user_id if received else None,
            action=action,
            subject_kind=SubjectKind.PAPER_ORDER_ACTIVITY,
            subject_id=str(request.episode_id),
            mode=AuditMode.PAPER,
            outcome=AuditOutcome.REJECTED if failure_code is not None else AuditOutcome.SUCCEEDED,
            failure_code=failure_code,
            details=PaperOrderRequestDetails(
                request.request_id,
                request.episode_id,
                request.action,
                None if command_id is None else UUID(str(command_id)),
            ),
        ),
    )


async def _admit(
    session: UserSession,
    *,
    wallet_id: UUID,
    episode_id: UUID,
    order_id: UUID,
    key: UUID,
    action: RequestAction,
    payload: dict[str, object],
    intent: OrderIntent | None,
) -> ManualRequest:
    session = require_user_session(session)
    fingerprint = _fingerprint(wallet_id, episode_id, action, payload)
    await wallet_lock(session)
    previous = await get_request_by_key(session, action=action, key=key)
    if previous is not None:
        if previous.fingerprint != fingerprint:
            raise OrderConflictError("manual request idempotency conflict")
        return previous
    active = (
        await session.execute(
            """SELECT 1 FROM paper_wallet_state s WHERE s.wallet_id=:wallet AND s.user_id=:owner
        AND s.active_episode_id=:episode AND NOT EXISTS(
          SELECT 1 FROM paper_wallet_episode_closures c WHERE c.episode_id=:episode)""",
            {"wallet": wallet_id, "owner": session.user_id, "episode": episode_id},
        )
    ).first()
    if active is None:
        await _reject_closed_episode(session, wallet_id=wallet_id, episode_id=episode_id)
        raise OrderConflictError("Paper episode is not active")
    revision = None
    if intent is not None and intent.side is ExecutionSide.BUY:
        revision = await lock_opening_pair_catalog(session, intent.pair)
    if action == "CANCEL":
        owned = (
            await session.execute(
                """SELECT id FROM paper_orders WHERE id=:order AND episode_id=:episode
                AND wallet_id=:wallet""",
                {"order": order_id, "episode": episode_id, "wallet": wallet_id},
            )
        ).first()
        if owned is None:
            raise OrderConflictError("cancel order is unavailable")
    row = (
        await session.execute(
            """INSERT INTO paper_order_requests
        (id,user_id,wallet_id,episode_id,order_id,action,idempotency_key,
         request_fingerprint,admitted_catalog_revision,payload)
        VALUES(:id,:owner,:wallet,:episode,:order,:action,:key,:fingerprint,
               :revision,CAST(:payload AS jsonb)) RETURNING *""",
            {
                "id": uuid4(),
                "owner": session.user_id,
                "wallet": wallet_id,
                "episode": episode_id,
                "order": order_id,
                "action": action,
                "key": key,
                "fingerprint": fingerprint,
                "revision": revision,
                "payload": canonical(payload),
            },
        )
    ).one()
    request = decode_request(row)
    await session.execute(
        """INSERT INTO paper_order_request_dispatch(request_id,user_id,episode_id)
        VALUES(:id,:owner,:episode)""",
        {"id": request.request_id, "owner": session.user_id, "episode": episode_id},
    )
    await request_audit(session, request, action=AuditAction.PAPER_ORDER_REQUESTED)
    return request


async def admit_new_request(
    session: UserSession, *, wallet_id: UUID, intent: OrderIntent
) -> ManualRequest:
    session = require_user_session(session)
    if (
        intent.scope.owner_id != session.user_id
        or intent.scope.mode is not TradingMode.PAPER
        or intent.origin is not OrderOrigin.MANUAL
    ):
        raise OrderConflictError("manual request owner/mode/origin mismatch")
    return await _admit(
        session,
        wallet_id=wallet_id,
        episode_id=intent.scope.episode_id,
        order_id=intent.order_id,
        key=intent.idempotency_key,
        action="NEW",
        payload=intent_payload(intent),
        intent=intent,
    )


async def admit_cancel_request(
    session: UserSession,
    *,
    wallet_id: UUID,
    episode_id: UUID,
    order_id: UUID,
    idempotency_key: UUID,
) -> ManualRequest:
    return await _admit(
        session,
        wallet_id=wallet_id,
        episode_id=episode_id,
        order_id=order_id,
        key=idempotency_key,
        action="CANCEL",
        payload={"order_id": str(order_id)},
        intent=None,
    )


async def _reject_closed_episode(
    session: UserSession, *, wallet_id: UUID, episode_id: UUID
) -> None:
    """Called only after same-key replay under wallet_lock.

    An immutable owner-bound closure proves this scope can never accept this
    absent request, even after a lost response/reload. Generic conflicts do not.
    """
    closed = (
        await session.execute(
            """SELECT 1 FROM paper_wallet_episode_closures c
            JOIN paper_wallet_episodes e ON e.id=c.episode_id
            WHERE e.id=:episode AND e.wallet_id=:wallet AND e.user_id=:owner""",
            {"episode": episode_id, "wallet": wallet_id, "owner": session.user_id},
        )
    ).first()
    if closed is not None:
        raise RequestEpisodeClosedError("manual request episode is permanently closed")


async def inspect_new_request(
    session: UserSession, *, wallet_id: UUID, intent: OrderIntent
) -> ManualRequest | None:
    session = require_user_session(session)
    await wallet_lock(session)
    previous = await get_request_by_key(session, action="NEW", key=intent.idempotency_key)
    if previous is not None and previous.fingerprint != _fingerprint(
        wallet_id, intent.scope.episode_id, "NEW", intent_payload(intent)
    ):
        raise OrderConflictError("manual request idempotency conflict")
    if previous is None:
        await _reject_closed_episode(
            session, wallet_id=wallet_id, episode_id=intent.scope.episode_id
        )
    return previous


async def inspect_cancel_request(
    session: UserSession, *, wallet_id: UUID, episode_id: UUID, order_id: UUID, key: UUID
) -> ManualRequest | None:
    session = require_user_session(session)
    await wallet_lock(session)
    previous = await get_request_by_key(session, action="CANCEL", key=key)
    if previous is not None and previous.fingerprint != _fingerprint(
        wallet_id, episode_id, "CANCEL", {"order_id": str(order_id)}
    ):
        raise OrderConflictError("manual request idempotency conflict")
    if previous is None:
        await _reject_closed_episode(session, wallet_id=wallet_id, episode_id=episode_id)
    return previous
