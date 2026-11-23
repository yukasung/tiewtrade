"""Real matcher/ledger/protection integration for the first-fill test policy."""

import asyncio
from dataclasses import replace
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_strategy_baskets import (
    accounting_indicator_heads as accounting_indicator_heads,
)
from tests.infra.execution_market.test_strategy_baskets import (
    bot_bracket_protocol as bot_bracket_protocol,
)
from tests.infra.execution_market.test_strategy_baskets import (
    entry,
    f21_run,
)
from tests.infra.risk_limits.test_execution import drive, runtime
from tiewtrade.core.market_data import Timeframe
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.strategy_config import PaperTestConfig
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.protections.storage import load
from tiewtrade.infra.protections.worker import process_group

pytestmark = pytest.mark.usefixtures(
    "internal_database", "bot_bracket_protocol", "accounting_indicator_heads"
)


@pytest.mark.parametrize("budget,terminal", [("105", "FILLED"), ("110", "EXPIRED")])
@pytest.mark.parametrize("exit_price,pnl", [("110", "4.78011"), ("90", "-15.17991")])
async def test_first_actual_fill_pins_both_legs_through_partial_fills_and_real_exit(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    budget: str,
    terminal: str,
    exit_price: str,
    pnl: str,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        config = PaperTestConfig(
            PositionPair("BTC", "USDT"), Timeframe.M5, Money.of(budget, "USDT")
        )
        run = await f21_run(engine_engine, owner, wallet, configuration=config)
        level = source.book.asks[0]
        source.book = replace(
            source.book,
            asks=(
                replace(level, price=Money.of("100", "USDT"), quantity=Quantity.of("0.5", "BTC")),
                replace(level, price=Money.of("110", "USDT"), quantity=Quantity.of("0.5", "BTC")),
            ),
        )
        order, protection = await entry(engine_engine, owner, wallet, run, source, budget=budget)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            group = await load(session, protection)
            assert group is not None
            assert group.value.prices.take_profit == Money.of("106", "USDT")
            assert group.value.prices.stop_loss == Money.of("94", "USDT")
            assert group.value.quantity == Quantity.of("0.999", "BTC")
            anchor = (
                await session.execute(
                    "SELECT * FROM bot_test_entry_anchors WHERE order_id=:order", {"order": order}
                )
            ).one()
            assert Money.of(anchor.anchor_price, "USDT") == Money.of("100", "USDT")
            assert (
                await session.execute(
                    "SELECT status FROM paper_order_projections WHERE order_id=:order",
                    {"order": order},
                )
            ).scalar_one() == terminal
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_execution_links WHERE order_id=:order",
                    {"order": order},
                )
            ).scalar_one() == 2
            await process_group(session, protection)
        source.book = replace(
            source.book,
            bids=(
                replace(
                    level, price=Money.of(exit_price, "USDT"), quantity=Quantity.of("10", "BTC")
                ),
            ),
            asks=(
                replace(level, price=Money.of("111", "USDT"), quantity=Quantity.of("10", "BTC")),
            ),
        )
        await source.price(exit_price)
        await source.next_book()
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, protection)
            command = (
                await session.execute(
                    "SELECT command_id FROM paper_protection_exits WHERE protection_id=:id",
                    {"id": protection},
                )
            ).scalar_one()
        await drive(engine_engine, owner, command)
        await asyncio.sleep(0.12)
        await source.next_book()
        await drive(engine_engine, owner, command)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, protection)
            group = await load(session, protection)
            assert group is not None and group.value.state.value == "CLOSED"
            assert group.value.prices.take_profit == Money.of("106", "USDT")
            assert group.value.prices.stop_loss == Money.of("94", "USDT")
            position = (
                await session.execute(
                    (
                        "SELECT held_quantity,total_cost,realized_pnl FROM "
                        "paper_position_projections WHERE episode_id=:episode"
                    ),
                    {"episode": wallet.episode_id},
                )
            ).one()
            assert Quantity.of(position.held_quantity, "BTC") == Quantity.of("0", "BTC")
            assert Money.of(position.total_cost, "USDT") == Money.of("0", "USDT")
            assert Money.of(position.realized_pnl, "USDT") == Money.of(pnl, "USDT")
            current = await get_wallet(session)
            assert current is not None and current.balance == wallet.balance + Money.of(pnl, "USDT")
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_reservations WHERE base_reserved<>0 OR "
                    "quote_reserved<>0"
                )
            ).scalar_one() == 0


