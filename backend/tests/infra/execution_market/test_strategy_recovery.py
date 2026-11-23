"""Real basket transaction faults, lost COMMIT replies and pool-independent recovery."""

import asyncio
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from tests.infra.execution_market.commit_proxy import drop_commit_reply
from tests.infra.execution_market.test_bot_decisions import (
    bot_bracket_protocol as bot_bracket_protocol,
)
from tests.infra.execution_market.test_strategy_baskets import (
    accounting_indicator_heads as accounting_indicator_heads,
)
from tests.infra.execution_market.test_strategy_baskets import entry, f21_run, queue_entry
from tests.infra.risk_limits.test_execution import drive, runtime
from tiewtrade.core.market_data import Timeframe
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import OrderConflictError
from tiewtrade.infra.db import DatabaseRole, InfraError, create_engine_for, user_session
from tiewtrade.infra.paper_orders.dispatch import DueOrder, OrderClaimLostError, claim_order
from tiewtrade.infra.paper_orders.worker import process_claimed_order
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.protections import worker
from tiewtrade.infra.protections.storage import load
from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy

pytestmark = pytest.mark.usefixtures(
    "accounting_indicator_heads", "internal_database", "bot_bracket_protocol"
)


@pytest.mark.parametrize("fault", ["before_commit", "lost_commit_reply"])
async def test_trigger_fanout_recovers_from_database_after_transaction_fault(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        run = await f21_run(engine_engine, owner, wallet)
        _, first = await entry(engine_engine, owner, wallet, run, source)
        await entry(engine_engine, owner, wallet, run, source)
        await source.price("107")
        if fault == "before_commit":
            original = worker._adopt_basket_trigger

            async def fail_after_real_adoption(*args: Any, **kwargs: Any) -> None:
                await original(*args, **kwargs)
                raise RuntimeError("injected before fanout commit")

            with monkeypatch.context() as patch:
                patch.setattr(worker, "_adopt_basket_trigger", fail_after_real_adoption)
                with pytest.raises(RuntimeError, match="before fanout commit"):
                    async with user_session(
                        engine_engine, owner, role=DatabaseRole.ENGINE
                    ) as session:
                        await worker.process_group(session, first)
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                assert (
                    await session.execute("SELECT count(*) FROM bot_basket_triggers")
                ).scalar_one() == 0
                assert (
                    await session.execute("SELECT count(*) FROM paper_protection_exits")
                ).scalar_one() == 0
                assert (
                    await session.execute("SELECT count(*) FROM paper_order_commands")
                ).scalar_one() == 2
        else:
            armed, dropped = asyncio.Event(), asyncio.Event()
            async with drop_commit_reply(
                engine_engine.url.host or "localhost",
                engine_engine.url.port or 5432,
                armed,
                dropped,
            ) as port:
                proxy = create_async_engine(
                    engine_engine.url.set(host="127.0.0.1", port=port),
                    connect_args={"ssl": False},
                    hide_parameters=True,
                )
                try:
                    with pytest.raises(InfraError):
                        async with asyncio.timeout(10):
                            async with user_session(
                                proxy, owner, role=DatabaseRole.ENGINE
                            ) as session:
                                await worker.process_group(session, first)
                                armed.set()
                    assert dropped.is_set()
                finally:
                    await proxy.dispose()

        # A new worker pool discovers work from the database; no Redis message,
        # saved strategy instance or in-memory exit list is supplied to it.
        restarted = create_engine_for(DatabaseRole.ENGINE)
        try:
            async with user_session(restarted, owner, role=DatabaseRole.ENGINE) as session:
                before = tuple(
                    (
                        await session.execute("SELECT id FROM paper_protection_exits ORDER BY id")
                    ).scalars()
                )
                groups = tuple(
                    (
                        await session.execute("SELECT id FROM paper_protections ORDER BY id")
                    ).scalars()
                )
            if fault == "before_commit":
                # No winning fact survived rollback, so a new current quote is
                # required. A below-target quote cannot fabricate that fact.
                await source.price("104")
                async with user_session(restarted, owner, role=DatabaseRole.ENGINE) as session:
                    await worker.process_group(session, groups[0])
                    assert (
                        await session.execute("SELECT count(*) FROM bot_basket_triggers")
                    ).scalar_one() == 0
                await source.price("107")
                async with user_session(restarted, owner, role=DatabaseRole.ENGINE) as session:
                    await worker.process_group(session, groups[0])
            await source.price("104")
            for _ in range(2):
                async with user_session(restarted, owner, role=DatabaseRole.ENGINE) as session:
                    for group in groups:
                        await worker.process_group(session, group)
            async with user_session(restarted, owner, role=DatabaseRole.ENGINE) as session:
                after = tuple(
                    (
                        await session.execute("SELECT id FROM paper_protection_exits ORDER BY id")
                    ).scalars()
                )
                assert len(after) == 2 and (not before or after == before)
                assert (
                    await session.execute("SELECT count(*) FROM bot_basket_triggers")
                ).scalar_one() == 1
                assert (
                    await session.execute(
                        "SELECT count(*) FROM paper_order_commands WHERE action='NEW'"
                    )
                ).scalar_one() == 4
                commands = tuple(
                    (
                        await session.execute(
                            "SELECT command_id FROM paper_protection_exits ORDER BY id"
                        )
                    ).scalars()
                )
            for command in commands:
                await drive(restarted, owner, command)
            await asyncio.sleep(0.12)
            await source.next_book()
            for command in commands:
                async with user_session(restarted, owner, role=DatabaseRole.ENGINE) as session:
                    done = (
                        await session.execute(
                            "SELECT state='TERMINAL' FROM paper_order_dispatch "
                            "WHERE command_id=:id",
                            {"id": command},
                        )
                    ).scalar_one()
                if not done:
                    await drive(restarted, owner, command)
            async with user_session(restarted, owner, role=DatabaseRole.ENGINE) as session:
                for group in groups:
                    await worker.process_group(session, group)
                assert (
                    await session.execute("SELECT status FROM bot_strategy_baskets")
                ).scalar_one() == "CLOSED"
                assert (
                    await session.execute("SELECT count(*) FROM paper_position_events")
                ).scalar_one() == 4
                wallet_after = await get_wallet(session)
                assert (
                    wallet_after is not None
                    and wallet_after.balance == wallet.balance - Money.of("2.395802", "USDT")
                )
                position = (
                    await session.execute(
                        "SELECT held_quantity,total_cost,realized_pnl "
                        "FROM paper_position_projections"
                    )
                ).one()
                assert Quantity.of(position.held_quantity, "BTC") == Quantity.of(0, "BTC")
                assert Money.of(position.total_cost, "USDT") == Money.of(0, "USDT")
                assert Money.of(position.realized_pnl, "USDT") == Money.of("-2.395802", "USDT")
        finally:
            await restarted.dispose()


async def test_winning_basket_cancels_an_admitted_unfilled_entry_without_extra_buy(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        run = await f21_run(engine_engine, owner, wallet)
        _, group = await entry(engine_engine, owner, wallet, run, source)
        pending_order, pending_command = await queue_entry(engine_engine, owner, wallet, run)
        await drive(engine_engine, owner, pending_command)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute(
                    "SELECT status FROM paper_order_projections WHERE order_id=:id",
                    {"id": pending_order},
                )
            ).scalar_one() == "ACCEPTED"
        await source.price("107")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await worker.process_group(session, group)
            exit_command = (
                await session.execute("SELECT command_id FROM paper_protection_exits")
            ).scalar_one()
            cancel = (
                await session.execute(
                    "SELECT id FROM paper_order_commands WHERE action='CANCEL' AND order_id=:id",
                    {"id": pending_order},
                )
            ).scalar_one()
        await source.price("104")
        await source.next_book()
        await drive(engine_engine, owner, pending_command)
        await drive(engine_engine, owner, cancel)
        await drive(engine_engine, owner, exit_command)
        await asyncio.sleep(0.12)
        await source.next_book()
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            done = (
                await session.execute(
                    "SELECT state='TERMINAL' FROM paper_order_dispatch WHERE command_id=:id",
                    {"id": exit_command},
                )
            ).scalar_one()
        if not done:
            await drive(engine_engine, owner, exit_command)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute(
                    "SELECT status FROM paper_order_projections WHERE order_id=:id",
                    {"id": pending_order},
                )
            ).scalar_one() == "CANCELED"
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 2
            assert (
                await session.execute("SELECT count(*) FROM paper_protection_exits")
            ).scalar_one() == 1
            assert (
                await session.execute("SELECT count(*) FROM bot_basket_triggers")
            ).scalar_one() == 1
            balance = await get_wallet(session)
            assert balance is not None and balance.balance == wallet.balance - Money.of(
                "1.197901", "USDT"
            )
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_reservations "
                    "WHERE quote_reserved<>0 OR base_reserved<>0"
                )
            ).scalar_one() == 0


