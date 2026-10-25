"""Fake feed -> real role/PG -> matcher -> existing F-14 calculation, then disconnect."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.order_book_fixtures import SYMBOL, capability, depth_payload, snapshot
from tiewtrade.core.market_catalog import CatalogSnapshot
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import (
    OrderIntent,
    OrderOrigin,
    OrderScope,
    OrderType,
    QuoteBudget,
    SourceUnavailableError,
    TradingMode,
)
from tiewtrade.core.paper_matching import MatchingState, admit_order, advance_matching
from tiewtrade.core.positions import ExecutionSide, PositionPair, PositionState, apply_execution
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.order_book_storage import read_inputs
from tiewtrade.services.market_data.order_book import ingest_execution_pair
from tiewtrade.venues.binance_th.order_book_mapping import observation_from_stream
from tiewtrade.venues.order_books import (
    DepthSnapshot,
    ExecutionCapability,
    ExecutionFeedData,
    ExecutionFeedEvent,
)
from tiewtrade.venues.price_streams import FeedConnected, FeedDisconnected
from tiewtrade.venues.symbols import Symbol


class FixtureFeed:
    def __init__(self, at: datetime) -> None:
        self.at = at
        self.disconnect = asyncio.Event()
        self.closed = asyncio.Event()

    async def snapshot(self, symbol: Symbol) -> DepthSnapshot:
        return snapshot(self.at - timedelta(milliseconds=20), symbol=symbol)

    async def capability(self, symbol: Symbol) -> ExecutionCapability:
        return capability(self.at, symbol=symbol)

    async def events(
        self, symbols: tuple[Symbol, ...], *, generation: int
    ) -> AsyncGenerator[ExecutionFeedEvent, None]:
        try:
            yield FeedConnected(generation)
            at = self.at - timedelta(milliseconds=10)
            observation = observation_from_stream(
                depth_payload(at=at, symbol=symbols[0]), symbols, at
            )
            yield ExecutionFeedData(generation, observation)
            await self.disconnect.wait()
            yield FeedDisconnected(generation, "FIXTURE_DISCONNECTED")
        finally:
            self.closed.set()


class FixturePolicy:
    def check(self, intent: OrderIntent) -> None:
        assert intent.scope.mode is TradingMode.PAPER


class OverflowFeed(FixtureFeed):
    async def events(
        self, symbols: tuple[Symbol, ...], *, generation: int
    ) -> AsyncGenerator[ExecutionFeedEvent, None]:
        yield FeedConnected(generation)
        for index in range(4097):
            value = observation_from_stream(
                depth_payload(11 + index, 11 + index, self.at), symbols, self.at
            )
            yield ExecutionFeedData(generation, value)


async def test_bootstrap_queue_overflow_invalidates_without_a_ready_book(
    engine_engine: AsyncEngine,
) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    pair = PositionPair("BTC", "USDT")
    try:
        async with market_data_session(engine) as session:
            await session.execute("""UPDATE market_execution_state
              SET lease_until=clock_timestamp()-interval '1 second' WHERE base='BTC'""")
        feed = OverflowFeed(datetime.now(UTC))
        with pytest.raises(ExceptionGroup) as failure:
            await ingest_execution_pair(engine=engine, feed=feed, symbol=SYMBOL, owner=uuid4())
        assert failure.value.subgroup(SourceUnavailableError) is not None
        async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
            with pytest.raises(SourceUnavailableError):
                await read_inputs(session, pair, after=0)
    finally:
        await engine.dispose()


@pytest.mark.parametrize("base", ["BTC", "ETH"])
async def test_fake_public_pipeline_matches_exactly_and_disconnect_invalidates(
    engine_engine: AsyncEngine,
    base: str,
) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    pair = PositionPair(base, "USDT")
    symbol = Symbol(base, "USDT")
    try:
        async with market_data_session(engine) as session:
            await session.execute(
                """UPDATE market_execution_state
                SET lease_until=clock_timestamp()-interval '1 second' WHERE base=:base""",
                {"base": base},
            )
            prior = (
                await session.execute(
                    "SELECT last_input_id FROM market_execution_state WHERE base=:base",
                    {"base": base},
                )
            ).scalar_one_or_none() or 0
        feed = FixtureFeed(datetime.now(UTC))
        task = asyncio.create_task(
            ingest_execution_pair(engine=engine, feed=feed, symbol=symbol, owner=uuid4())
        )
        try:
            async with asyncio.timeout(3):
                while True:
                    try:
                        async with user_session(
                            engine_engine, uuid4(), role=DatabaseRole.ENGINE
                        ) as session:
                            rows = await read_inputs(session, pair, after=prior)
                        if rows:
                            break
                    except SourceUnavailableError:
                        if task.done():
                            await task
                    await asyncio.sleep(0.01)
            record = rows[0]
            scope = OrderScope(uuid4(), uuid4(), TradingMode.PAPER)
            intent = OrderIntent(
                uuid4(),
                uuid4(),
                scope,
                pair,
                OrderOrigin.MANUAL,
                ExecutionSide.BUY,
                OrderType.MARKET,
                QuoteBudget(Money.of(100, "USDT")),
            )
            state = admit_order(
                MatchingState(scope, pair),
                intent,
                now=feed.at - timedelta(seconds=1),
                sequence=1,
                cash=Money.of(2500, "USDT"),
                held=Quantity.of(0, base),
                constraints=record.metadata.market,
                reference_price=Money.of(100, "USDT"),
                policy=FixturePolicy(),
                catalog=CatalogSnapshot(1, frozenset({(base, "USDT")})),
            )
            result = advance_matching(
                state,
                record.market,
                now=datetime.now(UTC),
                constraints=record.metadata.market,
                execution_ids=(UUID(int=5),),
                catalog=CatalogSnapshot(1, frozenset({(base, "USDT")})),
            )
            assert len(result.fills) == 1
            effect = apply_execution(PositionState.empty(pair), result.fills[0])
            assert effect.state.held_quantity == Quantity.of("0.999", base)
            assert Money.of(2500, "USDT") + effect.quote_cash_delta == Money.of(2400, "USDT")
            assert record.market.source_at is not None
            feed.disconnect.set()
            with pytest.raises(ExceptionGroup):
                await task
            assert feed.closed.is_set()
            async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
                with pytest.raises(SourceUnavailableError):
                    await read_inputs(session, pair, after=prior)
        finally:
            if not task.done():
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
    finally:
        await engine.dispose()
