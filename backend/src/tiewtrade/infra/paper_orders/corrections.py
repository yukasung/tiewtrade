"""Internal append-only correction integration for Paper fills."""

from dataclasses import replace
from uuid import UUID

from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.order_book import BookState
from tiewtrade.core.orders import BaseSize, OrderConflictError, OrderStatus, QuoteBudget
from tiewtrade.core.paper_matching import MatchingState, rebase_order_queues
from tiewtrade.core.positions import ExecutionFact
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
from tiewtrade.infra.market_data.order_book_storage import read_latest_book
from tiewtrade.infra.paper_orders.codec import intent_from_payload, object_payload
from tiewtrade.infra.paper_orders.executions import stage_correction_cash
from tiewtrade.infra.paper_orders.matching_storage import (
    MatchingCheckpoint,
    load_matching_state,
    load_order_state,
    persist_checkpoint,
)
from tiewtrade.infra.paper_orders.storage import (
    append_execution_input,
    increment_wallet_revision,
    lock_episode,
)
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.positions import (
    PositionEventKind,
    PositionWriteStatus,
    read_effective_executions,
    read_position_snapshot,
)


async def correct_fill(
    session: UserSession,
    *,
    wallet_id: UUID,
    episode_id: UUID,
    order_event_id: UUID,
    correction_event_id: UUID,
    supersedes_position_event_id: UUID,
    kind: PositionEventKind,
    fact: ExecutionFact,
) -> MatchingCheckpoint | None:
    """Apply one exact correction and reconcile order lifecycle in the same transaction."""
    session = require_user_session(session)
    wallet_id = UUID(str(wallet_id))
    episode_id = UUID(str(episode_id))
    order_event_id = UUID(str(order_event_id))
    correction_event_id = UUID(str(correction_event_id))
    supersedes_position_event_id = UUID(str(supersedes_position_event_id))
    await lock_episode(session, wallet_id, episode_id, require_active=False)
    source = (
        (
            await session.execute(
                """SELECT e.order_id,o.base,o.quote,c.payload AS command_payload
                FROM paper_order_events e JOIN paper_orders o ON o.id=e.order_id
                JOIN paper_order_commands c ON c.id=o.command_id
                WHERE e.id=:event AND e.episode_id=:episode AND e.event_kind='FILL'""",
                {"event": order_event_id, "episode": episode_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if source is None or fact.pair != fact.pair.__class__(source["base"], source["quote"]):
        raise OrderConflictError("correction source fill is unavailable")
    intent = intent_from_payload(object_payload(source["command_payload"])["intent"])
    linked = (
        await session.execute(
            "SELECT 1 FROM paper_execution_links WHERE position_event_id=:event",
            {"event": correction_event_id},
        )
    ).first()
    # Preserve checkpoint validation before a new correction. Committed replay
    # needs only its immutable linkage, never the active episode's matching state.
    checkpoint = (
        await load_matching_state(
            session, wallet_id=wallet_id, scope=intent.scope, pair=intent.pair
        )
        if linked is None
        else None
    )
    result = await stage_correction_cash(
        session,
        wallet_id=wallet_id,
        episode_id=episode_id,
        order_event_id=order_event_id,
        correction_event_id=correction_event_id,
        supersedes_position_event_id=supersedes_position_event_id,
        kind=kind,
        fact=fact,
    )
    if result.status is PositionWriteStatus.REPLAYED:
        return None
    if result.status is PositionWriteStatus.CONFLICTED:
        await session.execute(
            """UPDATE paper_order_activity SET availability='CONFLICTED',revision=revision+1,
            failure_code=:failure,observed_at=clock_timestamp() WHERE episode_id=:episode""",
            {"episode": episode_id, "failure": result.failure_code},
        )
        await increment_wallet_revision(session, wallet_id)
        await record_event(
            session,
            AuditEvent(
                owner_user_id=session.user_id,
                action=AuditAction.PAPER_ORDER_DECISION,
                actor_kind=ActorKind.SYSTEM,
                subject_kind=SubjectKind.PAPER_ORDER_ACTIVITY,
                subject_id=str(episode_id),
                outcome=AuditOutcome.SUCCEEDED,
                mode=AuditMode.PAPER,
                details=PaperOrderDecisionDetails(episode_id, correction_event_id, "CONFLICT"),
            ),
        )
        return None
    assert checkpoint is not None
    effective = await read_effective_executions(session, episode_id, fact.pair)
    identities = {
        row.execution_id
        for row in (
            await session.execute(
                """SELECT execution_id FROM paper_execution_links
                WHERE episode_id=:episode AND order_id=:order""",
                {"episode": episode_id, "order": source["order_id"]},
            )
        ).all()
    }
    filled = Quantity.of(0, fact.pair.base)
    spent = Money.of(0, fact.pair.quote)
    for execution in effective:
        if execution.execution_id in identities:
            filled += execution.gross_quantity
            spent += execution.quote_amount
    orders = list(checkpoint.state.orders)
    index = next(
        (i for i, value in enumerate(orders) if value.intent.order_id == source["order_id"]),
        None,
    )
    if index is None:
        orders.append(await load_order_state(session, source["order_id"]))
        orders.sort(key=lambda value: value.sequence)
        index = next(
            i for i, value in enumerate(orders) if value.intent.order_id == source["order_id"]
        )
    prior = orders[index]
    complete = (
        filled == prior.intent.size.quantity
        if isinstance(prior.intent.size, BaseSize)
        else spent == prior.intent.size.amount
    )
    if isinstance(prior.intent.size, BaseSize) and filled > prior.intent.size.quantity:
        raise OrderConflictError("corrected fills exceed immutable quantity")
    if isinstance(prior.intent.size, QuoteBudget) and spent > prior.intent.size.amount:
        raise OrderConflictError("corrected fills exceed immutable budget")
    terminal_before = prior.status.terminal
    status = (
        OrderStatus.FILLED
        if complete
        else OrderStatus.CANCELED
        if terminal_before
        else OrderStatus.PARTIALLY_FILLED
        if filled.amount > 0
        else OrderStatus.ACCEPTED
    )
    orders[index] = replace(
        prior,
        filled=filled,
        spent=spent,
        status=status,
        resting=prior.resting and not status.terminal,
        queue_ahead=prior.queue_ahead if not status.terminal else None,
    )
    state = replace(checkpoint.state, orders=tuple(orders))
    evidence = None
    if not terminal_before and prior.resting and not status.terminal:
        public = await read_latest_book(session, fact.pair)
        market = public.market
        if not isinstance(market, BookState):
            raise OrderConflictError("correction queue rebase book is unavailable")
        market = replace(market, rebase=True)
        evidence = await append_execution_input(
            session,
            wallet_id=wallet_id,
            episode_id=episode_id,
            evidence_id=UUID(int=correction_event_id.int ^ 1),
            record=public,
            decision_market=market,
        )
        state = rebase_order_queues(
            state,
            market,
            constraints=public.metadata.limit,
            market_constraints=public.metadata.market,
        )
    await _prove_reservations(session, wallet_id, episode_id, state)
    saved = await persist_checkpoint(
        session,
        wallet_id=wallet_id,
        state=state,
        anchor_order_id=source["order_id"],
        event_kind="CORRECTED",
        decision_kind="CORRECTION",
        occurred_at=(await session.execute("SELECT clock_timestamp()")).scalar_one(),
        input_recorded_at=None if evidence is None else evidence.recorded_at,
        input_evidence_id=None if evidence is None else evidence.evidence_id,
        decision_id=UUID(int=correction_event_id.int ^ 2),
    )
    if evidence is not None:
        saved = await persist_checkpoint(
            session,
            wallet_id=wallet_id,
            state=state,
            anchor_order_id=source["order_id"],
            event_kind="QUEUE_REBASED",
            decision_kind="REBASE",
            occurred_at=evidence.record.market.received_at,
            input_recorded_at=evidence.recorded_at,
            input_evidence_id=evidence.evidence_id,
            decision_id=UUID(int=correction_event_id.int ^ 3),
        )
    return saved


async def _prove_reservations(
    session: UserSession, wallet_id: UUID, episode_id: UUID, state: MatchingState
) -> None:
    if not isinstance(state, MatchingState):
        raise OrderConflictError("matching state required")
    wallet = await get_wallet(session)
    positions = await read_position_snapshot(session, episode_id)
    if wallet is None or positions is None:
        raise OrderConflictError("financial source is unavailable")
    pair_quote = Money.of(0, state.pair.quote)
    pair_base = Quantity.of(0, state.pair.base)
    for order in state.orders:
        pair_quote += order.reservation.quote
        pair_base += order.reservation.base
    other_quote = Money.of(
        (
            await session.execute(
                """SELECT coalesce(sum(quote_reserved),0) FROM paper_reservations
                WHERE episode_id=:episode AND (base<>:base OR quote<>:quote)""",
                {
                    "episode": episode_id,
                    "base": state.pair.base,
                    "quote": state.pair.quote,
                },
            )
        ).scalar_one(),
        state.pair.quote,
    )
    held = next(
        (value.held_quantity for value in positions.positions if value.pair == state.pair),
        Quantity.of(0, state.pair.base),
    )
    if pair_quote + other_quote > wallet.balance or pair_base > held:
        raise OrderConflictError("correction would leave insolvent reservations")
