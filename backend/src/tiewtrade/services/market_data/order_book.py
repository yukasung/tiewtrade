"""Public execution-book bootstrap, sequence bridge and fenced ingestion pipeline."""

import asyncio
import logging
from collections import OrderedDict, deque
from contextlib import aclosing
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.money import (
    Money,
    Quantity,
    RoundingDirection,
    money_for_quantity,
    price_for_notional,
)
from tiewtrade.core.order_book import MAX_BOOK_AGE, BookLevel, BookState, MarketInput, MarketTrade
from tiewtrade.core.orders import OrderError, SourceUnavailableError
from tiewtrade.core.positions import PositionPair
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.catalog import runtime_pairs
from tiewtrade.infra.market_data.order_book_storage import (
    BUFFER_SIZE,
    ExecutionMetadata,
    acquire_book_writer,
    invalidate_book,
    publish_input,
    renew_book_writer,
    retained_pairs,
)
from tiewtrade.infra.market_data.realtime_records import WriterLeaseLost
from tiewtrade.venues.errors import VenueError
from tiewtrade.venues.order_books import (
    DepthSnapshot,
    DepthUpdate,
    ExecutionFeed,
    ExecutionFeedData,
    ExecutionFeedEvent,
    TradeObservation,
    TradeSample,
)
from tiewtrade.venues.price_streams import FeedConnected, FeedDisconnected
from tiewtrade.venues.symbols import Symbol

MAX_PUBLIC_SOURCE_CLOCK_SKEW = timedelta(milliseconds=100)


def _failure_reasons(error: BaseException) -> tuple[str, ...]:
    if isinstance(error, BaseExceptionGroup):
        return tuple(reason for child in error.exceptions for reason in _failure_reasons(child))
    return (f"{type(error).__name__}: {error}",)


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
        self._trades: OrderedDict[int, TradeObservation] = OrderedDict()
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
            # Binance's local-book contract discards every stale/duplicate u,
            # irrespective of whether a retransmitted payload is byte-identical.
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
        if (
            update.event_at > received + MAX_PUBLIC_SOURCE_CLOCK_SKEW
            or received - update.event_at > MAX_BOOK_AGE
        ):
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
        previous = self._trades.get(trade.trade_id)
        if previous is not None:
            economic = ("symbol", "occurred_at", "resting_side", "price", "quantity")
            if any(getattr(trade, name) != getattr(previous, name) for name in economic):
                changed = ",".join(
                    name for name in economic if getattr(trade, name) != getattr(previous, name)
                )
                raise SourceUnavailableError(
                    f"conflicting duplicate trade identity fields={changed}"
                )
            self._trades.move_to_end(trade.trade_id)
            return None
        if (
            trade.event_at < trade.occurred_at
            or trade.event_at > trade.received_at + MAX_PUBLIC_SOURCE_CLOCK_SKEW
        ):
            raise SourceUnavailableError("trade ordering unproven")
        self._trades[trade.trade_id] = trade
        if len(self._trades) > BUFFER_SIZE:
            self._trades.popitem(last=False)
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


class TradeWindow:
    """Continuous public-trade window with one-rounding weighted price."""

    def __init__(
        self,
        symbol: Symbol,
        minutes: int,
        started_at: datetime,
        ended_at: datetime,
        history: tuple[TradeSample, ...],
    ) -> None:
        if minutes <= 0 or ended_at - started_at < timedelta(minutes=minutes):
            raise SourceUnavailableError("incomplete average-price history")
        self.symbol = symbol
        self.window = timedelta(minutes=minutes)
        self.seed_ended_at = ended_at
        self.seed_last_trade_id = max((sample.last_trade_id for sample in history), default=-1)
        self.samples: deque[tuple[datetime, Money, Quantity]] = deque()
        self.notional = Money.of(0, symbol.quote)
        self.quantity = Quantity.of(0, symbol.base)
        for sample in history:
            self._add(sample.occurred_at, sample.price, sample.quantity)
        self._trim(ended_at)

    def _add(self, occurred_at: datetime, price: Money, quantity: Quantity) -> None:
        notional = money_for_quantity(
            price,
            quantity,
            asset=self.symbol.base,
            rounding=RoundingDirection.TOWARD_ZERO,
        )
        self.samples.append((occurred_at, notional, quantity))
        self.notional += notional
        self.quantity += quantity

    def _trim(self, observed_through: datetime) -> None:
        cutoff = observed_through - self.window
        while self.samples and self.samples[0][0] < cutoff:
            _, notional, quantity = self.samples.popleft()
            self.notional -= notional
            self.quantity -= quantity

    def observe(self, value: DepthUpdate | TradeObservation) -> None:
        if isinstance(value, TradeObservation) and not (
            value.occurred_at <= self.seed_ended_at and value.trade_id <= self.seed_last_trade_id
        ):
            self._add(value.occurred_at, value.price, value.quantity)
        self._trim(value.received_at)

    def evidence(self, observed_through: datetime) -> tuple[Money, datetime, datetime]:
        self._trim(observed_through)
        if self.quantity.amount <= 0 or self.notional.amount <= 0:
            raise SourceUnavailableError("average-price window has no trades")
        return (
            price_for_notional(
                self.notional,
                self.quantity,
                asset=self.symbol.base,
                rounding=RoundingDirection.TOWARD_ZERO,
            ),
            observed_through - self.window,
            observed_through,
        )


