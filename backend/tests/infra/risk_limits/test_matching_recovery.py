"""A stale consumer can rebase and consume a proven later maker trade atomically."""

import asyncio
from dataclasses import replace
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_dispatch import intent
from tests.infra.risk_limits.test_execution import drive, runtime
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.order_book import MarketTrade
from tiewtrade.core.orders import BaseSize, OrderType, TimeInForce
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.order_book_storage import publish_input
from tiewtrade.infra.paper_orders.dispatch import submit_order
from tiewtrade.infra.paper_orders.matching_storage import load_order_state
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot


async def test_rebase_does_not_discard_fresh_trade_after_recovery_snapshot(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"
    ) as sources:
        value = replace(
            intent(owner, wallet.episode_id),
            kind=OrderType.LIMIT,
            size=BaseSize(Quantity.of(1, "BTC")),
            limit_price=Money.of(100, "USDT"),
            time_in_force=TimeInForce.GTC,
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        await drive(engine_engine, owner, command.command_id)
        await asyncio.sleep(0.12)
        sources.book = replace(
            sources.book,
            asks=(
                replace(sources.book.asks[0], quantity=Quantity.of("0.5", "BTC")),
                *sources.book.asks[1:],
            ),
        )
        await sources.next_book()
        await drive(engine_engine, owner, command.command_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            partial = await load_order_state(session, value.order_id)
            assert partial.filled == Quantity.of("0.5", "BTC") and partial.resting
        # Leave an unconsumed input, then let it age outside the one-second
        # execution window. Only the later snapshot/trade may be used.
        await sources.next_book()
        await asyncio.sleep(1.05)
        await sources.price("100")
        await sources.next_book()
        async with market_data_session(sources.market) as publisher:
            now = (await publisher.execute("SELECT clock_timestamp()")).scalar_one()
            trade = MarketTrade(
                sources.book.pair,
                sources.book.input_id + 1,
                sources.book.generation,
                now,
                200,
                ExecutionSide.BUY,
                Money.of(100, "USDT"),
                Quantity.of("0.5", "BTC"),
                True,
            )
            await publish_input(publisher, sources.lease, trade, sources.metadata)
        await drive(engine_engine, owner, command.command_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            filled = await load_order_state(session, value.order_id)
            assert filled.status.terminal and filled.filled == Quantity.of(1, "BTC")
            assert (
                await session.execute("SELECT count(*) FROM paper_execution_links")
            ).scalar_one() == 2
            current = await get_wallet(session)
            assert current is not None and current.balance == Money.of(9900, "USDT")
            held = (
                await session.execute("SELECT held_quantity FROM paper_position_projections")
            ).scalar_one()
            assert Quantity.of(held, "BTC") == Quantity.of("0.999", "BTC")
