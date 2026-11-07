"""Owner-locked protection state and append-only facts. Caller owns commit."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4, uuid5

from tiewtrade.core.money import Quantity
from tiewtrade.core.orders import OrderConflictError, OrderScope, TradingMode
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.protections import Protection, available_quantity
from tiewtrade.infra.audit import (
    ActorKind,
    AuditAction,
    AuditEvent,
    AuditMode,
    AuditOutcome,
    SubjectKind,
    record_event,
)
from tiewtrade.infra.audit.events import ProtectionDetails
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.market_data.order_book_codec import canonical
from tiewtrade.infra.paper_orders.requests import (
    RequestEpisodeClosedError,
    _reject_closed_episode,
    wallet_lock,
)
from tiewtrade.infra.paper_orders.storage import lock_active_episode
from tiewtrade.infra.positions.views import held_and_reserved
from tiewtrade.infra.protections.codec import decode, encode


class ProtectionEpisodeClosedError(OrderConflictError):
    code = "PROTECTION_EPISODE_CLOSED"


@dataclass(frozen=True, slots=True)
class StoredProtection:
    value: Protection
    wallet_id: UUID
    acquired: Quantity
    disposed: Quantity
    extra_exit: Quantity
    failure_code: str | None
    next_attempt_at: datetime
    observation: tuple[UUID, int, int] | None


def stored(row: Any) -> StoredProtection:
    value = decode(row.document)
    if value.scope.owner_id != row.user_id or value.protection_id != row.id:
        raise OrderConflictError("protection document scope differs from storage")
    return StoredProtection(
        value,
        row.wallet_id,
        Quantity.of(row.acquired, row.base),
        Quantity.of(row.disposed, row.base),
        Quantity.of(row.extra_exit, row.base),
        row.failure_code,
        row.next_attempt_at,
        None
        if row.observed_source is None
        else (
            UUID(str(row.observed_source)),
            int(row.observed_generation),
            int(row.observed_sequence),
        ),
    )


async def enabled(session: UserSession) -> bool:
    require_user_session(session)
    return bool(
        (
            await session.execute("SELECT enabled FROM paper_protection_protocol WHERE singleton")
        ).scalar_one()
    )


async def lock_scope(session: UserSession, wallet_id: UUID, episode_id: UUID) -> None:
    require_user_session(session)
    await wallet_lock(session)
    await lock_active_episode(session, wallet_id, episode_id)


async def audit(
    session: UserSession,
    *,
    value: Protection | None,
    episode_id: UUID,
    protection_id: UUID,
    event_id: UUID,
    kind: str,
) -> None:
    requested = kind == "REQUEST"
    await record_event(
        session,
        AuditEvent(
            owner_user_id=session.user_id,
            action=AuditAction.PROTECTION_EVENT,
            actor_kind=ActorKind.USER if requested else ActorKind.SYSTEM,
            actor_id=session.user_id if requested else None,
            subject_kind=SubjectKind.PAPER_ORDER_ACTIVITY,
            subject_id=str(episode_id),
            outcome=AuditOutcome.SUCCEEDED,
            mode=AuditMode.PAPER,
            details=ProtectionDetails(
                episode_id, protection_id, event_id, 0 if value is None else value.revision, kind
            ),
        ),
    )


async def load(session: UserSession, protection_id: UUID) -> StoredProtection | None:
    require_user_session(session)
    row = (
        await session.execute("SELECT * FROM paper_protections WHERE id=:id", {"id": protection_id})
    ).one_or_none()
    return None if row is None else stored(row)


async def groups(
    session: UserSession, episode_id: UUID, pair: PositionPair, *, include_closed: bool = False
) -> tuple[StoredProtection, ...]:
    require_user_session(session)
    rows = (
        await session.execute(
            """SELECT * FROM paper_protections
        WHERE episode_id=:episode AND base=:base AND quote=:quote
        AND state<>'CANCELED' AND (:closed OR state<>'CLOSED') ORDER BY created_at,id""",
            {
                "episode": episode_id,
                "base": pair.base,
                "quote": pair.quote,
                "closed": include_closed,
            },
        )
    ).all()
    return tuple(stored(r) for r in rows)


async def create(
    session: UserSession,
    value: Protection,
    wallet_id: UUID,
    *,
    entry_request_id: UUID | None = None,
) -> StoredProtection:
    if value.scope != OrderScope(
        UUID(str(session.user_id)), value.scope.episode_id, TradingMode.PAPER
    ):
        raise OrderConflictError("Paper protection scope required")
    await lock_scope(session, wallet_id, value.scope.episode_id)
    await session.execute(
        """INSERT INTO paper_protections
        (id,user_id,wallet_id,episode_id,base,quote,state,revision,quantity,document,
         entry_request_id,entry_order_id)
        VALUES(:id,:owner,:wallet,:episode,:base,:quote,:state,:revision,
               :quantity,CAST(:document AS jsonb),:request,:entry)""",
        {
            "id": value.protection_id,
            "owner": session.user_id,
            "wallet": wallet_id,
            "episode": value.scope.episode_id,
            "base": value.prices.pair.base,
            "quote": value.prices.pair.quote,
            "state": value.state.value,
            "revision": value.revision,
            "quantity": value.quantity.as_parts()["quantity"],
            "document": canonical(encode(value)),
            "request": entry_request_id,
            "entry": value.entry_order_id,
        },
    )
    await event(session, value, "CREATE")
    result = await load(session, value.protection_id)
    assert result is not None
    return result


async def event(session: UserSession, value: Protection, kind: str) -> None:
    event_id = uuid5(value.protection_id, f"revision:{value.revision}")
    await session.execute(
        """INSERT INTO paper_protection_events
        (id,user_id,episode_id,protection_id,revision,kind,document)
        VALUES(:id,:owner,:episode,:group,:revision,:kind,CAST(:document AS jsonb))""",
        {
            "id": event_id,
            "owner": session.user_id,
            "episode": value.scope.episode_id,
            "group": value.protection_id,
            "revision": value.revision,
            "kind": kind,
            "document": canonical(encode(value)),
        },
    )
    await audit(
        session,
        value=value,
        episode_id=value.scope.episode_id,
        protection_id=value.protection_id,
        event_id=event_id,
        kind=kind,
    )


async def save(
    session: UserSession,
    before: StoredProtection,
    value: Protection,
    *,
    kind: str,
    acquired: Quantity | None = None,
    disposed: Quantity | None = None,
    extra_exit: Quantity | None = None,
    failure_code: str | None = None,
) -> StoredProtection:
    if (
        value.protection_id != before.value.protection_id
        or value.scope != before.value.scope
        or value.revision != before.value.revision + 1
    ):
        raise OrderConflictError("protection update identity/revision differs")
    result = await session.execute(
        """UPDATE paper_protections SET state=:state,revision=:revision,
        quantity=:quantity,document=CAST(:document AS jsonb),acquired=:acquired,disposed=:disposed,
        extra_exit=:extra,failure_code=:failure,next_attempt_at=clock_timestamp()
        WHERE id=:id AND revision=:expected RETURNING id""",
        {
            "id": value.protection_id,
            "expected": before.value.revision,
            "state": value.state.value,
            "revision": value.revision,
            "quantity": value.quantity.as_parts()["quantity"],
            "document": canonical(encode(value)),
            "acquired": (before.acquired if acquired is None else acquired).as_parts()["quantity"],
            "disposed": (before.disposed if disposed is None else disposed).as_parts()["quantity"],
            "extra": (before.extra_exit if extra_exit is None else extra_exit).as_parts()[
                "quantity"
            ],
            "failure": failure_code,
        },
    )
    if result.scalar_one_or_none() is None:
        raise OrderConflictError("protection revision changed")
    await event(session, value, kind)
    current = await load(session, value.protection_id)
    assert current is not None
    return current


async def allocated(session: UserSession, episode_id: UUID, pair: PositionPair) -> Quantity:
    """An admitted exit reserves its remainder in F-15; don't count it twice."""
    rows = (
        await session.execute(
            """SELECT p.quantity,p.state,
       coalesce((SELECT sum(r.base_reserved) FROM paper_protection_exits x
         JOIN paper_reservations r ON r.order_id=x.order_id
         JOIN paper_protection_exit_progress s ON s.id=x.id
         WHERE x.protection_id=p.id AND NOT s.settled),0) AS reserved
       FROM paper_protections p WHERE p.episode_id=:episode AND p.base=:base AND p.quote=:quote
         AND p.state NOT IN ('CLOSED','CANCELED')""",
            {"episode": episode_id, "base": pair.base, "quote": pair.quote},
        )
    ).all()
    total = Quantity.of(0, pair.base)
    for row in rows:
        quantity = Quantity.of(row.quantity, pair.base)
        reserved = Quantity.of(row.reserved, pair.base)
        if reserved > quantity:
            raise OrderConflictError("exit reservation exceeds remaining protection")
        total += quantity - reserved
    return total


