"""Fenced Paper protection decisions, always inside the financial writer transaction."""

from dataclasses import replace
from typing import Any
from uuid import UUID, uuid5

from tiewtrade.core.money import Money, MoneyError, Quantity
from tiewtrade.core.orders import (
    BaseSize,
    OrderConflictError,
    OrderError,
    OrderIntent,
    OrderOrigin,
    OrderScope,
    OrderType,
    SafetyUnavailableError,
    SourceUnavailableError,
    TradingMode,
)
from tiewtrade.core.positions import (
    ExecutionFact,
    ExecutionSide,
    PositionPair,
    PositionState,
    apply_execution,
)
from tiewtrade.core.protections import (
    EntryAllocationEvidence,
    ManualSaleAllocation,
    Protection,
    ProtectionPrices,
    ProtectionState,
    SetupAction,
    SetupOutcome,
    TriggerEvidence,
    cancel_protection,
    decide_setup_result,
    evaluate_trigger,
    prepare_manual_sale,
    replace_protection,
    validate_setup,
)
from tiewtrade.core.realtime_prices import Readiness, readiness
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.market_data.order_book_codec import canonical
from tiewtrade.infra.market_data.order_book_storage import read_latest_book
from tiewtrade.infra.market_data.realtime_storage import read_snapshot
from tiewtrade.infra.paper_orders.codec import object_payload
from tiewtrade.infra.paper_orders.dispatch import submit_cancel, submit_order
from tiewtrade.infra.paper_orders.requests import ManualRequest, decode_request, wallet_lock
from tiewtrade.infra.positions.views import held_and_reserved
from tiewtrade.infra.protections.storage import (
    StoredProtection,
    allocated,
    audit,
    create,
    enabled,
    free_quantity,
    groups,
    load,
    lock_scope,
    save,
)


def prices(pair: PositionPair, payload: dict[str, Any]) -> ProtectionPrices:
    return ProtectionPrices(
        pair,
        None if payload.get("tp") is None else Money.of(payload["tp"], pair.quote),
        None if payload.get("sl") is None else Money.of(payload["sl"], pair.quote),
    )


async def market_evidence(session: UserSession, pair: PositionPair) -> TriggerEvidence:
    snapshot = await read_snapshot(session)
    feed = snapshot.feed
    row = next((r for r in snapshot.rows if (r.base, r.quote) == (pair.base, pair.quote)), None)
    if (
        feed is None
        or row is None
        or row.effective_readiness != "READY"
        or readiness(
            quote=row.observation,
            connected=feed.connected,
            reconciled=row.reconciled_generation == feed.generation,
            producer_alive=feed.lease_until > snapshot.server_time,
            now=snapshot.server_time,
        )
        is not Readiness.READY
    ):
        raise SourceUnavailableError("protection last trade unavailable")
    observation = row.observation
    assert observation is not None
    return TriggerEvidence(
        uuid5(feed.owner, f"{pair.base}:{pair.quote}:{feed.generation}:{observation.trade_id}"),
        feed.generation,
        observation.trade_id,
        observation.amount,
        observation.trade_time,
        observation.received_at,
        pair,
    )


async def _validate_market_setup(
    session: UserSession, value: Protection, evidence: TriggerEvidence
) -> None:
    source = await read_latest_book(session, value.prices.pair)
    validate_setup(
        value,
        source.metadata.market,
        evidence,
        filter_reference_price=source.metadata.average_price,
    )


async def _effective_order_executions(
    session: UserSession,
    episode_id: UUID,
    order_id: UUID,
    facts: tuple[ExecutionFact, ...],
) -> tuple[ExecutionFact, ...]:
    identities = {
        row.execution_id
        for row in (
            await session.execute(
                "SELECT execution_id FROM paper_execution_links "
                "WHERE order_id=:order AND episode_id=:episode",
                {"order": order_id, "episode": episode_id},
            )
        ).all()
    }
    return tuple(fact for fact in facts if fact.execution_id in identities)


