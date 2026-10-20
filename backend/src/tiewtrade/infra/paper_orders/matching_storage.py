"""Durable matching checkpoints and rebuildable order projections."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import (
    OrderConflictError,
    OrderScope,
    OrderState,
    OrderStatus,
    SimulationProfile,
)
from tiewtrade.core.paper_matching import MatchingState
from tiewtrade.core.positions import PositionPair
from tiewtrade.infra.audit import (
    ActorKind,
    AuditAction,
    AuditEvent,
    AuditMode,
    AuditOutcome,
    PaperOrderDecisionDetails,
    SubjectKind,
    record_event,
)
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.market_data.order_book_codec import (
    canonical,
    constraints_from_payload,
    constraints_payload,
)
from tiewtrade.infra.paper_orders.codec import (
    intent_from_payload,
    object_payload,
    state_from_payload,
    state_payload,
)
from tiewtrade.infra.paper_orders.initialization import enable_financial_writer
from tiewtrade.infra.paper_orders.storage import increment_wallet_revision, lock_active_episode


@dataclass(frozen=True, slots=True)
class MatchingCheckpoint:
    decision_sequence: int
    decision_id: UUID
    state: MatchingState


def _matching_document(state: MatchingState, sequence: int) -> tuple[str, str]:
    matching = state_payload(state)
    digest = hashlib.sha256(canonical(matching).encode()).hexdigest()
    document = canonical(
        {"decision_sequence": sequence, "matching": matching, "matching_digest": digest}
    )
    return document, digest


async def load_matching_state(
    session: UserSession,
    *,
    wallet_id: UUID,
    scope: OrderScope,
    pair: PositionPair,
) -> MatchingCheckpoint:
    """Load the latest verified pair checkpoint; absence is a proven empty pair only."""
    session = require_user_session(session)
    if scope.owner_id != session.user_id or scope.episode_id is None:
        raise OrderConflictError("matching scope owner mismatch")
    await lock_active_episode(session, wallet_id, scope.episode_id)
    activity = (
        (
            await session.execute(
                """SELECT availability,source_sequence,initialization_id,source_proof
                FROM paper_order_activity WHERE episode_id=:episode FOR UPDATE""",
                {"episode": scope.episode_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if (
        activity is None
        or activity["availability"] != "READY"
        or activity["initialization_id"] is None
        or activity["source_proof"] is None
    ):
        raise OrderConflictError("authoritative order source is unavailable")
    profile = (
        await session.execute(
            """SELECT fee_version,model_version FROM paper_execution_profiles
            WHERE episode_id=:episode""",
            {"episode": scope.episode_id},
        )
    ).first()
    if profile is None:
        raise OrderConflictError("pinned matching profile is unavailable")
    row = (
        (
            await session.execute(
                """SELECT id,payload FROM paper_order_events
                WHERE episode_id=:episode AND base=:base AND quote=:quote
                  AND payload ? 'matching'
                ORDER BY ((payload->>'decision_sequence')::bigint) DESC LIMIT 1""",
                {"episode": scope.episode_id, "base": pair.base, "quote": pair.quote},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        count = (
            await session.execute(
                """SELECT count(*) FROM paper_order_projections
                WHERE episode_id=:episode AND base=:base AND quote=:quote
                  AND status NOT IN ('FILLED','CANCELED','EXPIRED','REJECTED')""",
                {"episode": scope.episode_id, "base": pair.base, "quote": pair.quote},
            )
        ).scalar_one()
        if count:
            raise OrderConflictError("order history exists without matching checkpoint")
        state = MatchingState(
            scope,
            pair,
            SimulationProfile(profile.fee_version, profile.model_version),
            execution_sequence=await _position_sequence(session, scope.episode_id),
        )
        return MatchingCheckpoint(int(activity["source_sequence"]), uuid4(), state)
    payload = row["payload"]
    matching = payload["matching"]
    if hashlib.sha256(canonical(matching).encode()).hexdigest() != payload["matching_digest"]:
        raise OrderConflictError("matching checkpoint digest mismatch")
    if not 0 < int(payload["decision_sequence"]) <= int(activity["source_sequence"]):
        raise OrderConflictError("matching decision sequence is inconsistent")
    state = state_from_payload(matching)
    if (
        state.scope != scope
        or state.pair != pair
        or state.profile != SimulationProfile(profile.fee_version, profile.model_version)
    ):
        raise OrderConflictError("matching checkpoint provenance mismatch")
    state = MatchingState(
        state.scope,
        state.pair,
        state.profile,
        state.orders,
        state.liquidity,
        state.inputs,
        state.input_constraints,
        state.executions,
        state.book,
        await _position_sequence(session, scope.episode_id),
    )
    await _verify_projections(session, state)
    return MatchingCheckpoint(int(payload["decision_sequence"]), row["id"], state)


async def _position_sequence(session: UserSession, episode_id: UUID) -> int:
    value = (
        await session.execute(
            "SELECT source_sequence FROM paper_position_activity WHERE episode_id=:episode",
            {"episode": episode_id},
        )
    ).scalar_one_or_none()
    if value is None:
        raise OrderConflictError("position source is unavailable")
    return int(value)


async def _verify_projections(session: UserSession, state: MatchingState) -> None:
    rows = (
        (
            await session.execute(
                """SELECT p.*,r.quote_reserved,r.base_reserved FROM paper_order_projections p
                JOIN paper_reservations r ON r.order_id=p.order_id
                WHERE p.episode_id=:episode AND p.base=:base AND p.quote=:quote
                  AND p.status NOT IN ('FILLED','CANCELED','EXPIRED','REJECTED')""",
                {
                    "episode": state.scope.episode_id,
                    "base": state.pair.base,
                    "quote": state.pair.quote,
                },
            )
        )
        .mappings()
        .all()
    )
    expected = {order.intent.order_id: order for order in state.orders}
    if set(expected) != {row["order_id"] for row in rows}:
        raise OrderConflictError("matching checkpoint/projection set mismatch")
    for row in rows:
        order = expected[row["order_id"]]
        if (
            row["status"] != order.status.value
            or Quantity.of(row["filled_quantity"], state.pair.base) != order.filled
            or Money.of(row["spent"], state.pair.quote) != order.spent
            or bool(row["resting"]) != order.resting
            or (
                None
                if row["queue_ahead"] is None
                else Quantity.of(row["queue_ahead"], state.pair.base)
            )
            != order.queue_ahead
            or Money.of(row["quote_reserved"], state.pair.quote) != order.reservation.quote
            or Quantity.of(row["base_reserved"], state.pair.base) != order.reservation.base
        ):
            raise OrderConflictError("matching projection differs from immutable checkpoint")


async def load_order_state(session: UserSession, order_id: UUID) -> OrderState:
    """Rebuild one historical order for late cancel or append-only correction."""
    session = require_user_session(session)
    row = (
        (
            await session.execute(
                """SELECT o.*,c.payload AS command_payload,p.status,p.filled_quantity,p.spent,
                p.resting,p.queue_ahead FROM paper_orders o
                JOIN paper_order_commands c ON c.id=o.command_id
                JOIN paper_order_projections p ON p.order_id=o.id WHERE o.id=:order""",
                {"order": order_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise OrderConflictError("order projection is unavailable")
    intent = intent_from_payload(object_payload(row["command_payload"])["intent"])
    return OrderState(
        intent,
        int(row["sequence"]),
        row["accepted_at"],
        OrderStatus(row["status"]),
        Quantity.of(row["filled_quantity"], row["base"]),
        Money.of(row["spent"], row["quote"]),
        constraints_from_payload(row["constraints"]),
        bool(row["resting"]),
        None if row["queue_ahead"] is None else Quantity.of(row["queue_ahead"], row["base"]),
    )


async def insert_order_header(
    session: UserSession,
    *,
    wallet_id: UUID,
    command_id: UUID,
    order: OrderState,
) -> None:
    """Insert immutable accepted intent. The caller persists its checkpoint immediately."""
    session = require_user_session(session)
    intent = order.intent
    quantity = getattr(intent.size, "quantity", None)
    budget = getattr(intent.size, "amount", None)
    await session.execute(
        """INSERT INTO paper_orders
        (id,user_id,wallet_id,episode_id,command_id,sequence,base,quote,origin,side,kind,
         time_in_force,quantity,budget,limit_price,accepted_at,constraints)
        VALUES(:id,:user,:wallet,:episode,:command,:sequence,:base,:quote,:origin,:side,:kind,
         :tif,:quantity,:budget,:limit,:accepted,CAST(:constraints AS jsonb))""",
        {
            "id": intent.order_id,
            "user": session.user_id,
            "wallet": wallet_id,
            "episode": intent.scope.episode_id,
            "command": command_id,
            "sequence": order.sequence,
            "base": intent.pair.base,
            "quote": intent.pair.quote,
            "origin": intent.origin.value,
            "side": intent.side.value,
            "kind": intent.kind.value,
            "tif": None if intent.time_in_force is None else intent.time_in_force.value,
            "quantity": None if quantity is None else quantity.amount,
            "budget": None if budget is None else budget.amount,
            "limit": None if intent.limit_price is None else intent.limit_price.amount,
            "accepted": order.accepted_at,
            "constraints": canonical(constraints_payload(order.admission_constraints)),
        },
    )


async def append_fill_event(
    session: UserSession,
    *,
    order_id: UUID,
    fact_id: UUID,
    payload: str,
    evidence_id: UUID,
    evidence_recorded_at: datetime,
    pair: PositionPair,
    episode_id: UUID,
    occurred_at: datetime,
    event_id: UUID | None = None,
) -> UUID:
    """Append the immutable order-side half of a fill before F-14 links it."""
    session = require_user_session(session)
    identity = event_id or uuid4()
    sequence = (
        await session.execute(
            "SELECT coalesce(max(sequence),0)+1 FROM paper_order_events WHERE order_id=:order",
            {"order": order_id},
        )
    ).scalar_one()
    await session.execute(
        """INSERT INTO paper_order_events
        (id,order_id,user_id,episode_id,base,quote,sequence,event_kind,execution_id,
         input_recorded_at,input_evidence_id,payload,occurred_at)
        VALUES(:id,:order,:user,:episode,:base,:quote,:sequence,'FILL',:execution,
         :recorded,:evidence,CAST(:payload AS jsonb),:occurred)""",
        {
            "id": identity,
            "order": order_id,
            "user": session.user_id,
            "episode": episode_id,
            "base": pair.base,
            "quote": pair.quote,
            "sequence": sequence,
            "execution": fact_id,
            "recorded": evidence_recorded_at,
            "evidence": evidence_id,
            "payload": payload,
            "occurred": occurred_at,
        },
    )
    return identity


async def persist_checkpoint(
    session: UserSession,
    *,
    wallet_id: UUID,
    state: MatchingState,
    anchor_order_id: UUID,
    event_kind: str,
    decision_kind: str,
    occurred_at: datetime,
    input_recorded_at: datetime | None = None,
    input_evidence_id: UUID | None = None,
    decision_id: UUID | None = None,
) -> MatchingCheckpoint:
    """Append a decision and atomically advance every rebuildable projection."""
    session = require_user_session(session)
    await lock_active_episode(session, wallet_id, state.scope.episode_id)
    await enable_financial_writer(session)
    current = (
        await session.execute(
            """SELECT source_sequence,revision FROM paper_order_activity
            WHERE episode_id=:episode AND availability='READY' FOR UPDATE""",
            {"episode": state.scope.episode_id},
        )
    ).first()
    if current is None:
        raise OrderConflictError("authoritative order source is unavailable")
    sequence = int(current.source_sequence) + 1
    revision = int(current.revision) + 1
    event_id = decision_id or uuid4()
    document, _ = _matching_document(state, sequence)
    event_sequence = (
        await session.execute(
            """SELECT coalesce(max(sequence),0)+1 FROM paper_order_events
            WHERE order_id=:order""",
            {"order": anchor_order_id},
        )
    ).scalar_one()
    await session.execute(
        """INSERT INTO paper_order_events
        (id,order_id,user_id,episode_id,base,quote,sequence,event_kind,
         input_recorded_at,input_evidence_id,payload,occurred_at)
        VALUES(:id,:order,:user,:episode,:base,:quote,:sequence,:kind,
         :recorded,:evidence,CAST(:payload AS jsonb),:occurred)""",
        {
            "id": event_id,
            "order": anchor_order_id,
            "user": session.user_id,
            "episode": state.scope.episode_id,
            "base": state.pair.base,
            "quote": state.pair.quote,
            "sequence": event_sequence,
            "kind": event_kind,
            "recorded": input_recorded_at,
            "evidence": input_evidence_id,
            "payload": document,
            "occurred": occurred_at,
        },
    )
    for order in state.orders:
        last_event = (
            event_id
            if order.intent.order_id == anchor_order_id
            else await _last_event(session, order.intent.order_id)
        )
        params = {
            "order": order.intent.order_id,
            "user": session.user_id,
            "episode": state.scope.episode_id,
            "base": state.pair.base,
            "quote": state.pair.quote,
            "status": order.status.value,
            "filled": order.filled.amount,
            "spent": order.spent.amount,
            "resting": order.resting,
            "ahead": None if order.queue_ahead is None else order.queue_ahead.amount,
            "revision": revision,
            "event": last_event,
            "reserved_quote": order.reservation.quote.amount,
            "reserved_base": order.reservation.base.amount,
        }
        await session.execute(
            """INSERT INTO paper_order_projections
            (order_id,user_id,episode_id,base,quote,status,filled_quantity,spent,resting,
             queue_ahead,revision,last_event_id)
            VALUES(:order,:user,:episode,:base,:quote,:status,:filled,:spent,:resting,
             :ahead,:revision,:event)
            ON CONFLICT(order_id) DO UPDATE SET status=EXCLUDED.status,
             filled_quantity=EXCLUDED.filled_quantity,spent=EXCLUDED.spent,
             resting=EXCLUDED.resting,queue_ahead=EXCLUDED.queue_ahead,
             revision=EXCLUDED.revision,last_event_id=EXCLUDED.last_event_id""",
            params,
        )
        await session.execute(
            """INSERT INTO paper_reservations
            (order_id,user_id,episode_id,base,quote,quote_reserved,base_reserved,revision)
            VALUES(:order,:user,:episode,:base,:quote,:reserved_quote,:reserved_base,:revision)
            ON CONFLICT(order_id) DO UPDATE SET quote_reserved=EXCLUDED.quote_reserved,
             base_reserved=EXCLUDED.base_reserved,revision=EXCLUDED.revision""",
            params,
        )
    await session.execute(
        """UPDATE paper_order_projections SET revision=:revision WHERE episode_id=:episode""",
        {"episode": state.scope.episode_id, "revision": revision},
    )
    await session.execute(
        """UPDATE paper_reservations SET revision=:revision WHERE episode_id=:episode""",
        {"episode": state.scope.episode_id, "revision": revision},
    )
    await session.execute(
        """UPDATE paper_order_activity SET source_sequence=:sequence,revision=:revision,
        observed_at=clock_timestamp() WHERE episode_id=:episode""",
        {"episode": state.scope.episode_id, "sequence": sequence, "revision": revision},
    )
    await increment_wallet_revision(session, wallet_id)
    await record_event(
        session,
        AuditEvent(
            owner_user_id=session.user_id,
            action=AuditAction.PAPER_ORDER_DECISION,
            actor_kind=ActorKind.SYSTEM,
            subject_kind=SubjectKind.PAPER_ORDER_ACTIVITY,
            subject_id=str(state.scope.episode_id),
            outcome=AuditOutcome.SUCCEEDED,
            mode=AuditMode.PAPER,
            details=PaperOrderDecisionDetails(state.scope.episode_id, event_id, decision_kind),
        ),
    )
    return MatchingCheckpoint(sequence, event_id, state)


async def _last_event(session: UserSession, order_id: UUID) -> UUID:
    value = (
        await session.execute(
            """SELECT id FROM paper_order_events WHERE order_id=:order
            ORDER BY sequence DESC LIMIT 1""",
            {"order": order_id},
        )
    ).scalar_one_or_none()
    if value is None:
        raise OrderConflictError("order projection has no immutable event")
    return UUID(str(value))
