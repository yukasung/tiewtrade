"""One owner-scoped Paper order worker transaction."""

from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from tiewtrade.core.market_catalog import CatalogSnapshot
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.order_book import BookState, MarketInput
from tiewtrade.core.orders import (
    AdmissionPolicy,
    OrderError,
    OrderIntent,
    OrderStatus,
    OrderType,
    SourceUnavailableError,
)
from tiewtrade.core.paper_matching import MatchingState, admit_order, advance_matching, cancel_order
from tiewtrade.core.positions import ExecutionFact, ExecutionSide
from tiewtrade.core.realtime_prices import Readiness, readiness
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
from tiewtrade.infra.market_data.order_book_codec import canonical
from tiewtrade.infra.market_data.order_book_storage import (
    ExecutionInputGapError,
    StoredExecutionInput,
    read_inputs,
    read_latest_book,
    set_pair_dependency,
)
from tiewtrade.infra.market_data.realtime_storage import read_snapshot
from tiewtrade.infra.paper_orders.codec import intent_from_payload, object_payload
from tiewtrade.infra.paper_orders.dispatch import (
    ClaimedOrder,
    complete_command,
    finish_claim,
    require_claim,
    reschedule_processed_orders,
)
from tiewtrade.infra.paper_orders.executions import execution_payload, stage_fill_cash
from tiewtrade.infra.paper_orders.initialization import enable_financial_writer
from tiewtrade.infra.paper_orders.matching_storage import (
    append_expiry_event,
    append_fill_event,
    insert_order_header,
    load_matching_state,
    load_order_state,
    persist_checkpoint,
)
from tiewtrade.infra.paper_orders.storage import (
    append_execution_input,
    increment_wallet_revision,
    lock_active_episode,
    lock_pair_catalog,
)
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.positions import (
    PositionEventKind,
    PositionWriteStatus,
    apply_position_event,
    read_position_snapshot,
)


class OrderWorkerIntegrityError(OrderError):
    code = "ORDER_WORKER_INTEGRITY"


class NoNewExecutionInputError(SourceUnavailableError):
    """The verified stream is healthy but has not advanced yet."""


class OrderFinancialConflictError(Exception):
    """Carry a deterministic F-14 conflict across the rolled-back fill transaction."""

    def __init__(
        self,
        claim: ClaimedOrder,
        wallet_id: UUID,
        episode_id: UUID,
        position_event_id: UUID,
        fact: ExecutionFact,
    ) -> None:
        super().__init__("Paper fill conflicts with the authoritative financial source")
        self.claim = claim
        self.wallet_id = wallet_id
        self.episode_id = episode_id
        self.position_event_id = position_event_id
        self.fact = fact


@dataclass(frozen=True, slots=True)
class _InputDecision:
    source: StoredExecutionInput
    market: MarketInput


def _identity(episode_id: UUID, value: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"tiewtrade:paper:{episode_id}:{value}")


