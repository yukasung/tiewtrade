"""R5 preview is never authoritative across a concurrent price/control change."""

import asyncio
from collections.abc import Mapping
from dataclasses import replace
from datetime import timedelta
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_dispatch import intent
from tests.infra.risk_limits.test_execution import drive, fill_buy, runtime
from tiewtrade.core import order_book
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import BaseSize, OrderType, SourceUnavailableError, TimeInForce
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import UserSession, market_data_session
from tiewtrade.infra.market_data.realtime_storage import read_snapshot, set_connected
from tiewtrade.infra.paper_orders.dispatch import submit_order
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot


@pytest.mark.parametrize("change", ["transient_breach", "disconnect", "disable", "stale"])
async def test_preview_cannot_authorize_buy_after_concurrent_change(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="10"
    ) as sources:
        await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        value = intent(owner, wallet.episode_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        await drive(engine_engine, owner, command.command_id)
        await asyncio.sleep(0.12)
        await sources.price("100")
        await sources.next_book()
        original = UserSession.execute
        injected = False

        async def change_before_final_fence(
            session: UserSession,
            statement: str,
            parameters: Mapping[str, object] | None = None,
        ) -> Any:
            nonlocal injected
            if statement == "SELECT risk_financial_fence()" and not injected:
                injected = True
                if change == "transient_breach":
                    # These commits must succeed before the final fence. A
                    # preview that holds the fence would deadlock this barrier.
                    await asyncio.wait_for(sources.price("90"), timeout=2)
                    await asyncio.wait_for(sources.price("100"), timeout=2)
                elif change == "disconnect":
                    async with market_data_session(sources.market) as publisher:
                        snapshot = await read_snapshot(publisher)
                        assert snapshot.feed is not None
                        await set_connected(publisher, snapshot.feed, False)
                elif change == "disable":
                    async with migrator_engine.begin() as connection:
                        await connection.execute(
                            text("UPDATE risk_protocol_control SET admission_enabled=false")
                        )
                else:
                    # Force the verified-book freshness boundary to cross after
                    # the preview, without depending on suite wall-clock runtime.
                    patch.setattr(order_book, "MAX_BOOK_AGE", timedelta(0))
            return await original(session, statement, parameters)

        with monkeypatch.context() as patch:
            patch.setattr(UserSession, "execute", change_before_final_fence)
            if change == "stale":
                with pytest.raises(SourceUnavailableError):
                    await drive(engine_engine, owner, command.command_id)
            else:
                await asyncio.wait_for(drive(engine_engine, owner, command.command_id), timeout=3)
        assert injected
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 1
            assert (
                await session.execute("SELECT count(*) FROM paper_execution_links")
            ).scalar_one() == 1
            current = await get_wallet(session)
            assert current is not None and current.balance == Money.of(9900, "USDT")
            assert (
                await session.execute(
                    "SELECT status FROM paper_order_projections WHERE order_id=:id",
                    {"id": value.order_id},
                )
            ).scalar_one() == "ACCEPTED"

            if change == "transient_breach":
                assert (
                    await session.execute("SELECT latched FROM risk_limit_settings")
                ).scalar_one()
                assert (
                    await session.execute("SELECT count(*) FROM risk_stop_requests")
                ).scalar_one() == 1


@pytest.mark.parametrize("breached", [False, True])
async def test_sell_command_resolves_risk_for_buy_orders_in_shared_checkpoint(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    breached: bool,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="10"
    ) as sources:
        await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        buy = intent(owner, wallet.episode_id)
        sell = replace(
            intent(owner, wallet.episode_id),
            side=ExecutionSide.SELL,
            size=BaseSize(Quantity.of("0.5", "BTC")),
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            buy_command = await submit_order(session, wallet_id=wallet.wallet_id, intent=buy)
        await drive(engine_engine, owner, buy_command.command_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            sell_command = await submit_order(session, wallet_id=wallet.wallet_id, intent=sell)
        await drive(engine_engine, owner, sell_command.command_id)
        await asyncio.sleep(0.12)
        if breached:
            await sources.price("90")
        await sources.price("100")
        await sources.next_book()
        await drive(engine_engine, owner, sell_command.command_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("SELECT count(*) FROM paper_execution_links")
            ).scalar_one() == (2 if breached else 3)
            states = {
                UUID(str(row.order_id)): row.status
                for row in await session.execute(
                    "SELECT order_id,status FROM paper_order_projections"
                )
            }
            assert states[buy.order_id] == ("ACCEPTED" if breached else "FILLED")
            assert states[sell.order_id] == "FILLED"
            current = await get_wallet(session)
            assert current is not None and current.balance == Money.of(
                "9949.4505" if breached else "9849.4505", "USDT"
            )
            held = (
                await session.execute(
                    "SELECT held_quantity FROM paper_position_projections WHERE base='BTC'"
                )
            ).scalar_one()
            assert Quantity.of(held, "BTC") == Quantity.of("0.499" if breached else "1.498", "BTC")


async def test_unchanged_resting_buy_does_not_block_publisher_or_change_money(
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
            limit_price=Money.of(90, "USDT"),
            time_in_force=TimeInForce.GTC,
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        await drive(engine_engine, owner, command.command_id)
        await asyncio.sleep(0.12)
        await sources.next_book()
        await drive(engine_engine, owner, command.command_id)
        await sources.next_book()
        async with market_data_session(sources.market) as publisher:
            await publisher.execute("SELECT risk_publication_fence()")
            await asyncio.wait_for(drive(engine_engine, owner, command.command_id), timeout=2)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 0
            current = await get_wallet(session)
            assert current is not None and current.balance == Money.of(10000, "USDT")
            assert (
                await session.execute(
                    "SELECT status FROM paper_order_projections WHERE order_id=:id",
                    {"id": value.order_id},
                )
            ).scalar_one() == "ACCEPTED"
