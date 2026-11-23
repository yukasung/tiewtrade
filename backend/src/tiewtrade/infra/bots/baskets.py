"""F-21 execution projections and guards under the existing financial owner lock."""

import json
from dataclasses import replace
from datetime import datetime
from typing import Any
from uuid import UUID, uuid5

from tiewtrade.core.basket_disposals import SelectedEntry, fifo_disposals
from tiewtrade.core.market_data import Timeframe, advance, align_floor
from tiewtrade.core.money import Money, Quantity, RoundingDirection, price_for_notional
from tiewtrade.core.orders import OrderConflictError, OrderIntent, OrderType, QuoteBudget
from tiewtrade.core.positions import ExecutionFact, ExecutionSide, PositionState, apply_execution
from tiewtrade.core.strategies import document_from_payload
from tiewtrade.core.strategy_config import (
    CANDLE_STRATEGIES,
    PAPER_TEST_STRATEGY,
    decode_strategy_config,
)
from tiewtrade.infra.db.session import UserSession

_OPEN_ENTRY = """(e.quantity>0 OR
    (coalesce(p.status,'') NOT IN ('FILLED','CANCELED','EXPIRED','REJECTED')
      AND coalesce(c.state,'')<>'REJECTED'))"""


async def signal_exit_guarded(
    session: UserSession, run_id: UUID, opened: datetime, timeframe: Timeframe
) -> bool:
    """The closed signal A and its entry slot B share the existing exit guard."""
    return bool(
        (
            await session.execute(
                "SELECT EXISTS(SELECT 1 FROM bot_strategy_exit_guards WHERE run_id=:run "
                "AND candle_open_at IN (:signal,:entry))",
                {"run": run_id, "signal": opened, "entry": advance(opened, timeframe, 1)},
            )
        ).scalar_one()
    )


async def open_entry_order_ids(session: UserSession, basket_id: UUID) -> tuple[UUID, ...]:
    rows = (
        await session.execute(
            "SELECT e.order_id FROM bot_strategy_entries e "
            "LEFT JOIN paper_order_projections p ON p.order_id=e.order_id "
            "LEFT JOIN paper_order_command_results c ON c.command_id=e.command_id "
            "WHERE e.basket_id=:basket AND " + _OPEN_ENTRY + " ORDER BY e.entry_sequence",
            {"basket": basket_id},
        )
    ).all()
    return tuple(UUID(str(row.order_id)) for row in rows)


