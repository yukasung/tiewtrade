"""Fenced Paper protection decisions, always inside the financial writer transaction."""

from dataclasses import replace
from datetime import datetime
from typing import Any
from uuid import UUID, uuid5

from tiewtrade.core.money import Money, MoneyError, Quantity, basket_take_profit
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
    EntryAtrProtection,
    ManualSaleAllocation,
    Protection,
    ProtectionLeg,
    ProtectionPrices,
    ProtectionState,
    SetupAction,
    SetupOutcome,
    TriggerEvidence,
    cancel_protection,
    decide_setup_result,
    evaluate_trigger,
    executable_protection_quantity,
    prepare_manual_sale,
    replace_protection,
)
from tiewtrade.core.realtime_prices import Readiness, readiness
from tiewtrade.core.strategy_config import PAPER_TEST_STRATEGY
from tiewtrade.infra.bots.baskets import (
    finish_empty_baskets,
    open_entry_order_ids,
    record_execution,
)
from tiewtrade.infra.bots.system_stop import stop_for_protection_failure
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.market_data.order_book_codec import canonical
from tiewtrade.infra.market_data.order_book_storage import read_latest_book
from tiewtrade.infra.market_data.realtime_storage import read_snapshot
from tiewtrade.infra.paper_orders.codec import object_payload
from tiewtrade.infra.paper_orders.dispatch import submit_cancel, submit_order
from tiewtrade.infra.paper_orders.requests import ManualRequest, decode_request, wallet_lock
from tiewtrade.infra.positions.views import held_and_reserved
from tiewtrade.infra.protections.entry_anchor import resolve_first_fill
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
    session: UserSession,
    value: Protection,
    evidence: TriggerEvidence,
    *,
    quantity: Quantity | None = None,
) -> Quantity:
    source = await read_latest_book(session, value.prices.pair)
    return executable_protection_quantity(
        value,
        source.metadata.market,
        evidence,
        filter_reference_price=source.metadata.average_price,
        quantity=quantity,
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


async def bot_bracket(
    session: UserSession, intent: OrderIntent, command_id: UUID
) -> ProtectionPrices | None:
    if intent.origin is not OrderOrigin.BOT or intent.side is not ExecutionSide.BUY:
        return None
    result = await session.execute(
        """SELECT bracket FROM bot_order_links WHERE command_id=:id AND order_id=:order
           AND user_id=:owner AND episode_id=:episode""",
        {
            "id": command_id,
            "order": intent.order_id,
            "owner": session.user_id,
            "episode": intent.scope.episode_id,
        },
    )
    bracket = result.scalar_one_or_none()
    if bracket is None:
        return None
    payload = object_payload(bracket)
    if payload.get("kind") == "ATR_FIRST_FILL":
        if (
            payload.keys() != {"version", "kind", "atr"}
            or type(payload["version"]) is not int
            or payload["version"] != 1
        ):
            raise OrderConflictError("invalid anchored protection instruction")
        anchor = (
            await session.execute(
                (
                    "SELECT atr FROM bot_test_entry_anchors WHERE order_id=:order AND "
                    "command_id=:command"
                ),
                {"order": intent.order_id, "command": command_id},
            )
        ).scalar_one_or_none()
        if anchor is None or Money.of(anchor, intent.pair.quote) != Money.of(
            payload["atr"], intent.pair.quote
        ):
            raise OrderConflictError("anchored protection provenance differs")
        evidence = await market_evidence(session, intent.pair)
        tick = (await read_latest_book(session, intent.pair)).metadata.market.price_tick
        return EntryAtrProtection(intent.pair, Money.of(anchor, intent.pair.quote)).resolve(
            evidence.price, tick
        )
    return prices(intent.pair, payload)


async def linked_protection_exit(
    session: UserSession, intent: OrderIntent, command_id: UUID
) -> UUID | None:
    """Identify the immutable F-17 authority for this exact reducing command."""
    if intent.side is not ExecutionSide.SELL or not isinstance(intent.size, BaseSize):
        return None
    result = await session.execute(
        """SELECT protection_id FROM paper_protection_exits
        WHERE command_id=:command AND order_id=:order AND user_id=:owner
          AND episode_id=:episode AND quantity=:quantity""",
        {
            "command": command_id,
            "order": intent.order_id,
            "owner": session.user_id,
            "episode": intent.scope.episode_id,
            "quantity": intent.size.quantity.amount,
        },
    )
    value = result.scalar_one_or_none()
    return None if value is None else UUID(str(value))


async def prepare_admission(
    session: UserSession, intent: OrderIntent, wallet_id: UUID, command_id: UUID, held: Quantity
) -> tuple[Quantity, tuple[tuple[StoredProtection, Protection], ...]]:
    request = await manual_request(session, command_id)
    levels = await bot_bracket(session, intent, command_id)
    if request is not None and request.protection is not None:
        levels = prices(intent.pair, request.protection)
    selections = () if request is None else request.protection_allocations
    if (levels is not None or selections) and not await enabled(session):
        raise SafetyUnavailableError("protection protocol unavailable")
    if levels is not None:
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
    levels = await bot_bracket(session, intent, command_id)
    if request is not None and request.protection is not None:
        levels = prices(intent.pair, request.protection)
    if levels is not None:
        manual_id = None if request is None else request.request_id
        group = Protection(
            uuid5(command_id if manual_id is None else manual_id, "bracket"),
            intent.scope,
            intent.origin,
            levels,
            Quantity.of(0, intent.pair.base),
            ProtectionState.WAITING_ENTRY,
            entry_order_id=intent.order_id,
        )
        await create(
            session,
            group,
            wallet_id,
            entry_request_id=manual_id,
            entry_bot_command_id=command_id if manual_id is None else None,
        )


async def _record_fill(session: UserSession, order_id: UUID, fact: ExecutionFact) -> None:
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
        if value.setup_failed_exit and value.state is ProtectionState.FAILED:
            await save(
                session,
                group,
                replace(value, quantity=value.quantity + delta, revision=value.revision + 1),
                kind="FILL",
                acquired=group.acquired + delta,
                failure_code=group.failure_code,
            )
            return
        triggered = value.trigger is not None or value.setup_failed_exit
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


async def _close_after_bot_setup_failure(
    session: UserSession,
    group: StoredProtection,
    *,
    reason: str,
    permanent: bool,
) -> None:
    value = group.value
    if value.entry_order_id is None:
        raise OrderConflictError("BOT protection failure requires an entry order")
    await stop_for_protection_failure(
        session, entry_order_id=value.entry_order_id, protection_id=value.protection_id
    )
    # Keep a durable close allocation until the same F-17 market checks can
    # size it. Permanent filter failures leave exposure visible for the owner.
    await save(
        session,
        group,
        replace(
            value,
            revision=value.revision + 1,
            state=ProtectionState.FAILED if permanent else ProtectionState.EXITING,
            setup_due_at=None,
            setup_failed_exit=True,
        ),
        kind="FAIL",
        extra_exit=Quantity.of(0, value.prices.pair.base) if permanent else value.quantity,
        failure_code=reason,
    )


async def record_fill(
    session: UserSession,
    order_id: UUID,
    fact: ExecutionFact,
    *,
    tick: Money | None = None,
) -> None:
    anchor_failed = await resolve_first_fill(session, order_id, fact, tick)
    await _record_fill(session, order_id, fact)
    if anchor_failed:
        failed_row = (
            await session.execute(
                "SELECT id FROM paper_protections WHERE entry_order_id=:order", {"order": order_id}
            )
        ).one()
        group = await load(session, failed_row.id)
        assert group is not None
        await _close_after_bot_setup_failure(
            session, group, reason="PROTECTION_SETUP_REJECTED", permanent=True
        )
    if (
        await session.execute("SELECT to_regclass('public.bot_strategy_entries')")
    ).scalar_one_or_none() is None:
        return
    for basket_id in await record_execution(session, order_id, fact):
        await synchronize_basket(session, basket_id, tick=tick)
        if fact.side is ExecutionSide.BUY:
            row = (
                await session.execute(
                    "SELECT id FROM paper_protections WHERE entry_order_id=:order",
                    {"order": order_id},
                )
            ).one_or_none()
            if row is not None:
                group = await load(session, row.id)
                assert group is not None
                await _adopt_basket_trigger(session, basket_id, group)


async def synchronize_basket(
    session: UserSession, basket_id: UUID, *, tick: Money | None = None
) -> None:
    """Called inside the fill transaction: all allocations share one revision."""
    basket = (
        await session.execute(
            "SELECT b.*,r.strategy_name,p.reconciliation_required AS run_reconciliation_required "
            "FROM bot_strategy_baskets b JOIN bot_runs r ON r.id=b.run_id JOIN "
            "bot_strategy_progress p ON p.run_id=b.run_id "
            "WHERE b.id=:id FOR UPDATE OF b",
            {"id": basket_id},
        )
    ).one()
    if (
        basket.strategy_name == PAPER_TEST_STRATEGY
        or basket.reconciliation_required
        or basket.run_reconciliation_required
        or basket.status == "CLOSED"
    ):
        return
    entries = (
        await session.execute(
            """SELECT * FROM bot_strategy_entries
      WHERE basket_id=:id AND quantity>0 ORDER BY filled_at,entry_sequence""",
            {"id": basket_id},
        )
    ).all()
    if not entries:
        return
    pair = PositionPair(basket.base, basket.quote)
    if tick is None and basket.price_tick is not None:
        tick = Money.of(basket.price_tick, basket.quote)
    if tick is None:
        source = await read_latest_book(session, pair)
        tick = source.metadata.market.price_tick
    await session.execute(
        "UPDATE bot_strategy_baskets SET price_tick=:tick WHERE id=:id",
        {"tick": tick.as_parts()["amount"], "id": basket_id},
    )
    held = None if basket.target is None else Money.of(basket.target, pair.quote)
    target = (
        held
        if basket.status == "TRIGGERED"
        else basket_take_profit(
            tuple(
                (Money.of(entry.price, pair.quote), Quantity.of(entry.quantity, pair.base))
                for entry in entries
            ),
            Money.of(entries[-1].atr, pair.quote),
            tick,
            held=held,
            entry_costs=tuple(
                (
                    Money.of(entry.gross_notional, pair.quote),
                    Quantity.of(entry.gross_quantity, pair.base),
                )
                for entry in entries
            ),
        )
    )
    if target is None:
        raise OrderConflictError("triggered basket has no held target")
    for entry in entries:
        row = (
            await session.execute(
                "SELECT id FROM paper_protections WHERE entry_order_id=:order",
                {"order": entry.order_id},
            )
        ).one_or_none()
        if row is None:
            raise OrderConflictError("basket entry has no protection allocation")
        group = await load(session, row.id)
        assert group is not None
        value = group.value
        if value.state in (ProtectionState.CANCELED, ProtectionState.CLOSED):
            # An explicit manual release/cancel is never silently undone.
            continue
        if value.trigger is None and value.prices.take_profit != target:
            await save(
                session,
                group,
                replace(
                    value,
                    prices=ProtectionPrices(pair, take_profit=target),
                    revision=value.revision + 1,
                ),
                kind="REPLACE",
            )
        await session.execute(
            "UPDATE paper_protections SET "
            "observed_source=NULL,observed_generation=NULL,observed_sequence=NULL WHERE id=:id",
            {"id": row.id},
        )
    await session.execute(
        """UPDATE bot_strategy_baskets SET target=:target,
      target_revision=target_revision+1,revision=revision+1 WHERE id=:id""",
        {"id": basket_id, "target": target.as_parts()["amount"]},
    )


async def _basket_for_protection(session: UserSession, group: StoredProtection) -> UUID | None:
    if group.value.origin is not OrderOrigin.BOT or group.value.entry_order_id is None:
        return None
    if (
        await session.execute("SELECT to_regclass('public.bot_strategy_entries')")
    ).scalar_one_or_none() is None:
        return None
    value = (
        await session.execute(
            (
                "SELECT e.basket_id FROM bot_strategy_entries e JOIN bot_runs r ON "
                "r.id=e.run_id WHERE e.order_id=:order AND r.strategy_name<>:test"
            ),
            {"order": group.value.entry_order_id, "test": PAPER_TEST_STRATEGY},
        )
    ).scalar_one_or_none()
    return None if value is None else UUID(str(value))


def _basket_trigger_evidence(raw: dict[str, Any], pair: PositionPair) -> TriggerEvidence:
    return TriggerEvidence(
        UUID(raw["source"]),
        raw["generation"],
        raw["sequence"],
        Money.of(raw["price"], pair.quote),
        datetime.fromisoformat(raw["occurred_at"]),
        datetime.fromisoformat(raw["received_at"]),
        pair,
    )


async def _adopt_basket_trigger(
    session: UserSession,
    basket_id: UUID,
    group: StoredProtection,
    winning: TriggerEvidence | None = None,
) -> StoredProtection:
    value = group.value
    if (
        value.trigger is not None
        or value.quantity.amount == 0
        or value.conflicted
        or value.state not in (ProtectionState.ARMING, ProtectionState.ARMED)
    ):
        return group
    if winning is None:
        raw = (
            await session.execute(
                "SELECT t.evidence FROM bot_basket_triggers t "
                "JOIN bot_strategy_baskets b ON b.id=t.basket_id "
                "JOIN bot_strategy_progress p ON p.run_id=b.run_id "
                "WHERE b.id=:id AND b.status='TRIGGERED' "
                "AND NOT b.reconciliation_required AND NOT p.reconciliation_required",
                {"id": basket_id},
            )
        ).scalar_one_or_none()
        if raw is None:
            return group
        winning = _basket_trigger_evidence(raw, value.prices.pair)
    return await save(
        session,
        group,
        replace(
            value,
            state=ProtectionState.EXITING,
            winning_leg=ProtectionLeg.TAKE_PROFIT,
            trigger=winning,
            revision=value.revision + 1,
            setup_due_at=None,
        ),
        kind="TRIGGER",
        extra_exit=value.quantity,
    )


async def _executable_setup(
    session: UserSession, group: StoredProtection, evidence: TriggerEvidence
) -> Quantity | None:
    value = group.value
    if value.state is ProtectionState.ARMING:
        now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
        if value.setup_due_at is not None and now < value.setup_due_at:
            return None
    try:
        return await _validate_market_setup(session, value, evidence)
    except (SourceUnavailableError, SafetyUnavailableError):
        if value.state is not ProtectionState.ARMING:
            return None
        decision = decide_setup_result(
            origin=value.origin,
            attempt=value.setup_attempt,
            outcome=SetupOutcome.TRANSIENT_FAILURE,
            observed_at=now,
        )
        if decision.action is SetupAction.CLOSE_AND_STOP:
            await _close_after_bot_setup_failure(
                session, group, reason="PROTECTION_SETUP_UNAVAILABLE", permanent=False
            )
            return None
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
        return None
    except (OrderError, MoneyError):
        if value.origin is OrderOrigin.BOT and value.state is ProtectionState.ARMING:
            await _close_after_bot_setup_failure(
                session, group, reason="PROTECTION_SETUP_REJECTED", permanent=True
            )
            return None
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
            extra_exit=Quantity.of(0, value.prices.pair.base),
            failure_code="PROTECTION_SETUP_REJECTED",
        )
        return None


