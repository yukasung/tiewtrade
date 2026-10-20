"""Public execution-book bootstrap, sequence bridge and fenced ingestion pipeline."""

import asyncio
from contextlib import aclosing
from dataclasses import replace
from datetime import timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.order_book import BookLevel, BookState, MarketInput, MarketTrade
from tiewtrade.core.orders import OrderError, SourceUnavailableError
from tiewtrade.core.positions import PositionPair
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.order_book_storage import (
    BUFFER_SIZE,
    ExecutionMetadata,
    acquire_book_writer,
    invalidate_book,
    publish_input,
    renew_book_writer,
)
from tiewtrade.infra.market_data.realtime_records import WriterLeaseLost
from tiewtrade.venues.order_books import (
    DepthSnapshot,
    DepthUpdate,
    ExecutionFeed,
    ExecutionFeedData,
    ExecutionFeedEvent,
    TradeObservation,
)
from tiewtrade.venues.price_streams import FeedConnected, FeedDisconnected
from tiewtrade.venues.symbols import Symbol


class ExecutionBookAssembler:
    """Amounts stay in Money/Quantity; no facts are created across unproven gaps."""

    def __init__(self, snapshot: DepthSnapshot, generation: int) -> None:
        self.snapshot = snapshot
        self.generation = generation
        self.last_update_id = snapshot.last_update_id
        self.ready = False
        self.book: BookState | None = None
        self._bids = {v.price: v.quantity for v in snapshot.bids}
        self._asks = {v.price: v.quantity for v in snapshot.asks}
        self._bid_boundary = snapshot.bids[-1].price
        self._ask_boundary = snapshot.asks[-1].price
        self._last_depth: DepthUpdate | None = None
        self._last_trade: TradeObservation | None = None
        self._failed = False

    def observe(
        self, observation: DepthUpdate | TradeObservation, input_id: int
    ) -> MarketInput | None:
        if self._failed:
            raise SourceUnavailableError("failed source requires a new snapshot")
        if observation.symbol != self.snapshot.symbol:
            self.ready = False
            self._failed = True
            raise SourceUnavailableError("execution symbol changed")
        try:
            return (
                self._depth(observation, input_id)
                if isinstance(observation, DepthUpdate)
                else self._trade(observation, input_id)
            )
        except (OrderError, ValueError):
            self.ready = False
            self._failed = True
            raise

    def _depth(self, update: DepthUpdate, input_id: int) -> BookState | None:
        if update.last_update_id <= self.last_update_id:
            if (
                self._last_depth is not None
                and update.last_update_id == self._last_depth.last_update_id
                and replace(update, received_at=self._last_depth.received_at) != self._last_depth
            ):
                raise SourceUnavailableError("conflicting duplicate depth identity")
            return None
        if self.ready:
            if update.first_update_id != self.last_update_id + 1:
                raise SourceUnavailableError("depth sequence gap")
        elif not update.first_update_id <= self.last_update_id + 1 <= update.last_update_id:
            raise SourceUnavailableError("snapshot does not bridge stream")
        if self._last_depth is not None and update.event_at < self._last_depth.event_at:
            raise SourceUnavailableError("depth source time reversal")
        for rows, values, boundary, bids in (
            (update.bids, self._bids, self._bid_boundary, True),
            (update.asks, self._asks, self._ask_boundary, False),
        ):
            for level in rows:
                if (bids and level.price < boundary) or (not bids and level.price > boundary):
                    continue  # This snapshot proves no untouched levels beyond its boundary.
                if level.quantity.amount == 0 and level.price != boundary:
                    values.pop(level.price, None)
                else:
                    values[level.price] = level.quantity
        if not any(v.amount > 0 for v in self._bids.values()) or not any(
            v.amount > 0 for v in self._asks.values()
        ):
            raise SourceUnavailableError("snapshot coverage exhausted")
        received = max(self.snapshot.received_at, update.received_at)
        if update.event_at > received or received - update.event_at > timedelta(seconds=1):
            raise SourceUnavailableError("depth source freshness unproven")
        result = BookState(
            PositionPair(update.symbol.base, update.symbol.quote),
            input_id,
            self.generation,
            received,
            received,
            tuple(BookLevel(p, self._bids[p]) for p in sorted(self._bids, reverse=True)),
            tuple(BookLevel(p, self._asks[p]) for p in sorted(self._asks)),
            True,
            not self.ready,
            source_at=update.event_at,
            source_first_sequence=update.first_update_id,
            source_last_sequence=update.last_update_id,
            snapshot_sequence=self.snapshot.last_update_id,
        )
        self.last_update_id = update.last_update_id
        self._last_depth = update
        self.ready = True
        self.book = result
        return result

    def _trade(self, trade: TradeObservation, input_id: int) -> MarketTrade | None:
        if not self.ready or self.book is None or self._last_depth is None:
            return None  # No maker queue exists during bootstrap/recovery.
        self.book.require_ready(trade.received_at)
        if self._last_trade is not None:
            if trade.trade_id == self._last_trade.trade_id:
                if replace(trade, received_at=self._last_trade.received_at) != self._last_trade:
                    raise SourceUnavailableError("conflicting duplicate trade identity")
                return None
            if trade.trade_id != self._last_trade.trade_id + 1:
                raise SourceUnavailableError("trade sequence gap")
        if (
            trade.occurred_at <= self._last_depth.event_at
            or trade.event_at < trade.occurred_at
            or trade.event_at > trade.received_at
        ):
            raise SourceUnavailableError("trade ordering unproven")
        self._last_trade = trade
        return MarketTrade(
            self.book.pair,
            input_id,
            self.generation,
            trade.received_at,
            trade.trade_id,
            trade.resting_side,
            trade.price,
            trade.quantity,
            True,
            source_at=trade.occurred_at,
            source_event_at=trade.event_at,
        )