async def register_entry(
    session: UserSession,
    *,
    run_id: UUID,
    command_id: UUID,
    intent: OrderIntent,
    provenance: dict[str, str | int] | None,
) -> None:
    run = (await session.execute("SELECT * FROM bot_runs WHERE id=:run", {"run": run_id})).one()
    if run.strategy_name not in CANDLE_STRATEGIES:
        return
    if provenance is None or not all(
        key in provenance for key in ("candle_open_at", "signal_atr", "guard_revision")
    ):
        raise OrderConflictError("F-21 entry provenance required")
    config = decode_strategy_config(
        run.strategy_name, document_from_payload(run.configuration, expected_version=1)
    )
    if (
        intent.pair != config.pair
        or intent.side is not ExecutionSide.BUY
        or intent.kind is not OrderType.MARKET
        or not isinstance(intent.size, QuoteBudget)
        or intent.size.amount != config.capital_per_entry
    ):
        raise OrderConflictError("entry intent differs from pinned strategy configuration")
    order_id = intent.order_id
    progress = (
        await session.execute(
            "SELECT guard_revision,reconciliation_required,recovery_required "
            "FROM bot_strategy_progress "
            "WHERE run_id=:run",
            {"run": run_id},
        )
    ).one()
    start = datetime.fromisoformat(str(provenance["candle_open_at"]))
    exited = await signal_exit_guarded(session, run_id, start, config.timeframe)
    if (
        progress.reconciliation_required
        or progress.recovery_required
        or progress.guard_revision != provenance["guard_revision"]
        or exited
    ):
        raise OrderConflictError("exit guard changed before entry commit")
    await finish_empty_baskets(session, run_id)
    basket = (
        await session.execute(
            "SELECT * FROM bot_strategy_baskets WHERE run_id=:run AND status<>'CLOSED' FOR UPDATE",
            {"run": run_id},
        )
    ).one_or_none()
    if basket is None:
        basket_id = uuid5(order_id, "basket")
        await session.execute(
            """INSERT INTO bot_strategy_baskets
          (id,user_id,run_id,mode,episode_id,base,quote,timeframe)
          VALUES(:id,:owner,:run,'PAPER',:episode,:base,:quote,:timeframe)""",
            {
                "id": basket_id,
                "owner": session.user_id,
                "run": run_id,
                "episode": run.episode_id,
                "base": config.pair.base,
                "quote": config.pair.quote,
                "timeframe": config.timeframe.value,
            },
        )
    else:
        if basket.status != "OPEN" or basket.reconciliation_required:
            raise OrderConflictError("basket is not available for opening")
        basket_id = UUID(str(basket.id))
    sequence = int(
        (
            await session.execute(
                "SELECT coalesce(max(entry_sequence),0)+1 FROM bot_strategy_entries "
                "WHERE basket_id=:basket",
                {"basket": basket_id},
            )
        ).scalar_one()
    )
    occupied = len(await open_entry_order_ids(session, basket_id))
    if occupied >= config.max_entries:
        raise OrderConflictError("entry count is full")
    atr = Money.of(str(provenance["signal_atr"]), config.pair.quote)
    if atr.amount < 0:
        raise OrderConflictError("invalid signal ATR")
    await session.execute(
        """INSERT INTO bot_strategy_entries
      (order_id,command_id,user_id,mode,episode_id,run_id,basket_id,entry_sequence,atr,signal_open_at)
      VALUES(:order,:command,:owner,'PAPER',:episode,:run,:basket,:sequence,:atr,:start)""",
        {
            "order": order_id,
            "command": command_id,
            "owner": session.user_id,
            "episode": run.episode_id,
            "run": run_id,
            "basket": basket_id,
            "sequence": sequence,
            "atr": atr.as_parts()["amount"],
            "start": start,
        },
    )
    if run.strategy_name == PAPER_TEST_STRATEGY:
        await session.execute(
            """INSERT INTO bot_test_entry_anchors
            (order_id,command_id,run_id,user_id,mode,episode_id,atr)
            VALUES(:order,:command,:run,:owner,'PAPER',:episode,:atr)""",
            {
                "order": order_id,
                "command": command_id,
                "run": run_id,
                "owner": session.user_id,
                "episode": run.episode_id,
                "atr": atr.as_parts()["amount"],
            },
        )


async def finish_empty_baskets(session: UserSession, run_id: UUID) -> None:
    await session.execute(
        """UPDATE bot_strategy_baskets b SET status='CLOSED',revision=revision+1
      WHERE b.run_id=:run AND b.status<>'CLOSED' AND NOT b.reconciliation_required
      AND NOT EXISTS(SELECT 1 FROM bot_strategy_progress p
        WHERE p.run_id=b.run_id AND p.reconciliation_required)
      AND NOT EXISTS(SELECT 1 FROM bot_strategy_entries e
        JOIN paper_protections p ON p.entry_order_id=e.order_id
        JOIN paper_protection_exits x ON x.protection_id=p.id
        JOIN paper_protection_exit_progress s ON s.id=x.id
        WHERE e.basket_id=b.id AND NOT s.settled)
      AND NOT EXISTS (
        SELECT 1 FROM bot_strategy_entries e
        LEFT JOIN paper_order_projections p ON p.order_id=e.order_id
        LEFT JOIN paper_order_command_results c ON c.command_id=e.command_id
        WHERE e.basket_id=b.id AND """
        + _OPEN_ENTRY
        + ")",
        {"run": run_id},
    )