async def manual_request(session: UserSession, command_id: UUID) -> ManualRequest | None:
    row = (
        await session.execute(
            """SELECT q.* FROM paper_order_requests q
       JOIN paper_order_request_results r ON r.request_id=q.id WHERE r.command_id=:command""",
            {"command": command_id},
        )
    ).one_or_none()
    return None if row is None else decode_request(row)


async def prepare_admission(
    session: UserSession, intent: OrderIntent, wallet_id: UUID, command_id: UUID, held: Quantity
) -> tuple[Quantity, tuple[tuple[StoredProtection, Protection], ...]]:
    request = await manual_request(session, command_id)
    bracket = None if request is None else request.protection
    selections = () if request is None else request.protection_allocations
    if (bracket is not None or selections) and not await enabled(session):
        raise SafetyUnavailableError("protection protocol unavailable")
    if bracket is not None:
        levels = prices(intent.pair, bracket)
        levels.validate_creation((await market_evidence(session, intent.pair)).price)
    if intent.side is not ExecutionSide.SELL:
        return held, ()
    # Internal exit identity can only come from an owner-bound immutable command link.
    linked = (
        await session.execute(
            "SELECT protection_id FROM paper_protection_exits WHERE command_id=:id",
            {"id": command_id},
        )
    ).first()
    active = await groups(session, intent.scope.episode_id, intent.pair)
    if any(g.value.conflicted for g in active):
        # This command has not been admitted yet. Rejecting its unsafe allocation
        # lets the group settle to FAILED and be explicitly repaired; deferring
        # forever would keep EXITING uneditable with no actual order to cancel.
        raise OrderConflictError("protection allocation is conflicted")
    reserved = Quantity.of(
        (
            await session.execute(
                """SELECT coalesce(sum(base_reserved),0)
        FROM paper_reservations WHERE episode_id=:episode AND base=:base AND quote=:quote""",
                {
                    "episode": intent.scope.episode_id,
                    "base": intent.pair.base,
                    "quote": intent.pair.quote,
                },
            )
        ).scalar_one(),
        intent.pair.base,
    )
    released = Quantity.of(0, intent.pair.base)
    changes: tuple[tuple[StoredProtection, Protection], ...] = ()
    if linked is not None:
        group = next((g for g in active if g.value.protection_id == linked.protection_id), None)
        if group is None or group.value.state is not ProtectionState.EXITING:
            raise OrderConflictError("protection exit source unavailable")
        if not isinstance(intent.size, BaseSize) or intent.size.quantity > group.value.quantity:
            raise OrderConflictError("exit quantity exceeds allocation")
        released = intent.size.quantity
    elif selections:
        candidates = tuple(
            g
            for g in active
            if g.value.state
            in (ProtectionState.ARMED, ProtectionState.ARMING, ProtectionState.FAILED)
        )
        other = await allocated(session, intent.scope.episode_id, intent.pair)
        for group in candidates:
            other -= group.value.quantity
        assert isinstance(intent.size, BaseSize)
        preview = prepare_manual_sale(
            scope=intent.scope,
            pair=intent.pair,
            quantity=intent.size.quantity,
            held=held,
            reserved=reserved + other,
            protections=tuple(g.value for g in candidates),
            selections=tuple(
                ManualSaleAllocation(
                    UUID(s["protection_id"]),
                    s["expected_revision"],
                    Quantity.of(s["quantity"], intent.pair.base),
                )
                for s in selections
            ),
            authoritative_ready=True,
        )
        changes = tuple(
            (before, after)
            for before, after in zip(candidates, preview, strict=True)
            if before.value != after
        )
        for before, after in changes:
            released += before.value.quantity - after.quantity
    total = await allocated(session, intent.scope.episode_id, intent.pair)
    return held - (total - released), changes