@pytest.mark.parametrize("concurrent_retry", [False, True])
async def test_anchor_fill_rollback_retry_and_database_immutability(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
    concurrent_retry: bool,
) -> None:
    from uuid import uuid4

    from tests.infra.execution_market.test_strategy_baskets import queue_entry
    from tiewtrade.infra.db.errors import NotPermittedError
    from tiewtrade.infra.paper_orders.dispatch import DueOrder, OrderClaimLostError, claim_order
    from tiewtrade.infra.paper_orders.worker import process_claimed_order
    from tiewtrade.infra.protections import worker
    from tiewtrade.infra.protections.entry_anchor import resolve_first_fill
    from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy

    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        config = PaperTestConfig(PositionPair("BTC", "USDT"), Timeframe.M5, Money.of(100, "USDT"))
        run = await f21_run(engine_engine, owner, wallet, configuration=config)
        order, command = await queue_entry(engine_engine, owner, wallet, run)
        await drive(engine_engine, owner, command)
        await asyncio.sleep(0.12)
        await source.next_book()
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            due = (
                await session.execute(
                    "UPDATE paper_order_dispatch SET next_attempt_at=clock_timestamp() "
                    "WHERE command_id=:id RETURNING next_attempt_at",
                    {"id": command},
                )
            ).scalar_one()
            claim = await claim_order(session, DueOrder(command, owner, due), worker="anchor-fault")
        assert claim is not None
        original = resolve_first_fill

        async def fail_after_anchor(*args: object, **kwargs: object) -> bool:
            # Keep the real DB resolver and fail only after its write.
            result = await original(*args, **kwargs)  # type: ignore[arg-type]
            assert result is False
            raise RuntimeError("injected after anchor")

        with monkeypatch.context() as patch:
            patch.setattr(worker, "resolve_first_fill", fail_after_anchor)
            with pytest.raises(RuntimeError, match="injected after anchor"):
                async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                    await process_claimed_order(session, claim, policy=TransactionalRiskPolicy())
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute(
                    "SELECT execution_id FROM bot_test_entry_anchors WHERE order_id=:id",
                    {"id": order},
                )
            ).scalar_one() is None
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_execution_links WHERE order_id=:id", {"id": order}
                )
            ).scalar_one() == 0

        async def retry() -> bool:
            try:
                async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                    await process_claimed_order(session, claim, policy=TransactionalRiskPolicy())
                return True
            except OrderClaimLostError:
                return False

        if concurrent_retry:
            assert sum(await asyncio.gather(retry(), retry())) == 1
        else:
            assert await retry()
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            anchor = (
                await session.execute(
                    "SELECT execution_id,anchor_price,take_profit,stop_loss "
                    "FROM bot_test_entry_anchors WHERE order_id=:id",
                    {"id": order},
                )
            ).one()
            assert anchor.execution_id is not None
            assert Money.of(anchor.take_profit, "USDT") == Money.of(106, "USDT")
            assert Money.of(anchor.stop_loss, "USDT") == Money.of(94, "USDT")
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_execution_links WHERE order_id=:id", {"id": order}
                )
            ).scalar_one() == 1
        # A separate interpreter/DB pool has no access to the worker's objects.
        import subprocess
        import sys

        child = r"""
import asyncio, sys
from uuid import UUID
from tiewtrade.core.strategies import document_from_payload
from tiewtrade.core.strategy_config import PAPER_TEST_STRATEGY, PaperTestConfig
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.services.engine.bot import StrategyRegistry


async def main():
    engine = create_engine_for(DatabaseRole.ENGINE)
    try:
        async with user_session(
            engine, UUID(sys.argv[1]), role=DatabaseRole.ENGINE
        ) as session:
            run = (
                await session.execute(
                    "SELECT configuration FROM bot_runs WHERE id=:id",
                    {"id": UUID(sys.argv[2])},
                )
            ).one()
            document = document_from_payload(run.configuration, expected_version=1)
            strategy = StrategyRegistry(
                enable_paper_test=True
            ).configured_implementation(PAPER_TEST_STRATEGY, 1, 1, 1, document)
            assert (
                strategy is not None
                and PaperTestConfig.from_document(document) == strategy.config
            )
            anchor = (
                await session.execute(
                    "SELECT execution_id,take_profit::text,stop_loss::text "
                    "FROM bot_test_entry_anchors WHERE order_id=:id",
                    {"id": UUID(sys.argv[3])},
                )
            ).one()
            assert (
                anchor.execution_id is not None
                and anchor.take_profit == "106"
                and anchor.stop_loss == "94"
            )
    finally:
        await engine.dispose()


asyncio.run(main())
"""
        recovered = subprocess.run(
            [sys.executable, "-c", child, str(owner), str(run), str(order)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert recovered.returncode == 0, recovered.stderr
        # A new owner-scoped connection sees the same durable latch; RLS hides it
        # from a different owner, and runtime UPDATE cannot move resolved levels.
        async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("SELECT count(*) FROM bot_test_entry_anchors")
            ).scalar_one() == 0
        with pytest.raises(NotPermittedError):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await session.execute(
                    "UPDATE bot_test_entry_anchors SET take_profit=107 WHERE order_id=:id",
                    {"id": order},
                )
        async with user_session(api_engine, owner) as session:
            assert (
                await session.execute(
                    "SELECT execution_id FROM bot_test_entry_anchors WHERE order_id=:id",
                    {"id": order},
                )
            ).scalar_one() == anchor.execution_id
        with pytest.raises(NotPermittedError):
            async with user_session(api_engine, owner) as session:
                await session.execute(
                    "DELETE FROM bot_test_entry_anchors WHERE order_id=:id", {"id": order}
                )


async def test_pending_entry_and_manual_reduction_cannot_open_another_position(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tests.infra.execution_market.test_dispatch import intent
    from tests.infra.execution_market.test_strategy_baskets import queue_entry
    from tests.infra.protections.test_lifecycle import transfer
    from tiewtrade.core.orders import BaseSize, OrderConflictError
    from tiewtrade.core.positions import ExecutionSide

    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        config = PaperTestConfig(PositionPair("BTC", "USDT"), Timeframe.M5, Money.of(100, "USDT"))
        run = await f21_run(engine_engine, owner, wallet, configuration=config)
        order, command = await queue_entry(engine_engine, owner, wallet, run)
        with pytest.raises(OrderConflictError, match="entry count is full"):
            await queue_entry(engine_engine, owner, wallet, run)
        await drive(engine_engine, owner, command)
        await asyncio.sleep(0.12)
        source.book = replace(
            source.book, asks=(replace(source.book.asks[0], quantity=Quantity.of("0.4", "BTC")),)
        )
        await source.next_book()
        await drive(engine_engine, owner, command)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            protection = (
                await session.execute(
                    "SELECT id FROM paper_protections WHERE entry_order_id=:id", {"id": order}
                )
            ).scalar_one()
            group = await load(session, protection)
            assert group is not None and group.value.quantity == Quantity.of("0.3996", "BTC")
        sale = replace(
            intent(owner, wallet.episode_id),
            side=ExecutionSide.SELL,
            size=BaseSize(Quantity.of("0.1", "BTC")),
        )
        sell_command = await transfer(
            api_engine,
            engine_engine,
            scan_engine,
            owner,
            wallet,
            sale,
            selections=(
                {
                    "protection_id": str(protection),
                    "expected_revision": group.value.revision,
                    "quantity": "0.1",
                },
            ),
        )
        await drive(engine_engine, owner, sell_command)
        await asyncio.sleep(0.12)
        await source.next_book()
        await drive(engine_engine, owner, sell_command)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            remaining = await load(session, protection)
            assert remaining is not None and remaining.value.quantity == Quantity.of(
                "0.2996", "BTC"
            )
            assert remaining.value.prices == group.value.prices
            assert (
                await session.execute("SELECT count(*) FROM bot_strategy_entries")
            ).scalar_one() == 1
        # The same-candle exit fence rejects a new opening before any command is
        # created. Residual inventory is independently checked by pure strategy.
        with pytest.raises(OrderConflictError, match="exit guard changed"):
            await queue_entry(engine_engine, owner, wallet, run)


async def test_invalid_actual_stop_preserves_fill_and_uses_bot_failure_policy(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        config = PaperTestConfig(PositionPair("BTC", "USDT"), Timeframe.M5, Money.of(100, "USDT"))
        run = await f21_run(engine_engine, owner, wallet, configuration=config)
        # Admission reference110 yields SL5; actual fill100 would yield SL-5.
        await source.price("110")
        order, protection = await entry(engine_engine, owner, wallet, run, source, atr="35")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            row = (
                await session.execute(
                    "SELECT failure_code,anchor_price FROM bot_test_entry_anchors "
                    "WHERE order_id=:id",
                    {"id": order},
                )
            ).one()
            assert row.failure_code == "PROTECTION_SETUP_REJECTED"
            assert Money.of(row.anchor_price, "USDT") == Money.of(100, "USDT")
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_execution_links WHERE order_id=:id", {"id": order}
                )
            ).scalar_one() == 1
            group = await load(session, protection)
            assert group is not None and group.value.setup_failed_exit
            assert group.value.quantity == Quantity.of("0.999", "BTC")
            assert (
                await session.execute("SELECT status FROM bot_runs WHERE id=:id", {"id": run})
            ).scalar_one() == "STOPPED"


async def test_anchor_registration_failure_rolls_back_the_entire_decision(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.infra.execution_market.test_strategy_baskets import queue_entry
    from tiewtrade.infra.bots import decisions
    from tiewtrade.infra.bots.baskets import register_entry

    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ):
        config = PaperTestConfig(PositionPair("BTC", "USDT"), Timeframe.M5, Money.of(100, "USDT"))
        run = await f21_run(engine_engine, owner, wallet, configuration=config)

        async def fail_after_registration(*args: object, **kwargs: object) -> None:
            await register_entry(*args, **kwargs)  # type: ignore[arg-type]
            raise RuntimeError("injected after registration")

        with monkeypatch.context() as patch:
            patch.setattr(decisions, "register_entry", fail_after_registration)
            with pytest.raises(RuntimeError, match="injected after registration"):
                await queue_entry(engine_engine, owner, wallet, run)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            for table in (
                "bot_test_entry_anchors",
                "bot_strategy_entries",
                "bot_order_links",
                "bot_decisions",
                "paper_order_commands",
            ):
                assert (await session.execute(f"SELECT count(*) FROM {table}")).scalar_one() == 0
            assert (
                await session.execute("SELECT revision FROM bot_runs WHERE id=:id", {"id": run})
            ).scalar_one() == 1
        await queue_entry(engine_engine, owner, wallet, run)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("SELECT count(*) FROM bot_test_entry_anchors")
            ).scalar_one() == 1


async def test_disabled_engine_cannot_execute_a_persisted_test_run(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from uuid import uuid4

    from tiewtrade.services.engine.bot import StrategyRegistry, run_bot_quote

    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ):
        config = PaperTestConfig(PositionPair("BTC", "USDT"), Timeframe.M5, Money.of(100, "USDT"))
        run = await f21_run(engine_engine, owner, wallet, configuration=config)
        assert (
            await run_bot_quote(
                engine=engine_engine,
                owner=owner,
                run_id=run,
                registry=StrategyRegistry(enable_f21=True),
                worker_id=uuid4(),
            )
            is None
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == 0
            assert (
                await session.execute(
                    "SELECT reason_code FROM trading_stop_requests WHERE mode='PAPER'"
                )
            ).scalar_one() == "STRATEGY_VERSION_UNAVAILABLE"