async def _receipt(
    session: UserSession, run: Any, order_id: UUID, fact: ExecutionFact, details: dict[str, object]
) -> None:
    await session.execute(
        """INSERT INTO bot_strategy_execution_receipts
      (execution_id,user_id,run_id,mode,episode_id,order_id,details)
      VALUES(:execution,:owner,:run,'PAPER',:episode,:order,CAST(:details AS jsonb))""",
        {
            "execution": fact.execution_id,
            "owner": session.user_id,
            "run": run.run_id,
            "episode": run.episode_id,
            "order": order_id,
            "details": json.dumps(details),
        },
    )


async def _seen(session: UserSession, run_id: UUID, fact: ExecutionFact) -> bool:
    return bool(
        (
            await session.execute(
                "SELECT EXISTS(SELECT 1 FROM bot_strategy_execution_receipts "
                "WHERE run_id=:run AND execution_id=:id)",
                {"run": run_id, "id": fact.execution_id},
            )
        ).scalar_one()
    )


async def record_execution(
    session: UserSession,
    order_id: UUID,
    fact: ExecutionFact,
) -> tuple[UUID, ...]:
    """Return affected baskets; caller atomically installs their protection targets."""
    if fact.side is ExecutionSide.BUY:
        entry = (
            await session.execute(
                "SELECT * FROM bot_strategy_entries WHERE order_id=:order FOR UPDATE",
                {"order": order_id},
            )
        ).one_or_none()
        if entry is None or await _seen(session, entry.run_id, fact):
            return ()
        delta = apply_execution(
            PositionState.empty(fact.pair), replace(fact, source_sequence=1)
        ).base_delta
        gross = Quantity.of(entry.gross_quantity, fact.pair.base) + fact.gross_quantity
        notional = Money.of(entry.gross_notional, fact.pair.quote) + fact.quote_amount
        price = price_for_notional(
            notional, gross, asset=fact.pair.base, rounding=RoundingDirection.TOWARD_NEGATIVE
        )
        quantity = Quantity.of(entry.quantity, fact.pair.base) + delta
        await session.execute(
            """UPDATE bot_strategy_entries SET quantity=:quantity,price=:price,
          gross_quantity=:gross,gross_notional=:notional,filled_at=coalesce(filled_at,:at)
          WHERE order_id=:order""",
            {
                "quantity": quantity.as_parts()["quantity"],
                "price": price.as_parts()["amount"],
                "gross": gross.as_parts()["quantity"],
                "notional": notional.as_parts()["amount"],
                "at": fact.occurred_at,
                "order": order_id,
            },
        )
        await _receipt(session, entry, order_id, fact, {"side": "BUY"})
        return (UUID(str(entry.basket_id)),)

    # Protection-generated SELL has a precise entry identity. Manual SELL uses
    # only the selected allocations, attributed FIFO by the approved amendment.
    linked = (
        await session.execute(
            """SELECT e.* FROM paper_protection_exits x
      JOIN paper_protections p ON p.id=x.protection_id
      JOIN bot_strategy_entries e ON e.order_id=p.entry_order_id WHERE x.order_id=:order""",
            {"order": order_id},
        )
    ).one_or_none()
    selections: dict[UUID, Quantity] = {}
    mixed_selection = False
    if linked is not None:
        entries = [linked]
        selections[UUID(str(linked.order_id))] = Quantity.of(linked.quantity, fact.pair.base)
    else:
        raw = (
            await session.execute(
                "SELECT protection_allocations FROM paper_order_requests WHERE "
                "order_id=:order AND action='NEW'",
                {"order": order_id},
            )
        ).scalar_one_or_none()
        entries = []
        for selection in raw or []:
            entry = (
                await session.execute(
                    """SELECT e.* FROM paper_protections p
              JOIN bot_strategy_entries e ON e.order_id=p.entry_order_id WHERE p.id=:id""",
                    {"id": UUID(selection["protection_id"])},
                )
            ).one_or_none()
            if entry is not None:
                entries.append(entry)
                selections[UUID(str(entry.order_id))] = Quantity.of(
                    selection["quantity"], fact.pair.base
                )
            else:
                mixed_selection = True
    runs = {UUID(str(entry.run_id)): entry for entry in entries}
    if not entries:
        # Never guess attribution for unselected/unprotected inventory. Persist
        # a reconciliation requirement rather than silently moving entry costs.
        baskets = (
            await session.execute(
                """SELECT id,run_id,episode_id,timeframe FROM bot_strategy_baskets
          WHERE episode_id=(SELECT episode_id FROM paper_orders WHERE id=:order)
            AND base=:base AND quote=:quote AND status<>'CLOSED' FOR UPDATE""",
                {"order": order_id, "base": fact.pair.base, "quote": fact.pair.quote},
            )
        ).all()
        for basket in baskets:
            if await _seen(session, basket.run_id, fact):
                continue
            linked_quantities = (
                await session.execute(
                    "SELECT e.quantity,p.quantity AS protected,p.state "
                    "FROM bot_strategy_entries e LEFT JOIN paper_protections p "
                    "ON p.entry_order_id=e.order_id WHERE e.basket_id=:id AND e.quantity>0",
                    {"id": basket.id},
                )
            ).all()
            if all(
                item.protected is not None
                and item.state not in ("CLOSED", "CANCELED")
                and not Quantity.of(item.protected, fact.pair.base)
                < Quantity.of(item.quantity, fact.pair.base)
                for item in linked_quantities
            ):
                # Common admission cannot sell allocated F-21 inventory without
                # selecting it. This disposal belongs to other free holdings.
                continue
            await session.execute(
                "UPDATE bot_strategy_baskets SET "
                "reconciliation_required=true,revision=revision+1 WHERE id=:id",
                {"id": basket.id},
            )
            await session.execute(
                "UPDATE bot_strategy_progress SET reconciliation_required=true WHERE run_id=:id",
                {"id": basket.run_id},
            )
            await _guard(
                session, basket.run_id, basket.episode_id, Timeframe(basket.timeframe), fact
            )
            await _receipt(session, basket, order_id, fact, {"side": "SELL", "unattributed": True})
        return ()
    if len(runs) != 1:
        raise OrderConflictError("manual disposal crosses strategy runs")
    run_id, run = next(iter(runs.items()))
    if await _seen(session, run_id, fact):
        return ()
    if mixed_selection:
        # No common approved FIFO numbering exists for F-21 and manual groups.
        # Preserve the financial fact, but never guess which cost basis survived.
        await invalidate_execution_selection(session, run_id, order_id, fact, run)
        return ()
    prior = (
        (
            await session.execute(
                "SELECT details FROM bot_strategy_execution_receipts WHERE "
                "run_id=:run AND order_id=:order",
                {"run": run_id, "order": order_id},
            )
        )
        .scalars()
        .all()
    )
    for receipt in prior:
        for disposal in receipt.get("disposals", []):
            identity = UUID(disposal["entry"])
            if identity in selections and linked is None:
                selections[identity] -= Quantity.of(disposal["quantity"], fact.pair.base)
    changes = fifo_disposals(
        tuple(
            SelectedEntry(
                UUID(str(entry.order_id)),
                entry.entry_sequence,
                Quantity.of(entry.quantity, fact.pair.base),
                selections[UUID(str(entry.order_id))],
            )
            for entry in entries
        ),
        fact.gross_quantity,
    )
    total = Quantity.of(0, fact.pair.base)
    details = []
    for identity, quantity in changes:
        total += quantity
        entry = next(value for value in entries if value.order_id == identity)
        remaining = Quantity.of(entry.quantity, fact.pair.base) - quantity
        await session.execute(
            "UPDATE bot_strategy_entries SET quantity=:quantity WHERE order_id=:order",
            {"quantity": remaining.as_parts()["quantity"], "order": identity},
        )
        details.append({"entry": str(identity), "quantity": quantity.as_parts()["quantity"]})
    ids = tuple({UUID(str(entry.basket_id)) for entry in entries})
    basket = (
        await session.execute(
            "SELECT * FROM bot_strategy_baskets WHERE id=:id FOR UPDATE", {"id": ids[0]}
        )
    ).one()
    if total != fact.gross_quantity:
        await session.execute(
            "UPDATE bot_strategy_baskets SET "
            "reconciliation_required=true,revision=revision+1 WHERE id=:id",
            {"id": basket.id},
        )
    await _guard(session, run_id, run.episode_id, Timeframe(basket.timeframe), fact)
    await _receipt(session, run, order_id, fact, {"side": "SELL", "disposals": details})
    return ids