async def commit_admission(
    session: UserSession,
    intent: OrderIntent,
    wallet_id: UUID,
    command_id: UUID,
    changes: tuple[tuple[StoredProtection, Protection], ...],
) -> None:
    for before, after in changes:
        await save(
            session,
            before,
            after,
            kind="MANUAL_RELEASE",
            disposed=before.disposed + before.value.quantity - after.quantity,
        )
    request = await manual_request(session, command_id)
    if request is not None and request.protection is not None:
        value = Protection(
            uuid5(request.request_id, "bracket"),
            intent.scope,
            intent.origin,
            prices(intent.pair, request.protection),
            Quantity.of(0, intent.pair.base),
            ProtectionState.WAITING_ENTRY,
            entry_order_id=intent.order_id,
        )
        await create(session, value, wallet_id, entry_request_id=request.request_id)


async def record_fill(session: UserSession, order_id: UUID, fact: ExecutionFact) -> None:
    # Reuse F-14's fee/base effect. Never reproduce fee arithmetic here.
    if fact.side is ExecutionSide.BUY:
        row = (
            await session.execute(
                "SELECT id FROM paper_protections WHERE entry_order_id=:order", {"order": order_id}
            )
        ).first()
        if row is None:
            return
        group = await load(session, row.id)
        assert group is not None
        value = group.value
        if value.state is ProtectionState.CANCELED:
            return
        delta = apply_execution(
            PositionState.empty(fact.pair), replace(fact, source_sequence=1)
        ).base_delta
        triggered = value.trigger is not None
        updated = replace(
            value,
            quantity=value.quantity + delta,
            revision=value.revision + 1,
            state=ProtectionState.EXITING if triggered else ProtectionState.ARMING,
            setup_attempt=1,
            setup_due_at=None,
        )
        await save(
            session,
            group,
            updated,
            kind="FILL",
            acquired=group.acquired + delta,
            extra_exit=group.extra_exit + delta if triggered else group.extra_exit,
        )
    else:
        row = (
            await session.execute(
                "SELECT id,protection_id FROM paper_protection_exits WHERE order_id=:order",
                {"order": order_id},
            )
        ).first()
        if row is None:
            return
        group = await load(session, row.protection_id)
        assert group is not None
        delta = fact.gross_quantity
        if delta > group.value.quantity:
            raise OrderConflictError("exit fill exceeds remaining protection")
        await save(
            session,
            group,
            replace(
                group.value,
                quantity=group.value.quantity - delta,
                revision=group.value.revision + 1,
            ),
            kind="FILL",
            disposed=group.disposed + delta,
        )
        await session.execute(
            "UPDATE paper_protection_exit_progress SET accounted=accounted+:quantity WHERE id=:id",
            {"id": row.id, "quantity": delta.as_parts()["quantity"]},
        )


async def queue_exit(session: UserSession, group: StoredProtection, quantity: Quantity) -> None:
    value = group.value
    exit_id = uuid5(value.protection_id, f"exit:{value.revision}")
    intent = OrderIntent(
        exit_id,
        exit_id,
        value.scope,
        value.prices.pair,
        value.origin,
        ExecutionSide.SELL,
        OrderType.MARKET,
        BaseSize(quantity),
    )
    command = await submit_order(session, wallet_id=group.wallet_id, intent=intent)
    await session.execute(
        """INSERT INTO paper_protection_exits
        (id,user_id,episode_id,protection_id,order_id,command_id,quantity)
        VALUES(:id,:owner,:episode,:group,:order,:command,:quantity)""",
        {
            "id": exit_id,
            "owner": session.user_id,
            "episode": value.scope.episode_id,
            "group": value.protection_id,
            "order": exit_id,
            "command": command.command_id,
            "quantity": quantity.as_parts()["quantity"],
        },
    )
    await session.execute(
        """INSERT INTO paper_protection_exit_progress(id,user_id,episode_id,quantity)
        VALUES(:id,:owner,:episode,:quantity)""",
        {
            "id": exit_id,
            "owner": session.user_id,
            "episode": value.scope.episode_id,
            "quantity": quantity.as_parts()["quantity"],
        },
    )