class ExecutionBookSupervisor:
    """Keep one fenced public execution producer for every managed pair."""

    def __init__(
        self,
        engine: AsyncEngine,
        feed: ExecutionFeed,
        *,
        refresh_interval: float = 1.0,
    ) -> None:
        if refresh_interval <= 0:
            raise ValueError("positive execution supervisor interval required")
        self.engine = engine
        self.feed = feed
        self.refresh_interval = refresh_interval
        self.tasks: dict[PositionPair, asyncio.Task[None]] = {}

    async def _desired_pairs(self) -> frozenset[PositionPair]:
        async with market_data_session(self.engine) as session:
            catalog = await runtime_pairs(session)
            retained = await retained_pairs(session)
        return frozenset((*retained, *(PositionPair(base, quote) for base, quote in catalog)))

    async def _produce(self, pair: PositionPair) -> None:
        while True:
            try:
                try:
                    await ingest_execution_pair(
                        engine=self.engine,
                        feed=self.feed,
                        symbol=Symbol(pair.base, pair.quote),
                        owner=uuid4(),
                    )
                except* (SourceUnavailableError, VenueError, WriterLeaseLost) as failure:
                    logging.getLogger(__name__).warning(
                        "execution producer unavailable for %s/%s: %s",
                        pair.base,
                        pair.quote,
                        "; ".join(_failure_reasons(failure)),
                    )
                await asyncio.sleep(self.refresh_interval)
            except asyncio.CancelledError:
                raise

    async def run(self) -> None:
        try:
            while True:
                for pair, task in tuple(self.tasks.items()):
                    if task.done():
                        task.result()  # Unexpected defects stop the process instead of hiding them.
                        del self.tasks[pair]
                desired = await self._desired_pairs()
                obsolete = [self.tasks.pop(pair) for pair in set(self.tasks).difference(desired)]
                for task in obsolete:
                    task.cancel()
                if obsolete:
                    await asyncio.gather(*obsolete, return_exceptions=True)
                for pair in desired.difference(self.tasks):
                    self.tasks[pair] = asyncio.create_task(self._produce(pair))
                await asyncio.sleep(self.refresh_interval)
        finally:
            tasks = tuple(self.tasks.values())
            self.tasks.clear()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


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
        capability = None
        trade_window: TradeWindow | None = None
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
                    loaded_capability = await feed.capability(symbol)
                capability = loaded_capability
                minutes = max(
                    capability.market.average_price_minutes,
                    capability.limit.average_price_minutes,
                )
                if minutes:
                    ended_at = capability.observed_at
                    started_at = ended_at - timedelta(minutes=minutes)
                    history = await feed.trade_history(
                        symbol, started_at=started_at, ended_at=ended_at
                    )
                    trade_window = TradeWindow(symbol, minutes, started_at, ended_at, history)
                # Take the depth snapshot after history pagination so buffered stream
                # frames bridge a current book instead of ageing the snapshot in place.
                async with asyncio.timeout(5):
                    snapshot = await feed.snapshot(symbol)
                assembler = ExecutionBookAssembler(snapshot, lease.generation)
            elif isinstance(event, ExecutionFeedData):
                if assembler is None or capability is None:
                    raise SourceUnavailableError("execution data before connection proof")
                if trade_window is not None:
                    trade_window.observe(event.observation)
                value = assembler.observe(event.observation, current.last_input_id + 1)
                if value is not None:
                    average = None
                    started = observed = None
                    if trade_window is not None:
                        average, started, observed = trade_window.evidence(value.received_at)
                    metadata = ExecutionMetadata(
                        capability.market,
                        capability.limit,
                        capability.observed_at,
                        capability.source_document,
                        average,
                        started,
                        observed,
                    )
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