async def ingest_execution_pair(
    *,
    engine: AsyncEngine,
    feed: ExecutionFeed,
    symbol: Symbol,
    owner: UUID,
) -> None:
    """One connection epoch; supervisor retries by acquiring a new DB-fenced epoch."""
    pair = PositionPair(symbol.base, symbol.quote)
    async with market_data_session(engine) as session:
        lease = await acquire_book_writer(session, pair, owner)
    if lease is None:
        return
    queue: asyncio.Queue[ExecutionFeedEvent | None] = asyncio.Queue(BUFFER_SIZE)

    async def reader() -> None:
        events = feed.events((symbol,), generation=lease.generation)
        # Contract implementations expose a closing async generator.
        async with aclosing(events) as stream:
            async for event in stream:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull as error:
                    raise SourceUnavailableError("bootstrap input buffer overflow") from error
        queue.put_nowait(None)

    async def heartbeat() -> None:
        while True:
            await asyncio.sleep(1)
            async with market_data_session(engine) as session:
                await renew_book_writer(session, lease)

    async def consume() -> None:
        assembler: ExecutionBookAssembler | None = None
        metadata: ExecutionMetadata | None = None
        current = lease
        while True:
            event = await queue.get()
            if event is None:
                return
            if event.generation != lease.generation:
                continue  # Late callbacks cannot resurrect another connection epoch.
            if isinstance(event, FeedDisconnected):
                raise SourceUnavailableError("execution feed disconnected")
            if isinstance(event, FeedConnected):
                if assembler is not None:
                    raise SourceUnavailableError("connection reused without new generation")
                async with asyncio.timeout(5):
                    snapshot, capability = await asyncio.gather(
                        feed.snapshot(symbol), feed.capability(symbol)
                    )
                assembler = ExecutionBookAssembler(snapshot, lease.generation)
                metadata = ExecutionMetadata(
                    capability.market,
                    capability.limit,
                    capability.observed_at,
                    capability.source_document,
                )
            elif isinstance(event, ExecutionFeedData):
                if assembler is None or metadata is None:
                    raise SourceUnavailableError("execution data before connection proof")
                value = assembler.observe(event.observation, current.last_input_id + 1)
                if value is not None:
                    async with market_data_session(engine) as session:
                        current = await publish_input(session, current, value, metadata)

    try:
        async with asyncio.TaskGroup() as group:
            reader_task = group.create_task(reader())
            heartbeat_task = group.create_task(heartbeat())
            consumer = group.create_task(consume())
            await consumer
            reader_task.cancel()
            heartbeat_task.cancel()
    finally:
        # Even cancellation/disconnect invalidates persisted READY before releasing ownership.
        try:
            async with market_data_session(engine) as session:
                await invalidate_book(session, lease, "FEED_DISCONNECTED")
        except WriterLeaseLost:
            pass  # The newer epoch or expired DB lease already fences all old inputs.