async def process_group(session: UserSession, group_id: UUID) -> None:
    group = await load(session, group_id)
    if group is None:
        return
    await lock_scope(session, group.wallet_id, group.value.scope.episode_id)
    group = await load(session, group_id)
    assert group is not None
    value = group.value
    if value.state in (ProtectionState.CANCELED, ProtectionState.CLOSED):
        return
    if value.state is ProtectionState.EXITING:
        exits = (
            await session.execute(
                """SELECT x.*,p.status,r.state AS command_state FROM paper_protection_exits x
            JOIN paper_protection_exit_progress s ON s.id=x.id
            LEFT JOIN paper_order_projections p ON p.order_id=x.order_id
            LEFT JOIN paper_order_command_results r ON r.command_id=x.command_id
            WHERE x.protection_id=:group AND NOT s.settled""",
                {"group": group_id},
            )
        ).all()
        if any(
            x.status not in ("FILLED", "CANCELED", "EXPIRED", "REJECTED")
            and x.command_state != "REJECTED"
            for x in exits
        ):
            return
        for item in exits:
            await session.execute(
                "UPDATE paper_protection_exit_progress SET settled=true WHERE id=:id",
                {"id": item.id},
            )
        if value.conflicted:
            await save(
                session,
                group,
                replace(value, revision=value.revision + 1, state=ProtectionState.FAILED),
                kind="CONFLICT",
                failure_code="ORDER_CONFLICT",
            )
        elif group.extra_exit.amount > 0:
            updated = await save(
                session,
                group,
                replace(value, revision=value.revision + 1),
                kind="EXIT",
                extra_exit=Quantity.of(0, value.prices.pair.base),
            )
            await queue_exit(session, updated, group.extra_exit)
        else:
            await save(
                session,
                group,
                replace(
                    value,
                    revision=value.revision + 1,
                    state=ProtectionState.CLOSED
                    if value.quantity.amount == 0
                    else ProtectionState.FAILED,
                ),
                kind="EXIT",
                failure_code=None if value.quantity.amount == 0 else "PROTECTION_RESIDUAL",
            )
        return
    if value.state is ProtectionState.WAITING_ENTRY:
        # Rejected/terminal-unfilled entry has no exposure to protect.
        row = (
            await session.execute(
                """SELECT p.status,r.state FROM paper_order_requests q
            LEFT JOIN paper_order_request_results t ON t.request_id=q.id
            LEFT JOIN paper_order_command_results r ON r.command_id=t.command_id
            LEFT JOIN paper_order_projections p ON p.order_id=q.order_id
            WHERE q.order_id=:entry AND q.action='NEW'""",
                {"entry": value.entry_order_id},
            )
        ).first()
        if row is not None and (
            row.state == "REJECTED" or row.status in ("CANCELED", "EXPIRED", "REJECTED")
        ):
            await save(
                session,
                group,
                cancel_protection(value, expected_revision=value.revision),
                kind="CANCEL",
            )
        return
    if value.conflicted or value.state is ProtectionState.FAILED:
        return
    try:
        evidence = await market_evidence(session, value.prices.pair)
        await free_quantity(session, value.scope.episode_id, value.prices.pair)
    except SourceUnavailableError:
        return
    except (OrderConflictError, MoneyError):
        await save(
            session,
            group,
            replace(value, conflicted=True, revision=value.revision + 1),
            kind="CONFLICT",
            failure_code="ORDER_CONFLICT",
        )
        return
    if value.state is ProtectionState.ARMING:
        now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
        if value.setup_due_at is not None and now < value.setup_due_at:
            return
        try:
            await _validate_market_setup(session, value, evidence)
        except (SourceUnavailableError, SafetyUnavailableError):
            decision = decide_setup_result(
                origin=value.origin,
                attempt=value.setup_attempt,
                outcome=SetupOutcome.TRANSIENT_FAILURE,
                observed_at=now,
            )
            retry = decision.action is SetupAction.RETRY
            await save(
                session,
                group,
                replace(
                    value,
                    revision=value.revision + 1,
                    state=ProtectionState.ARMING if retry else ProtectionState.FAILED,
                    setup_attempt=decision.next_attempt or value.setup_attempt,
                    setup_due_at=decision.due_at,
                ),
                kind="RETRY" if retry else "FAIL",
                failure_code="PROTECTION_SETUP_UNAVAILABLE",
            )
            return
        except (OrderError, MoneyError):
            await save(
                session,
                group,
                replace(
                    value,
                    revision=value.revision + 1,
                    state=ProtectionState.FAILED,
                    setup_due_at=None,
                ),
                kind="FAIL",
                failure_code="PROTECTION_SETUP_REJECTED",
            )
            return
        group = await save(
            session,
            group,
            replace(
                value, state=ProtectionState.ARMED, setup_due_at=None, revision=value.revision + 1
            ),
            kind="ARM",
        )
        value = group.value
    cursor = (evidence.source_id, evidence.generation, evidence.sequence)
    if group.observation == cursor and value.state is ProtectionState.ARMED:
        return
    await session.execute(
        """UPDATE paper_protections SET observed_source=:source,
        observed_generation=:generation,observed_sequence=:sequence WHERE id=:id""",
        {
            "id": value.protection_id,
            "source": evidence.source_id,
            "generation": evidence.generation,
            "sequence": evidence.sequence,
        },
    )
    changed = evaluate_trigger(value, evidence, market_ready=True, authoritative_ready=True)
    if changed is not value:
        group = await save(session, group, changed, kind="TRIGGER")
        await queue_exit(session, group, changed.quantity)
        if changed.entry_order_id is not None:
            await submit_cancel(
                session,
                wallet_id=group.wallet_id,
                episode_id=changed.scope.episode_id,
                order_id=changed.entry_order_id,
                idempotency_key=uuid5(changed.protection_id, "cancel-entry"),
            )