async def free_quantity(session: UserSession, episode_id: UUID, pair: PositionPair) -> Quantity:
    held, reserved = await held_and_reserved(session, episode_id, pair)
    return available_quantity(
        held=held, reserved=reserved, allocations=(await allocated(session, episode_id, pair),)
    )


async def admit_request(
    session: UserSession,
    *,
    wallet_id: UUID,
    episode_id: UUID,
    action: str,
    key: UUID,
    protection_id: UUID | None,
    payload: dict[str, object],
) -> UUID:
    require_user_session(session)
    if action not in ("CREATE", "REPLACE", "CANCEL"):
        raise OrderConflictError("unsupported protection action")
    await wallet_lock(session)
    fingerprint = hashlib.sha256(
        canonical(
            {
                "wallet": str(wallet_id),
                "episode": str(episode_id),
                "action": action,
                "target": None if action == "CREATE" else str(protection_id),
                "payload": payload,
            }
        ).encode()
    ).hexdigest()
    previous = (
        await session.execute(
            """SELECT id,fingerprint FROM paper_protection_requests
       WHERE user_id=:owner AND action=:action AND idempotency_key=:key""",
            {"owner": session.user_id, "action": action, "key": key},
        )
    ).one_or_none()
    if previous is not None:
        if previous.fingerprint != fingerprint:
            raise OrderConflictError("protection idempotency conflict")
        return UUID(str(previous.id))
    active = (
        await session.execute(
            """SELECT 1 FROM paper_wallet_state s
        WHERE s.wallet_id=:wallet AND s.active_episode_id=:episode
        AND NOT EXISTS(SELECT 1 FROM paper_wallet_episode_closures c
                       WHERE c.episode_id=:episode)""",
            {"wallet": wallet_id, "episode": episode_id},
        )
    ).first()
    if active is None:
        try:
            await _reject_closed_episode(session, wallet_id=wallet_id, episode_id=episode_id)
        except RequestEpisodeClosedError:
            raise ProtectionEpisodeClosedError("Paper episode is permanently closed") from None
        raise OrderConflictError("Paper episode unavailable")
    if action != "CANCEL" and not await enabled(session):
        raise OrderConflictError("protection protocol unavailable")
    if action != "CREATE":
        current = await load(session, protection_id) if protection_id is not None else None
        if current is None or current.value.scope.episode_id != episode_id:
            raise OrderConflictError("protection is unavailable")
    group_id = uuid4() if action == "CREATE" else protection_id
    assert group_id is not None
    request_id = uuid4()
    await session.execute(
        """INSERT INTO paper_protection_requests
        (id,user_id,wallet_id,episode_id,protection_id,action,idempotency_key,fingerprint,payload)
        VALUES(:id,:owner,:wallet,:episode,:group,:action,:key,:fp,CAST(:payload AS jsonb))""",
        {
            "id": request_id,
            "owner": session.user_id,
            "wallet": wallet_id,
            "episode": episode_id,
            "group": group_id,
            "action": action,
            "key": key,
            "fp": fingerprint,
            "payload": canonical(payload),
        },
    )
    await audit(
        session,
        value=None,
        episode_id=episode_id,
        protection_id=group_id,
        event_id=request_id,
        kind="REQUEST",
    )
    return request_id
