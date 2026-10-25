"""Bulk projections retain exact reservations and isolate pair checkpoints."""

from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_dispatch import intent
from tests.infra.execution_market.test_worker import AllowPolicy
from tiewtrade.core.market_catalog import CatalogSnapshot
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import BaseSize, OrderConstraints, OrderScope, OrderType, TimeInForce
from tiewtrade.core.paper_matching import admit_order, cancel_order
from tiewtrade.core.positions import PositionPair
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_orders.dispatch import (
    DueOrder,
    claim_order,
    complete_command,
    finish_claim,
    reschedule_processed_orders,
    submit_cancel,
    submit_order,
)
from tiewtrade.infra.paper_orders.initialization import enable_financial_writer
from tiewtrade.infra.paper_orders.matching_storage import (
    insert_order_header,
    load_matching_state,
    persist_checkpoint,
)
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot


@pytest.mark.parametrize(
    "corruption",
    [
        None,
        ("paper_order_projections", "revision=revision+100"),
        ("paper_reservations", "revision=revision+100"),
        ("paper_reservations", "quote_reserved=1"),
        ("paper_reservations", "base_reserved=1"),
        ("paper_reservations", "revision=revision-1"),
    ],
)
async def test_bulk_checkpoint_preserves_other_pair_and_rebuilds_multiple_orders(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    corruption: tuple[str, str] | None,
) -> None:
    orders = []
    commands = []
    for sequence, base in enumerate(("BTC", "BTC", "ETH", "ETH"), start=1):
        pair = PositionPair(base, "USDT")
        value = replace(
            intent(owner, wallet.episode_id),
            pair=pair,
            kind=OrderType.LIMIT,
            size=BaseSize(Quantity.of(1, base)),
            limit_price=Money.of(100, "USDT"),
            time_in_force=TimeInForce.GTC,
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
            checkpoint = await load_matching_state(
                session, wallet_id=wallet.wallet_id, scope=value.scope, pair=pair
            )
            now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            state = admit_order(
                checkpoint.state,
                value,
                now=now,
                sequence=sequence,
                cash=Money.of(10000, "USDT"),
                held=Quantity.of(0, base),
                constraints=OrderConstraints(
                    pair,
                    "bulk-fixture-v1",
                    Quantity.of("0.01", base),
                    Quantity.of("0.01", base),
                    Money.of("0.01", "USDT"),
                    Money.of("0.01", "USDT"),
                ),
                reference_price=Money.of(100, "USDT"),
                policy=AllowPolicy(),
                catalog=CatalogSnapshot(1, frozenset({(base, "USDT")})),
            )
            await insert_order_header(
                session,
                wallet_id=wallet.wallet_id,
                command_id=command.command_id,
                order=state.orders[-1],
            )
            await persist_checkpoint(
                session,
                wallet_id=wallet.wallet_id,
                state=state,
                anchor_order_id=value.order_id,
                event_kind="ACCEPTED",
                decision_kind="ACCEPT",
                occurred_at=now,
            )
            await complete_command(
                session,
                command_id=command.command_id,
                episode_id=wallet.episode_id,
                succeeded=True,
                snapshot={
                    "order_id": str(value.order_id),
                    "status": "ACCEPTED",
                    "filled": state.orders[-1].filled.as_parts(),
                    "spent": state.orders[-1].spent.as_parts(),
                },
            )
        orders.append(value)
        commands.append(command)

    scope: OrderScope = orders[0].scope
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        eth_before = await load_matching_state(
            session, wallet_id=wallet.wallet_id, scope=scope, pair=orders[2].pair
        )
        btc_before = await load_matching_state(
            session, wallet_id=wallet.wallet_id, scope=scope, pair=orders[0].pair
        )
        canceled = cancel_order(btc_before.state, orders[0].order_id, scope=scope)
        now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
        await persist_checkpoint(
            session,
            wallet_id=wallet.wallet_id,
            state=canceled,
            anchor_order_id=orders[0].order_id,
            event_kind="CANCELED",
            decision_kind="CANCEL",
            occurred_at=now,
        )

    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        eth_after = await load_matching_state(
            session, wallet_id=wallet.wallet_id, scope=scope, pair=orders[2].pair
        )
        btc_after = await load_matching_state(
            session, wallet_id=wallet.wallet_id, scope=scope, pair=orders[0].pair
        )
        rows = (
            await session.execute(
                """SELECT p.order_id,p.status,p.revision,r.revision AS reservation_revision,
                a.revision AS activity_revision,r.quote_reserved,r.base_reserved,
                p.last_event_id,
                (SELECT e.id FROM paper_order_events e WHERE e.order_id=p.order_id
                 ORDER BY e.sequence DESC LIMIT 1) AS latest_event
                FROM paper_order_projections p JOIN paper_reservations r USING(order_id)
                JOIN paper_order_activity a ON a.episode_id=p.episode_id
                WHERE p.episode_id=:episode""",
                {"episode": wallet.episode_id},
            )
        ).all()
    assert eth_after.state == eth_before.state
    assert {
        order.intent.order_id for order in btc_after.state.orders if not order.status.terminal
    } == {orders[1].order_id}
    assert len(rows) == 4
    for row in rows:
        is_canceled = row.order_id == orders[0].order_id
        assert row.status == ("CANCELED" if is_canceled else "ACCEPTED")
        assert row.quote_reserved == (0 if is_canceled else 100)
        assert row.base_reserved == 0
        assert row.revision == row.reservation_revision == row.activity_revision
        assert row.last_event_id == row.latest_event

    if corruption is None:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await enable_financial_writer(session)
            for table in ("paper_order_projections", "paper_reservations"):
                await session.execute(
                    f"UPDATE {table} SET revision=revision-1 WHERE order_id=:order",
                    {"order": orders[1].order_id},
                )
            # Both copies agree, but an active order must still match activity revision.
            unsafe = await get_wallet(session)
            assert unsafe is not None
            assert not unsafe.reset_available and unsafe.reset_reason == "ACTIVITY_UNKNOWN"
            for table in ("paper_order_projections", "paper_reservations"):
                await session.execute(
                    f"UPDATE {table} SET revision=revision+1 WHERE order_id=:order",
                    {"order": orders[1].order_id},
                )
        with pytest.raises(RuntimeError, match="rollback scheduling fixture"):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                pending = await submit_order(
                    session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
                )
                cancel = await submit_cancel(
                    session,
                    wallet_id=wallet.wallet_id,
                    episode_id=wallet.episode_id,
                    order_id=orders[1].order_id,
                    idempotency_key=uuid4(),
                )
                before = {
                    row.command_id: row.next_attempt_at
                    for row in (
                        await session.execute(
                            "SELECT command_id,next_attempt_at FROM paper_order_dispatch"
                        )
                    ).all()
                }
                btc_claim = await claim_order(
                    session,
                    DueOrder(commands[1].command_id, owner, before[commands[1].command_id]),
                    worker="pair-btc",
                )
                assert btc_claim is not None
                await reschedule_processed_orders(
                    session, btc_claim, order_ids=tuple(order.order_id for order in orders[:2])
                )
                btc_rows = {
                    row.command_id: row
                    for row in (await session.execute("SELECT * FROM paper_order_dispatch")).all()
                }
                assert btc_rows[commands[0].command_id].state == "TERMINAL"
                for command in (commands[2], commands[3], pending, cancel):
                    assert (
                        btc_rows[command.command_id].next_attempt_at == before[command.command_id]
                    )
                assert btc_rows[commands[1].command_id].claim_id == btc_claim.claim_id
                await finish_claim(session, btc_claim, terminal=False)
                btc_due = (
                    await session.execute(
                        "SELECT next_attempt_at FROM paper_order_dispatch WHERE command_id=:id",
                        {"id": commands[1].command_id},
                    )
                ).scalar_one()
                eth_claim = await claim_order(
                    session,
                    DueOrder(commands[2].command_id, owner, before[commands[2].command_id]),
                    worker="pair-eth",
                )
                assert eth_claim is not None
                await reschedule_processed_orders(
                    session, eth_claim, order_ids=tuple(order.order_id for order in orders[2:])
                )
                after = {
                    row.command_id: row
                    for row in (await session.execute("SELECT * FROM paper_order_dispatch")).all()
                }
                assert (
                    after[commands[3].command_id].next_attempt_at > before[commands[3].command_id]
                )
                for command in (commands[2], pending, cancel):
                    assert after[command.command_id].next_attempt_at == before[command.command_id]
                assert after[commands[1].command_id].next_attempt_at == btc_due
                assert after[commands[2].command_id].claim_id == eth_claim.claim_id
                raise RuntimeError("rollback scheduling fixture")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            restored = (
                await session.execute(
                    "SELECT command_id,state,next_attempt_at FROM paper_order_dispatch"
                )
            ).all()
            assert len(restored) == len(commands)
            assert all(
                row.state == "PENDING" and row.next_attempt_at == before[row.command_id]
                for row in restored
            )

    async def terminal_versions() -> tuple[object, ...]:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            return tuple(
                (
                    await session.execute(
                        """SELECT p.xmin::text,r.xmin::text,p.revision,r.revision
                        FROM paper_order_projections p
                        JOIN paper_reservations r USING(order_id) WHERE p.order_id=:order""",
                        {"order": orders[0].order_id},
                    )
                ).one()
            )

    original_versions = await terminal_versions()
    for value in orders[1:]:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            checkpoint = await load_matching_state(
                session, wallet_id=wallet.wallet_id, scope=scope, pair=value.pair
            )
            state = cancel_order(checkpoint.state, value.order_id, scope=scope)
            now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            await persist_checkpoint(
                session,
                wallet_id=wallet.wallet_id,
                state=state,
                anchor_order_id=value.order_id,
                event_kind="CANCELED",
                decision_kind="CANCEL",
                occurred_at=now,
            )
            readiness = (
                await session.execute(
                    "SELECT * FROM paper_wallet_reset_readiness(:episode)",
                    {"episode": wallet.episode_id},
                )
            ).one()
            assert readiness.order_projection_mismatch == 0
            assert readiness.reservation_revision_mismatch == 0
        # xmin proves no UPDATE occurred, even one assigning the original revision.
        assert await terminal_versions() == original_versions

    assert readiness.active_order_count == readiness.active_reservation_count == 0
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        for command in commands:
            scheduled = (
                await session.execute(
                    "SELECT next_attempt_at FROM paper_order_dispatch WHERE command_id=:id",
                    {"id": command.command_id},
                )
            ).scalar_one()
            claim = await claim_order(
                session, DueOrder(command.command_id, owner, scheduled), worker="storage-fixture"
            )
            assert claim is not None
            await finish_claim(session, claim, terminal=True)
        ready = await get_wallet(session)
        assert ready is not None and ready.reset_available
    if corruption is not None:
        table, assignment = corruption
        async with migrator_engine.begin() as connection:
            await connection.execute(text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
            await connection.execute(text(f"ALTER TABLE {table} DISABLE TRIGGER USER"))
            await connection.execute(
                text(f"UPDATE {table} SET {assignment} WHERE order_id=:order"),
                {"order": orders[0].order_id},
            )
            await connection.execute(text(f"ALTER TABLE {table} ENABLE TRIGGER USER"))
            await connection.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            unsafe = await get_wallet(session)
            assert unsafe is not None
            assert not unsafe.reset_available and unsafe.reset_reason == "ACTIVITY_UNKNOWN"