async def process_request(session: UserSession, request_id: UUID) -> None:
    row = (
        await session.execute(
            "SELECT * FROM paper_protection_requests WHERE id=:id", {"id": request_id}
        )
    ).one_or_none()
    if row is None:
        return
    await wallet_lock(session)
    if (
        await session.execute(
            "SELECT 1 FROM paper_protection_results WHERE request_id=:id", {"id": request_id}
        )
    ).first() is not None:
        return
    await session.execute(
        """INSERT INTO paper_protection_request_progress(request_id,user_id,episode_id)
        VALUES(:id,:owner,:episode) ON CONFLICT(request_id) DO NOTHING""",
        {"id": request_id, "owner": session.user_id, "episode": row.episode_id},
    )
    progress = (
        await session.execute(
            """SELECT attempt,next_attempt_at,clock_timestamp() AS now
            FROM paper_protection_request_progress WHERE request_id=:id""",
            {"id": request_id},
        )
    ).one()
    if progress.now < progress.next_attempt_at:
        return
    await lock_scope(session, row.wallet_id, row.episode_id)
    payload = object_payload(row.payload)
    failure = None
    result: dict[str, object] = {}
    await session.execute("SAVEPOINT protection_request")
    try:
        current = await load(session, row.protection_id)
        if row.action == "CREATE":
            pair = PositionPair(payload["base"], "USDT")
            level = prices(pair, payload)
            level.validate_creation((await market_evidence(session, pair)).price)
            quantity = Quantity.of(payload["quantity"], pair.base)
            if quantity.amount <= 0 or quantity > await free_quantity(
                session, row.episode_id, pair
            ):
                raise OrderConflictError("protection quantity unavailable")
            value = Protection(
                UUID(str(row.protection_id)),
                OrderScope(session.user_id, UUID(str(row.episode_id)), TradingMode.PAPER),
                OrderOrigin.MANUAL,
                level,
                quantity,
                ProtectionState.ARMING,
            )
            current = await create(session, value, row.wallet_id)
        else:
            if current is None or current.value.scope.episode_id != row.episode_id:
                raise OrderConflictError("protection unavailable")
            value = current.value
            if row.action == "CANCEL":
                updated = cancel_protection(value, expected_revision=payload["expected_revision"])
            else:
                held, reserved = await held_and_reserved(session, row.episode_id, value.prices.pair)
                other = await allocated(session, row.episode_id, value.prices.pair) - value.quantity
                capacity = max(held - reserved - other, Quantity.of(0, value.prices.pair.base))
                entry = (
                    None
                    if value.entry_order_id is None
                    else EntryAllocationEvidence(
                        value.scope,
                        value.prices.pair,
                        value.entry_order_id,
                        max(
                            current.acquired - current.disposed,
                            Quantity.of(0, value.prices.pair.base),
                        ),
                        value.revision,
                    )
                )
                evidence = await market_evidence(session, value.prices.pair)
                updated = replace_protection(
                    value,
                    expected_revision=payload["expected_revision"],
                    prices=prices(value.prices.pair, payload),
                    quantity=Quantity.of(payload["quantity"], value.prices.pair.base),
                    current_price=evidence.price,
                    available_including_current=capacity,
                    authoritative_ready=True,
                    entry_evidence=entry,
                )
                if updated.state is not ProtectionState.WAITING_ENTRY:
                    await _validate_market_setup(session, updated, evidence)
                    # Install only a fully prepared revision. The savepoint keeps
                    # the previous protection intact if any prerequisite fails.
                    updated = replace(updated, state=ProtectionState.ARMED)
            current = await save(
                session,
                current,
                updated,
                kind=row.action,
                # Explicit repair/cancel supersedes unsent late-entry work. An
                # EXITING group remains uneditable, so sent exits are untouched.
                extra_exit=Quantity.of(0, value.prices.pair.base),
            )
            await reconcile_allocations(
                session, row.episode_id, value.prices.pair, allow_clear=True
            )
        result = {
            "protection_id": str(current.value.protection_id),
            "revision": current.value.revision,
        }
    except (OrderError, MoneyError, ValueError, KeyError, TypeError) as error:
        await session.execute("ROLLBACK TO SAVEPOINT protection_request")
        if row.action == "REPLACE" and isinstance(
            error, (SourceUnavailableError, SafetyUnavailableError)
        ):
            now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            decision = decide_setup_result(
                origin=OrderOrigin.MANUAL,
                attempt=progress.attempt,
                outcome=SetupOutcome.TRANSIENT_FAILURE,
                observed_at=now,
            )
            if decision.action is SetupAction.RETRY:
                await session.execute("RELEASE SAVEPOINT protection_request")
                await session.execute(
                    """UPDATE paper_protection_request_progress
                    SET attempt=:attempt,next_attempt_at=:due WHERE request_id=:id""",
                    {"id": request_id, "attempt": decision.next_attempt, "due": decision.due_at},
                )
                return
        failure = (
            error.code
            if isinstance(error, OrderError)
            and error.code in ("ORDER_INPUT_INVALID", "ORDER_CONFLICT", "ORDER_SAFETY_UNAVAILABLE")
            else "ORDER_SAFETY_UNAVAILABLE"
        )
    await session.execute("RELEASE SAVEPOINT protection_request")
    await session.execute(
        """INSERT INTO paper_protection_results
        (request_id,user_id,episode_id,state,failure_code,snapshot,protection_id,revision)
        VALUES(:id,:owner,:episode,:state,:failure,CAST(:snapshot AS jsonb),:group,:revision)""",
        {
            "id": row.id,
            "owner": session.user_id,
            "episode": row.episode_id,
            "state": "APPLIED" if failure is None else "REJECTED",
            "failure": failure,
            "snapshot": canonical(result),
            "group": UUID(str(result["protection_id"])) if result else None,
            "revision": result.get("revision"),
        },
    )
    if failure is not None:
        await audit(
            session,
            value=None,
            episode_id=row.episode_id,
            protection_id=row.protection_id,
            event_id=row.id,
            kind="REJECT",
        )