async def process_claimed_order(
    session: UserSession,
    claim: ClaimedOrder,
    *,
    policy: AdmissionPolicy | None,
) -> None:
    """Process admission/cancel and one bounded market batch in one fenced transaction."""
    session = require_user_session(session)
    command = (
        (
            await session.execute(
                """SELECT c.*,r.state AS result_state FROM paper_order_commands c
                LEFT JOIN paper_order_command_results r ON r.command_id=c.id
                WHERE c.id=:id""",
                {"id": claim.command_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if command is None or command["user_id"] != session.user_id:
        raise OrderWorkerIntegrityError("claimed command is unavailable")
    await session.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(:key,0))",
        {"key": f"paper-wallet:{session.user_id}"},
    )
    active_episode = (
        await session.execute(
            """SELECT s.active_episode_id,
              EXISTS(SELECT 1 FROM paper_wallet_episode_closures c
                     WHERE c.episode_id=:episode) AS expected_episode_closed
            FROM paper_wallet_state s
            WHERE s.wallet_id=:wallet AND s.user_id=:user
            FOR UPDATE""",
            {
                "wallet": command["wallet_id"],
                "user": session.user_id,
                "episode": command["episode_id"],
            },
        )
    ).one_or_none()
    await require_claim(session, claim)
    await enable_financial_writer(session)
    if (
        active_episode is None
        or active_episode.active_episode_id != command["episode_id"]
        or active_episode.expected_episode_closed
    ):
        await _reject(session, claim, command, "EPISODE_CONFLICT")
        return
    await lock_active_episode(session, command["wallet_id"], command["episode_id"])
    if command["action"] == "CANCEL":
        await _process_cancel(session, claim, command)
        return
    intent = intent_from_payload(object_payload(command["payload"])["intent"])
    fence = await lock_pair_catalog(session, intent.pair)
    await _process_new(
        session,
        claim,
        command,
        policy,
        fence.snapshot,
        fence.latest_removed_revision,
    )


async def _process_new(
    session: UserSession,
    claim: ClaimedOrder,
    command: Any,
    policy: AdmissionPolicy | None,
    catalog: CatalogSnapshot,
    latest_removed_revision: int | None,
) -> None:
    row = command
    payload = object_payload(row["payload"])
    intent = intent_from_payload(payload["intent"])
    admitted_revision_value = _catalog_revision(payload)
    invalidated = (
        intent.side is ExecutionSide.BUY
        and latest_removed_revision is not None
        and latest_removed_revision > admitted_revision_value
    )
    accepted_command = (
        await session.execute(
            "SELECT command_id FROM paper_orders WHERE id=:order",
            {"order": intent.order_id},
        )
    ).scalar_one_or_none()
    if accepted_command is not None and accepted_command != row["id"]:
        await _reject(session, claim, row, "ORDER_CONFLICT")
        return
    checkpoint = await load_matching_state(
        session,
        wallet_id=row["wallet_id"],
        scope=intent.scope,
        pair=intent.pair,
    )
    state = await _cancel_removed_openings(
        session, row["wallet_id"], checkpoint.state, catalog, latest_removed_revision
    )
    result_exists = row["result_state"] is not None
    if (
        not result_exists
        and intent.side is ExecutionSide.BUY
        and (invalidated or not catalog.supports(intent.pair.base, intent.pair.quote))
    ):
        await _reject(session, claim, row, "CATALOG_PAIR_REMOVED")
        return
    if not result_exists:
        try:
            bootstrap_evidence = None
            if state.inputs:
                record = await _admission_record(session, state)
            else:
                record = await read_latest_book(session, state.pair)
                market = record.market
                assert isinstance(market, BookState)
                bootstrap = advance_matching(
                    state,
                    market,
                    now=(await session.execute("SELECT clock_timestamp()")).scalar_one(),
                    constraints=record.metadata.limit,
                    market_constraints=record.metadata.market,
                    execution_ids=(),
                    catalog=catalog,
                )
                if bootstrap.fills:
                    raise OrderWorkerIntegrityError("empty source bootstrap created a fill")
                state = bootstrap.state
                pair_key = f"{state.pair.base}:{state.pair.quote}"
                bootstrap_evidence = await append_execution_input(
                    session,
                    wallet_id=row["wallet_id"],
                    episode_id=row["episode_id"],
                    evidence_id=_identity(
                        row["episode_id"],
                        f"evidence:{pair_key}:{market.generation}:{market.input_id}:True",
                    ),
                    record=record,
                )
            reference = await _reference_price(session, intent)
            wallet = await get_wallet(session)
            positions = await read_position_snapshot(session, intent.scope.episode_id)
            if wallet is None or positions is None:
                raise OrderWorkerIntegrityError("financial source is unavailable")
            held = next(
                (p.held_quantity for p in positions.positions if p.pair == intent.pair),
                Quantity.of(0, intent.pair.base),
            )
            other_reserved = (
                await session.execute(
                    """SELECT coalesce(sum(quote_reserved),0) FROM paper_reservations
                    WHERE episode_id=:episode AND quote=:quote
                      AND (base<>:base OR quote<>:quote)""",
                    {
                        "episode": intent.scope.episode_id,
                        "base": intent.pair.base,
                        "quote": intent.pair.quote,
                    },
                )
            ).scalar_one()
            cash = wallet.balance - Money.of(other_reserved, intent.pair.quote)
            constraints = (
                record.metadata.market if intent.kind is OrderType.MARKET else record.metadata.limit
            )
            order_sequence = int(
                (
                    await session.execute(
                        """SELECT coalesce(max(sequence),0)+1 FROM paper_orders
                        WHERE episode_id=:episode""",
                        {"episode": intent.scope.episode_id},
                    )
                ).scalar_one()
            )
            accepted = admit_order(
                state,
                intent,
                now=(await session.execute("SELECT clock_timestamp()")).scalar_one(),
                sequence=order_sequence,
                cash=cash,
                held=held,
                constraints=constraints,
                reference_price=reference,
                policy=policy,
                catalog=catalog,
            )
            order = next(v for v in accepted.orders if v.intent.order_id == intent.order_id)
            await insert_order_header(
                session,
                wallet_id=row["wallet_id"],
                command_id=row["id"],
                order=order,
            )
            await persist_checkpoint(
                session,
                wallet_id=row["wallet_id"],
                state=accepted,
                anchor_order_id=intent.order_id,
                event_kind="ACCEPTED",
                decision_kind="ACCEPT",
                occurred_at=order.accepted_at,
                input_recorded_at=(
                    None if bootstrap_evidence is None else bootstrap_evidence.recorded_at
                ),
                input_evidence_id=(
                    None if bootstrap_evidence is None else bootstrap_evidence.evidence_id
                ),
                decision_id=_identity(intent.scope.episode_id, f"accept:{row['id']}"),
            )
            await complete_command(
                session,
                command_id=row["id"],
                episode_id=intent.scope.episode_id,
                succeeded=True,
                snapshot={
                    "order_id": str(intent.order_id),
                    "status": OrderStatus.ACCEPTED.value,
                    "filled": order.filled.as_parts(),
                    "spent": order.spent.as_parts(),
                },
            )
            state = accepted
        except SourceUnavailableError:
            raise
        except OrderError as error:
            await _reject(session, claim, row, error.code)
            return
    target = next((v for v in state.orders if v.intent.order_id == intent.order_id), None)
    if target is None:
        target = await load_order_state(session, intent.order_id)
        if not target.status.terminal:
            raise OrderWorkerIntegrityError("active order is absent from checkpoint")
    if target.status.terminal:
        await set_pair_dependency(
            session,
            wallet_id=row["wallet_id"],
            episode_id=intent.scope.episode_id,
            pair=intent.pair,
            needed=any(not order.status.terminal for order in state.orders),
        )
        await finish_claim(session, claim, terminal=True)
        return
    try:
        decisions = await _next_or_recovery_inputs(session, state)
    except NoNewExecutionInputError:
        await set_pair_dependency(
            session,
            wallet_id=row["wallet_id"],
            episode_id=intent.scope.episode_id,
            pair=intent.pair,
            needed=True,
        )
        await finish_claim(session, claim, terminal=False)
        return
    await _apply_inputs(session, claim, row, state, decisions, catalog)


def _catalog_revision(payload: dict[str, Any]) -> int:
    revision = payload.get("catalog_revision", 0)
    if type(revision) is not int or revision < 0:
        raise OrderWorkerIntegrityError("opening catalog revision is invalid")
    return revision


async def _cancel_removed_openings(
    session: UserSession,
    wallet_id: UUID,
    state: MatchingState,
    catalog: CatalogSnapshot,
    latest_removed_revision: int | None,
) -> MatchingState:
    """Fence every opening order before any claim advances the shared pair state."""
    active = catalog.supports(state.pair.base, state.pair.quote)
    if active and latest_removed_revision is None:
        return state
    openings = tuple(
        order
        for order in state.orders
        if order.intent.side is ExecutionSide.BUY and not order.status.terminal
    )
    if not openings:
        return state
    rows = (
        (
            await session.execute(
                """SELECT o.id,c.payload FROM paper_orders o
            JOIN paper_order_commands c ON c.id=o.command_id
            WHERE o.id=ANY(:orders)""",
                {"orders": [order.intent.order_id for order in openings]},
            )
        )
        .mappings()
        .all()
    )
    revisions = {row["id"]: _catalog_revision(object_payload(row["payload"])) for row in rows}
    if len(revisions) != len(openings):
        raise OrderWorkerIntegrityError("opening catalog evidence is unavailable")
    for order in openings:
        if active and (
            latest_removed_revision is None
            or revisions[order.intent.order_id] >= latest_removed_revision
        ):
            continue
        state = cancel_order(state, order.intent.order_id, scope=order.intent.scope)
        await persist_checkpoint(
            session,
            wallet_id=wallet_id,
            state=state,
            anchor_order_id=order.intent.order_id,
            event_kind="CANCELED",
            decision_kind="CANCEL",
            occurred_at=(await session.execute("SELECT clock_timestamp()")).scalar_one(),
            decision_id=_identity(
                order.intent.scope.episode_id, f"catalog-cancel:{order.intent.order_id}"
            ),
        )
    return state


async def _next_or_recovery_inputs(
    session: UserSession, state: MatchingState
) -> tuple[_InputDecision, ...]:
    after = state.inputs[-1].input_id if state.inputs else 0
    try:
        values = await read_inputs(session, state.pair, after=after, limit=20)
    except ExecutionInputGapError:
        record = await read_latest_book(session, state.pair)
        market = record.market
        assert isinstance(market, BookState)
        return (_InputDecision(record, replace(market, rebase=True)),)
    if not values:
        raise NoNewExecutionInputError("no new verified execution input")
    now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
    if now - values[0].market.received_at > timedelta(seconds=1):
        record = await read_latest_book(session, state.pair)
        market = record.market
        assert isinstance(market, BookState)
        return (_InputDecision(record, replace(market, rebase=True)),)
    return tuple(_InputDecision(value, value.market) for value in values)


async def _admission_record(session: UserSession, state: MatchingState) -> StoredExecutionInput:
    if not state.inputs:
        return (await _next_or_recovery_inputs(session, state))[0].source
    identity = state.inputs[-1].input_id
    try:
        values = await read_inputs(session, state.pair, after=identity - 1, limit=1)
    except ExecutionInputGapError:
        return await read_latest_book(session, state.pair)
    if not values or values[0].market.input_id != identity:
        raise SourceUnavailableError("latest execution capability is unavailable")
    return values[0]


async def _reference_price(session: UserSession, intent: OrderIntent) -> Money:
    snapshot = await read_snapshot(session)
    row = next(
        (v for v in snapshot.rows if (v.base, v.quote) == (intent.pair.base, intent.pair.quote)),
        None,
    )
    feed = snapshot.feed
    if (
        row is None
        or feed is None
        or row.effective_readiness != Readiness.READY.value
        or readiness(
            quote=row.observation,
            connected=feed.connected,
            reconciled=row.reconciled_generation == feed.generation,
            producer_alive=feed.lease_until > snapshot.server_time,
            now=snapshot.server_time,
        )
        is not Readiness.READY
        or row.observation is None
    ):
        raise SourceUnavailableError("latest trade reference is unavailable")
    return row.observation.amount


async def _apply_inputs(
    session: UserSession,
    claim: ClaimedOrder,
    command: Any,
    state: MatchingState,
    decisions: tuple[_InputDecision, ...],
    catalog: CatalogSnapshot,
) -> None:
    row = command
    pair_key = f"{state.pair.base}:{state.pair.quote}"
    anchor = row["order_id"]
    rebased = False
    saved = None
    market = None
    record = None
    for decision in decisions:
        record = decision.source
        market = decision.market
        recovery = int(isinstance(market, BookState) and market.rebase)
        evidence_key = (
            f"evidence:{pair_key}:{record.market.generation}:{record.market.input_id}:{recovery}"
        )
        saved = await append_execution_input(
            session,
            wallet_id=row["wallet_id"],
            episode_id=row["episode_id"],
            evidence_id=_identity(row["episode_id"], evidence_key),
            record=record,
            decision_market=market,
        )
        identity_count = (
            len(state.orders)
            if not isinstance(market, BookState)
            else len(state.orders) * (len(market.bids) + len(market.asks))
        )
        transition = advance_matching(
            state,
            market,
            now=(await session.execute("SELECT clock_timestamp()")).scalar_one(),
            constraints=record.metadata.limit,
            market_constraints=record.metadata.market,
            execution_ids=tuple(
                _identity(
                    row["episode_id"],
                    f"fill:{pair_key}:{record.market.generation}:{record.market.input_id}:{index}",
                )
                for index in range(identity_count)
            ),
            catalog=catalog,
        )
        for index, (fact, order_id) in enumerate(
            zip(transition.fills, transition.fill_order_ids, strict=True)
        ):
            order_event_id = _identity(row["episode_id"], f"order-fill:{fact.execution_id}")
            await append_fill_event(
                session,
                order_id=order_id,
                fact_id=fact.execution_id,
                payload=canonical({"execution": execution_payload(fact)}),
                evidence_id=saved.evidence_id,
                evidence_recorded_at=saved.recorded_at,
                pair=fact.pair,
                episode_id=row["episode_id"],
                occurred_at=fact.occurred_at,
                event_id=order_event_id,
            )
            result = await stage_fill_cash(
                session,
                wallet_id=row["wallet_id"],
                episode_id=row["episode_id"],
                order_event_id=order_event_id,
                position_event_id=_identity(row["episode_id"], f"position:{fact.execution_id}"),
                fact=fact,
            )
            if result.status is PositionWriteStatus.CONFLICTED:
                raise OrderFinancialConflictError(
                    claim,
                    row["wallet_id"],
                    row["episode_id"],
                    _identity(row["episode_id"], f"position:{fact.execution_id}"),
                    fact,
                )
            if result.status is not PositionWriteStatus.APPLIED:
                raise OrderWorkerIntegrityError(f"fill {index} did not apply atomically")
        previous_status = {order.intent.order_id: order.status for order in state.orders}
        for order in transition.state.orders:
            if (
                order.status is OrderStatus.EXPIRED
                and previous_status[order.intent.order_id] is not OrderStatus.EXPIRED
            ):
                await append_expiry_event(
                    session,
                    order=order,
                    evidence_id=saved.evidence_id,
                    evidence_recorded_at=saved.recorded_at,
                    occurred_at=market.received_at,
                    event_id=_identity(row["episode_id"], f"expired:{order.intent.order_id}"),
                )
        if transition.fill_order_ids:
            anchor = transition.fill_order_ids[-1]
        rebased = rebased or transition.rebased
        state = transition.state
    assert record is not None and market is not None and saved is not None
    await persist_checkpoint(
        session,
        wallet_id=row["wallet_id"],
        state=state,
        anchor_order_id=anchor,
        event_kind="INPUT_APPLIED",
        decision_kind="REBASE" if rebased else "INPUT",
        occurred_at=market.received_at,
        input_recorded_at=saved.recorded_at,
        input_evidence_id=saved.evidence_id,
        decision_id=_identity(
            row["episode_id"],
            f"input:{pair_key}:{record.market.generation}:{record.market.input_id}:{int(rebased)}",
        ),
    )
    terminal = next(
        order for order in state.orders if order.intent.order_id == row["order_id"]
    ).status.terminal
    await set_pair_dependency(
        session,
        wallet_id=row["wallet_id"],
        episode_id=row["episode_id"],
        pair=state.pair,
        needed=any(not order.status.terminal for order in state.orders),
    )
    await reschedule_processed_orders(
        session, claim, order_ids=tuple(order.intent.order_id for order in state.orders)
    )
    await finish_claim(
        session,
        claim,
        terminal=terminal,
        retry_delay_ms=20 if terminal else 200,
    )


async def persist_financial_conflict(
    session: UserSession, conflict: OrderFinancialConflictError
) -> None:
    """Persist only the deterministic conflict after the attempted fill batch rolled back."""
    session = require_user_session(session)
    await lock_active_episode(session, conflict.wallet_id, conflict.episode_id)
    await require_claim(session, conflict.claim)
    await enable_financial_writer(session)
    result = await apply_position_event(
        session,
        conflict.episode_id,
        conflict.position_event_id,
        PositionEventKind.RECORD,
        conflict.fact,
    )
    if result.status is not PositionWriteStatus.CONFLICTED or result.failure_code is None:
        raise OrderWorkerIntegrityError("financial conflict could not be reproduced safely")
    await session.execute(
        """UPDATE paper_order_activity SET availability='CONFLICTED',revision=revision+1,
        failure_code=:failure,observed_at=clock_timestamp() WHERE episode_id=:episode""",
        {"episode": conflict.episode_id, "failure": result.failure_code},
    )
    await increment_wallet_revision(session, conflict.wallet_id)
    await set_pair_dependency(
        session,
        wallet_id=conflict.wallet_id,
        episode_id=conflict.episode_id,
        pair=conflict.fact.pair,
        needed=True,
    )
    await finish_claim(session, conflict.claim, terminal=True)


async def _process_cancel(session: UserSession, claim: ClaimedOrder, command: Any) -> None:
    row = command
    order = (
        await session.execute(
            "SELECT base,quote FROM paper_orders WHERE id=:order",
            {"order": row["order_id"]},
        )
    ).first()
    if order is None:
        await _reject(session, claim, row, "ORDER_CONFLICT")
        return
    intent = (
        await session.execute(
            """SELECT c.payload FROM paper_orders o
            JOIN paper_order_commands c ON c.id=o.command_id
            WHERE o.id=:order""",
            {"order": row["order_id"]},
        )
    ).scalar_one()
    original = intent_from_payload(object_payload(intent)["intent"])
    checkpoint = await load_matching_state(
        session,
        wallet_id=row["wallet_id"],
        scope=original.scope,
        pair=original.pair,
    )
    historical = next(
        (value for value in checkpoint.state.orders if value.intent.order_id == row["order_id"]),
        None,
    )
    was_terminal = historical.status.terminal if historical is not None else None
    if historical is None:
        historical = await load_order_state(session, row["order_id"])
        was_terminal = historical.status.terminal
        state = replace(
            checkpoint.state,
            orders=tuple(
                sorted(
                    (*checkpoint.state.orders, historical),
                    key=lambda value: value.sequence,
                )
            ),
        )
    else:
        state = checkpoint.state
    changed = cancel_order(state, row["order_id"], scope=original.scope)
    target = next(v for v in changed.orders if v.intent.order_id == row["order_id"])
    if not was_terminal:
        await persist_checkpoint(
            session,
            wallet_id=row["wallet_id"],
            state=changed,
            anchor_order_id=row["order_id"],
            event_kind="CANCELED",
            decision_kind="CANCEL",
            occurred_at=(await session.execute("SELECT clock_timestamp()")).scalar_one(),
            decision_id=_identity(row["episode_id"], f"cancel:{row['id']}"),
        )
    await complete_command(
        session,
        command_id=row["id"],
        episode_id=row["episode_id"],
        succeeded=True,
        snapshot={"order_id": str(row["order_id"]), "status": target.status.value},
    )
    await set_pair_dependency(
        session,
        wallet_id=row["wallet_id"],
        episode_id=row["episode_id"],
        pair=original.pair,
        needed=any(not value.status.terminal for value in changed.orders),
    )
    await finish_claim(session, claim, terminal=True)


async def _reject(
    session: UserSession,
    claim: ClaimedOrder,
    command: Any,
    failure_code: str,
) -> None:
    row = command
    await complete_command(
        session,
        command_id=row["id"],
        episode_id=row["episode_id"],
        succeeded=False,
        failure_code=failure_code,
        snapshot={"order_id": str(row["order_id"]), "status": "REJECTED"},
    )
    await record_event(
        session,
        AuditEvent(
            owner_user_id=session.user_id,
            action=AuditAction.PAPER_ORDER_DECISION,
            actor_kind=ActorKind.SYSTEM,
            subject_kind=SubjectKind.PAPER_ORDER_ACTIVITY,
            subject_id=str(row["episode_id"]),
            outcome=AuditOutcome.SUCCEEDED,
            mode=AuditMode.PAPER,
            details=PaperOrderDecisionDetails(row["episode_id"], row["id"], "REJECT"),
        ),
    )
    await finish_claim(session, claim, terminal=True)