class SimulatedRestartError(Exception):
    """Roll back the completed writer operation before COMMIT."""


@pytest.mark.parametrize("commit_ack_lost", [False, True], ids=["rollback", "lost-commit-ack"])
async def test_restart_at_actual_sell_fill_preserves_remaining_exit_and_candle_guard(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    commit_ack_lost: bool,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        run = await f21_run(engine_engine, owner, wallet, timeframe=Timeframe.MN1)
        _, first = await entry(engine_engine, owner, wallet, run, source)
        _, second = await entry(engine_engine, owner, wallet, run, source)
        await source.price("107")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await worker.process_group(session, first)
            commands: dict[UUID, UUID] = {
                row.protection_id: row.command_id
                for row in (
                    await session.execute(
                        "SELECT protection_id,command_id FROM paper_protection_exits"
                    )
                ).all()
            }
        assert set(commands) == {first, second}
        # Only admit the first SELL. The second command stays durable across the fault.
        await drive(engine_engine, owner, commands[first])
        await asyncio.sleep(0.12)
        await source.price("104")
        await source.next_book()
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            due = (
                await session.execute(
                    "UPDATE paper_order_dispatch SET next_attempt_at=clock_timestamp() "
                    "WHERE command_id=:id RETURNING next_attempt_at",
                    {"id": commands[first]},
                )
            ).scalar_one()
            claim = await claim_order(
                session, DueOrder(commands[first], owner, due), worker="first"
            )
            assert claim is not None
        armed, dropped = asyncio.Event(), asyncio.Event()
        async with drop_commit_reply(
            engine_engine.url.host or "localhost", engine_engine.url.port or 5432, armed, dropped
        ) as port:
            proxy = create_async_engine(
                engine_engine.url.set(host="127.0.0.1", port=port),
                connect_args={"ssl": False},
                hide_parameters=True,
            )
            try:
                with pytest.raises(InfraError if commit_ack_lost else SimulatedRestartError):
                    async with user_session(proxy, owner, role=DatabaseRole.ENGINE) as session:
                        await process_claimed_order(
                            session, claim, policy=TransactionalRiskPolicy()
                        )
                        assert (
                            await session.execute("SELECT count(*) FROM paper_position_events")
                        ).scalar_one() == 3
                        if not commit_ack_lost:
                            raise SimulatedRestartError
                        armed.set()
                assert dropped.is_set() == commit_ack_lost
            finally:
                await proxy.dispose()
        restarted = create_engine_for(DatabaseRole.ENGINE)
        try:
            async with user_session(restarted, owner, role=DatabaseRole.ENGINE) as session:
                assert (
                    await session.execute("SELECT count(*) FROM paper_position_events")
                ).scalar_one() == (3 if commit_ack_lost else 2)
                if not commit_ack_lost:
                    await process_claimed_order(session, claim, policy=TransactionalRiskPolicy())
            with pytest.raises(OrderClaimLostError):
                async with user_session(restarted, owner, role=DatabaseRole.ENGINE) as session:
                    await process_claimed_order(session, claim, policy=TransactionalRiskPolicy())
            async with user_session(restarted, owner, role=DatabaseRole.ENGINE) as session:
                target = (
                    await session.execute(
                        "SELECT target FROM bot_strategy_baskets WHERE status='TRIGGERED'"
                    )
                ).scalar_one()
                assert Money.of(target, "USDT") == Money.of(106, "USDT")
                remaining = await load(session, second)
                assert remaining is not None and remaining.value.quantity == Quantity.of(
                    "0.999", "BTC"
                )
                assert remaining.value.prices.take_profit == Money.of(target, "USDT")
                balance = await get_wallet(session)
                assert balance is not None and balance.balance == wallet.balance - Money.of(
                    "101.197901", "USDT"
                )
                held = (
                    await session.execute("SELECT held_quantity FROM paper_position_projections")
                ).scalar_one()
                assert Quantity.of(held, "BTC") == remaining.value.quantity
                await worker.process_group(session, first)
                await worker.process_group(session, second)
            await drive(restarted, owner, commands[second])
            await asyncio.sleep(0.12)
            await source.next_book()
            await drive(restarted, owner, commands[second])
            async with user_session(restarted, owner, role=DatabaseRole.ENGINE) as session:
                await worker.process_group(session, second)
                assert (
                    await session.execute("SELECT status FROM bot_strategy_baskets")
                ).scalar_one() == "CLOSED"
                assert {
                    row.protection_id: row.command_id
                    for row in (
                        await session.execute(
                            "SELECT protection_id,command_id FROM paper_protection_exits"
                        )
                    ).all()
                } == commands
                assert (
                    await session.execute("SELECT count(*) FROM bot_strategy_execution_receipts")
                ).scalar_one() == 4
                assert (
                    await session.execute("SELECT count(*) FROM paper_position_events")
                ).scalar_one() == 4
                assert (
                    await session.execute(
                        "SELECT count(*) FROM paper_order_commands WHERE action='NEW'"
                    )
                ).scalar_one() == 4
                balance = await get_wallet(session)
                assert balance is not None and balance.balance == wallet.balance - Money.of(
                    "2.395802", "USDT"
                )
                pos = (
                    await session.execute(
                        "SELECT held_quantity,total_cost,realized_pnl "
                        "FROM paper_position_projections"
                    )
                ).one()
                assert Quantity.of(pos.held_quantity, "BTC") == Quantity.of(0, "BTC")
                assert Money.of(pos.total_cost, "USDT") == Money.of(0, "USDT")
                assert Money.of(pos.realized_pnl, "USDT") == Money.of("-2.395802", "USDT")
                assert (
                    await session.execute(
                        "SELECT count(*) FROM paper_reservations "
                        "WHERE base_reserved<>0 OR quote_reserved<>0"
                    )
                ).scalar_one() == 0
                guard = (
                    await session.execute("SELECT guard_revision FROM bot_strategy_progress")
                ).scalar_one()
            with pytest.raises(OrderConflictError, match="exit guard changed"):
                await queue_entry(restarted, owner, wallet, run, guard_revision=guard)
        finally:
            await restarted.dispose()