async def reconcile_allocations(
    session: UserSession, episode_id: UUID, pair: PositionPair, *, allow_clear: bool = False
) -> None:
    """Retain instructions on source corrections; never choose a group to cut."""
    from tiewtrade.infra.positions import read_effective_executions

    tracked_groups = await groups(session, episode_id, pair, include_closed=True)
    if not tracked_groups:
        return
    try:
        held, reserved = await held_and_reserved(session, episode_id, pair)
        total = await allocated(session, episode_id, pair)
        unsafe = reserved + total > held
        facts = await read_effective_executions(session, episode_id, pair)
    except (OrderError, MoneyError, ValueError):
        for group in tracked_groups:
            if not group.value.conflicted:
                await save(
                    session,
                    group,
                    replace(group.value, conflicted=True, revision=group.value.revision + 1),
                    kind="CONFLICT",
                    failure_code="ORDER_CONFLICT",
                )
        return
    for group in tracked_groups:
        # Re-fold effective exit facts, including terminal exits. Corrections do
        # not call record_fill and must not leave a CLOSED group hiding exposure.
        exits = (
            await session.execute(
                """SELECT x.id,x.order_id,s.accounted FROM paper_protection_exits x
                JOIN paper_protection_exit_progress s ON s.id=x.id
                WHERE x.protection_id=:group""",
                {"group": group.value.protection_id},
            )
        ).all()
        exit_quantity_delta = Quantity.of(0, pair.base)
        for exit_row in exits:
            exit_facts = await _effective_order_executions(
                session, episode_id, exit_row.order_id, facts
            )
            effective = Quantity.of(0, pair.base)
            for fact in exit_facts:
                if fact.side is ExecutionSide.SELL:
                    effective += fact.gross_quantity
            accounted = Quantity.of(exit_row.accounted, pair.base)
            exit_quantity_delta += accounted - effective
            if effective != accounted:
                await session.execute(
                    "UPDATE paper_protection_exit_progress SET accounted=:quantity WHERE id=:id",
                    {"id": exit_row.id, "quantity": effective.as_parts()["quantity"]},
                )
        remaining = max(group.value.quantity + exit_quantity_delta, Quantity.of(0, pair.base))
        disposed = group.disposed - exit_quantity_delta
        acquired = group.acquired
        if group.value.entry_order_id is not None:
            entry_facts = await _effective_order_executions(
                session, episode_id, group.value.entry_order_id, facts
            )
            acquired = Quantity.of(0, pair.base)
            for fact in entry_facts:
                if fact.side is ExecutionSide.BUY:
                    acquired += apply_execution(
                        PositionState.empty(pair), replace(fact, source_sequence=1)
                    ).base_delta
        cap = max(acquired - disposed, Quantity.of(0, pair.base))
        own_unsafe = group.value.entry_order_id is not None and remaining > cap
        changed_source = acquired != group.acquired or exit_quantity_delta.amount != 0
        conflict = unsafe or own_unsafe or (changed_source and not allow_clear)
        if not allow_clear:
            conflict = conflict or group.value.conflicted
        if conflict != group.value.conflicted or changed_source:
            await save(
                session,
                group,
                replace(
                    group.value,
                    quantity=remaining,
                    state=ProtectionState.FAILED
                    if group.value.state is ProtectionState.CLOSED and remaining.amount > 0
                    else group.value.state,
                    conflicted=conflict,
                    revision=group.value.revision + 1,
                ),
                acquired=acquired,
                disposed=disposed,
                extra_exit=min(group.extra_exit, remaining),
                kind="CONFLICT",
                failure_code="ORDER_CONFLICT" if conflict else None,
            )