async def process_basket(
    session: UserSession, basket_id: UUID, current_evidence: TriggerEvidence
) -> bool:
    """Latch one TP observation and fan out all exit work atomically."""
    basket = (
        await session.execute(
            "SELECT b.*,p.reconciliation_required AS run_reconciliation_required "
            "FROM bot_strategy_baskets b JOIN bot_strategy_progress p ON p.run_id=b.run_id "
            "WHERE b.id=:id FOR UPDATE OF b",
            {"id": basket_id},
        )
    ).one()
    if (
        basket.status == "CLOSED"
        or basket.reconciliation_required
        or basket.run_reconciliation_required
        or basket.target is None
    ):
        return False
    pair = PositionPair(basket.base, basket.quote)
    target = Money.of(basket.target, pair.quote)
    if basket.status != "TRIGGERED" and current_evidence.price < target:
        return False
    rows = (
        await session.execute(
            "SELECT id FROM paper_protections WHERE entry_order_id=ANY(:orders) ORDER BY id",
            {"orders": list(await open_entry_order_ids(session, basket_id))},
        )
    ).all()
    groups_now = []
    for row in rows:
        group = await load(session, row.id)
        if group is not None:
            groups_now.append(group)
    trigger = (
        await session.execute(
            "SELECT evidence FROM bot_basket_triggers WHERE basket_id=:id", {"id": basket_id}
        )
    ).scalar_one_or_none()
    if trigger is None:
        # Keep the immutable winning evidence independent of subsequent quotes.
        trigger = {
            "source": str(current_evidence.source_id),
            "generation": current_evidence.generation,
            "sequence": current_evidence.sequence,
            "price": current_evidence.price.as_parts()["amount"],
            "occurred_at": current_evidence.occurred_at.isoformat(),
            "received_at": current_evidence.received_at.isoformat(),
        }
        await session.execute(
            """INSERT INTO bot_basket_triggers
          (id,basket_id,user_id,mode,episode_id,run_id,target_revision,evidence,membership)
          VALUES(:trigger,:basket,:owner,'PAPER',:episode,:run,:revision,
            CAST(:evidence AS jsonb),CAST(:members AS jsonb))""",
            {
                "trigger": uuid5(basket_id, "TP"),
                "basket": basket_id,
                "owner": session.user_id,
                "episode": basket.episode_id,
                "run": basket.run_id,
                "revision": basket.target_revision,
                "evidence": canonical(trigger),
                "members": canonical([str(group.value.protection_id) for group in groups_now]),
            },
        )
        await session.execute(
            "UPDATE bot_strategy_baskets SET status='TRIGGERED',revision=revision+1 WHERE id=:id",
            {"id": basket_id},
        )
    winning = _basket_trigger_evidence(trigger, pair)
    for group in groups_now:
        value = group.value
        if value.entry_order_id is not None:
            await submit_cancel(
                session,
                wallet_id=group.wallet_id,
                episode_id=value.scope.episode_id,
                order_id=value.entry_order_id,
                idempotency_key=uuid5(value.protection_id, "cancel-entry"),
            )
        if (
            value.state not in (ProtectionState.ARMING, ProtectionState.ARMED)
            or value.quantity.amount == 0
            or value.conflicted
        ):
            continue
        if value.prices.take_profit != target:
            raise OrderConflictError("basket protection target revision differs")
        # ARMED allocations retain durable EXITING work if the book is unavailable.
        # ARMING allocations must first pass the F-17 setup/retry policy.
        if value.state is ProtectionState.ARMED:
            group = await _adopt_basket_trigger(session, basket_id, group, winning)
        executable = await _executable_setup(session, group, current_evidence)
        if executable is None:
            continue
        if value.state is ProtectionState.ARMING:
            group = await _adopt_basket_trigger(session, basket_id, group, winning)
        value = group.value
        group = await save(
            session,
            group,
            replace(value, revision=value.revision + 1),
            kind="EXIT",
            extra_exit=Quantity.of(0, pair.base),
        )
        await queue_exit(session, group, executable)
    return True


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
    basket_id = await _basket_for_protection(session, group)
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
            try:
                evidence = await market_evidence(session, value.prices.pair)
                executable = await _validate_market_setup(
                    session, value, evidence, quantity=group.extra_exit
                )
            except (SourceUnavailableError, SafetyUnavailableError):
                return
            except (OrderError, MoneyError):
                # Carry late-fill dust while the entry can still fill. Never mix
                # it with the residual of a previously terminal exit.
                entry = (
                    await session.execute(
                        "SELECT status FROM paper_order_projections WHERE order_id=:order",
                        {"order": value.entry_order_id},
                    )
                ).scalar_one_or_none()
                if entry not in ("FILLED", "CANCELED", "EXPIRED", "REJECTED"):
                    return
                await save(
                    session,
                    group,
                    replace(value, state=ProtectionState.FAILED, revision=value.revision + 1),
                    kind="EXIT",
                    failure_code="PROTECTION_RESIDUAL",
                    extra_exit=Quantity.of(0, value.prices.pair.base),
                )
                return
            updated = await save(
                session,
                group,
                replace(value, revision=value.revision + 1),
                kind="EXIT",
                extra_exit=group.extra_exit - executable,
            )
            await queue_exit(session, updated, executable)
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
        if basket_id is not None:
            run_id = (
                await session.execute(
                    "SELECT run_id FROM bot_strategy_baskets WHERE id=:id", {"id": basket_id}
                )
            ).scalar_one()
            await finish_empty_baskets(session, UUID(str(run_id)))
        return
    if value.state is ProtectionState.WAITING_ENTRY:
        # Rejected/terminal-unfilled entry has no exposure to protect.
        row = (
            await session.execute(
                """SELECT p.status,r.state FROM paper_order_requests q
            LEFT JOIN paper_order_request_results t ON t.request_id=q.id
            LEFT JOIN paper_order_command_results r ON r.command_id=t.command_id
            LEFT JOIN paper_order_projections p ON p.order_id=q.order_id
            WHERE q.order_id=:entry AND q.action='NEW'
            UNION ALL
            SELECT p.status,r.state FROM bot_order_links b
            LEFT JOIN paper_order_command_results r ON r.command_id=b.command_id
            LEFT JOIN paper_order_projections p ON p.order_id=b.order_id
            WHERE b.order_id=:entry""",
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
    if basket_id is not None and await process_basket(session, basket_id, evidence):
        return
    exit_quantity = await _executable_setup(session, group, evidence)
    if exit_quantity is None:
        return
    if value.state is ProtectionState.ARMING:
        group = await save(
            session,
            group,
            replace(
                value, state=ProtectionState.ARMED, setup_due_at=None, revision=value.revision + 1
            ),
            kind="ARM",
        )
        value = group.value
    if basket_id is not None:
        return
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
        await queue_exit(session, group, exit_quantity)
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
                OrderScope(
                    UUID(str(session.user_id)), UUID(str(row.episode_id)), TradingMode.PAPER
                ),
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
                if await _basket_for_protection(session, current) is not None:
                    raise OrderConflictError("strategy-managed protection cannot be amended")
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
        if changed_source:
            basket_id = await _basket_for_protection(session, group)
            if basket_id is not None:
                await session.execute(
                    "UPDATE bot_strategy_baskets SET reconciliation_required=true,"
                    "revision=revision+1 WHERE id=:id AND NOT reconciliation_required",
                    {"id": basket_id},
                )
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