async def invalidate_execution_selection(
    session: UserSession, run_id: UUID, order_id: UUID, fact: ExecutionFact, run: Any
) -> None:
    await session.execute(
        "UPDATE bot_strategy_progress SET reconciliation_required=true WHERE run_id=:run",
        {"run": run_id},
    )
    baskets = (
        await session.execute(
            "UPDATE bot_strategy_baskets SET reconciliation_required=true,revision=revision+1 "
            "WHERE run_id=:run AND status<>'CLOSED' RETURNING timeframe",
            {"run": run_id},
        )
    ).all()
    for basket in baskets:
        await _guard(session, run_id, run.episode_id, Timeframe(basket.timeframe), fact)
    await _receipt(session, run, order_id, fact, {"side": "SELL", "unattributed": True})


async def _guard(
    session: UserSession, run_id: UUID, episode_id: UUID, timeframe: Timeframe, fact: ExecutionFact
) -> None:
    inserted = (
        await session.execute(
            """INSERT INTO bot_strategy_exit_guards
      (execution_id,user_id,run_id,mode,episode_id,candle_open_at,occurred_at)
      VALUES(:id,:owner,:run,'PAPER',:episode,:candle,:at)
      ON CONFLICT(run_id,execution_id) DO NOTHING RETURNING execution_id""",
            {
                "id": fact.execution_id,
                "owner": session.user_id,
                "run": run_id,
                "episode": episode_id,
                "candle": align_floor(fact.occurred_at, timeframe),
                "at": fact.occurred_at,
            },
        )
    ).scalar_one_or_none()
    if inserted is not None:
        await session.execute(
            "UPDATE bot_strategy_progress SET guard_revision=guard_revision+1 WHERE run_id=:run",
            {"run": run_id},
        )


async def invalidate_execution(session: UserSession, execution_id: UUID) -> None:
    """Corrections cannot reuse original entry costs, even for a closed basket."""
    if (
        await session.execute("SELECT to_regclass('public.bot_strategy_execution_receipts')")
    ).scalar_one_or_none() is None:
        return
    await session.execute(
        """UPDATE bot_strategy_progress SET reconciliation_required=true
        WHERE run_id IN (SELECT run_id FROM bot_strategy_execution_receipts
          WHERE execution_id=:execution)""",
        {"execution": execution_id},
    )

    await session.execute(
        """UPDATE bot_strategy_baskets SET reconciliation_required=true,revision=revision+1
        WHERE NOT reconciliation_required AND run_id IN (
          SELECT run_id FROM bot_strategy_execution_receipts WHERE execution_id=:execution)""",
        {"execution": execution_id},
    )


async def strategy_managed_protection(session: UserSession, protection_id: UUID) -> bool:
    """Read membership under owner RLS; clients cannot select management policy."""
    if (
        await session.execute("SELECT to_regclass('public.bot_strategy_entries')")
    ).scalar_one_or_none() is None:
        return False
    return bool(
        (
            await session.execute(
                "SELECT EXISTS(SELECT 1 FROM paper_protections p "
                "JOIN bot_strategy_entries e ON e.order_id=p.entry_order_id WHERE p.id=:id)",
                {"id": protection_id},
            )
        ).scalar_one()
    )
