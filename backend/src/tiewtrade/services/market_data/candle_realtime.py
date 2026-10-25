"""One fenced candle supervisor; frame input is coalesced into the supported slots."""

import asyncio
import logging
from contextlib import aclosing
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.candle_preview import CandleObservation, Progress, compare
from tiewtrade.core.market_data import CandleFinality, CandleSeries, CandleWindow, Timeframe
from tiewtrade.infra.db.errors import InfraError
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.candle_preview import (
    PreviewLease,
    PreviewLeaseLostError,
    acquire,
    bootstrap_series,
    complete_bootstrap,
    connection,
    enqueue_ended,
    fence,
    flush,
)
from tiewtrade.infra.market_data.catalog import SOURCE, runtime_symbol_map
from tiewtrade.infra.platform import RuntimeSymbol, record_timeframe_readiness
from tiewtrade.infra.realtime.notifications import RedisNotifications
from tiewtrade.venues.candle_streams import CandleFeed, FeedCandle
from tiewtrade.venues.price_streams import FeedConnected, FeedDisconnected

PUBLIC_CATALOG_MODES = frozenset({"PUBLIC", "PREPARING"})


class CandleConflictError(ValueError):
    pass


class CandleSupervisor:
    def __init__(
        self, engine: AsyncEngine, feed: CandleFeed, notifications: RedisNotifications
    ) -> None:
        self.engine, self.feed, self.notifications = engine, feed, notifications
        self.lease: PreviewLease | None = None
        self.epoch: int | None = None
        self.last_generation = 0
        self.rows: dict[tuple[str, str, Timeframe], tuple[CandleObservation, int]] = {}
        self.dirty: set[tuple[str, str, Timeframe]] = set()
        self.demands: dict[tuple[str, str, Timeframe], CandleWindow] = {}
        self.lock = asyncio.Lock()
        self.bootstrap: asyncio.Task[None] | None = None
        self.catalog: dict[tuple[str, str], RuntimeSymbol] = {}
        self.series: tuple[CandleSeries, ...] = ()

    async def _reload_catalog(self) -> None:
        async with market_data_session(self.engine) as session:
            self.catalog = await runtime_symbol_map(session, modes=PUBLIC_CATALOG_MODES)
        self.series = tuple(
            CandleSeries(base, quote, timeframe)
            for base, quote in sorted(self.catalog)
            for timeframe in Timeframe
        )

    async def _connection(self, connected: bool, failure: str | None = None) -> None:
        async with self.lock:
            if self.lease is None:
                raise PreviewLeaseLostError()
            async with market_data_session(self.engine) as session:
                self.lease = await connection(session, self.lease, connected, failure)
            self.rows.clear()
            self.dirty.clear()
            self.demands.clear()

    def observe(self, event: FeedCandle) -> None:
        if event.generation != self.epoch:
            return
        incoming = event.observation
        candle = incoming.candle
        key = candle.base, candle.quote, candle.timeframe
        if candle.timeframe not in Timeframe or (candle.base, candle.quote) not in self.catalog:
            raise CandleConflictError()
        old = self.rows.get(key)
        revision = 1
        if old is not None:
            prior, revision = old
            if candle.open_at < prior.candle.open_at:
                return
            if candle.open_at == prior.candle.open_at:
                progress = compare(prior, incoming)
                if progress is Progress.OLDER:
                    return
                if progress is Progress.CONFLICT:
                    # Public series/progress counters only; never log raw payloads or credentials.
                    logging.getLogger(__name__).warning(
                        "candle progression conflict: %s/%s %s old=%s new=%s",
                        candle.base,
                        candle.quote,
                        candle.timeframe.value,
                        (prior.trade_count, prior.first_trade_id, prior.last_trade_id),
                        (incoming.trade_count, incoming.first_trade_id, incoming.last_trade_id),
                    )
                    raise CandleConflictError()
                if progress is Progress.DUPLICATE:
                    if incoming.event_at < prior.event_at:
                        return
                    if prior.closed_hint:
                        incoming = replace(
                            incoming,
                            closed_hint=True,
                            candle=replace(candle, finality=CandleFinality.UNCONFIRMED),
                        )
                else:
                    revision += 1
            else:
                revision += 1
                # Coalesce all ended slots even when intermediate stream events were missed.
                self._demand(key, CandleWindow(prior.candle.open_at, candle.open_at))
        if incoming.received_at >= candle.end_at:
            self._demand(key, CandleWindow(candle.open_at, candle.end_at))
        self.rows[key] = incoming, revision
        self.dirty.add(key)

    def _demand(self, key: tuple[str, str, Timeframe], window: CandleWindow) -> None:
        old = self.demands.get(key)
        self.demands[key] = (
            CandleWindow(min(old.start, window.start), max(old.end, window.end)) if old else window
        )

    async def _flush(self) -> None:
        async with self.lock:
            if self.lease is None:
                raise PreviewLeaseLostError()
            now = datetime.now(UTC)
            for key, (observation, _) in self.rows.items():
                candle = observation.candle
                if now >= candle.end_at:
                    self._demand(key, CandleWindow(candle.open_at, candle.end_at))
            rows = tuple(self.rows[key] for key in self.dirty)
            demands = dict(self.demands)
            async with asyncio.timeout(4):
                async with market_data_session(self.engine) as session:
                    await session.execute("SET LOCAL statement_timeout='500ms'")
                    await session.execute("SET LOCAL lock_timeout='200ms'")
                    await flush(session, self.lease, rows)
                    if demands:
                        await enqueue_ended(session, self.lease, demands)
            self.dirty.clear()
            self.demands.clear()
            epoch = self.lease.epoch
        # Lossy notification failure cannot undo committed previews or change feed readiness.
        if rows:
            await self.notifications.publish(SOURCE, epoch)

    async def _heartbeat(self) -> None:
        next_tick = asyncio.get_running_loop().time() + 2
        while True:
            await asyncio.sleep(max(0, next_tick - asyncio.get_running_loop().time()))
            if self.bootstrap is not None and self.bootstrap.done():
                completed, self.bootstrap = self.bootstrap, None
                completed.result()
            await self._flush()
            next_tick = max(next_tick + 2, asyncio.get_running_loop().time())

    async def _cancel_bootstrap(self) -> None:
        if self.bootstrap is None:
            return
        self.bootstrap.cancel()
        await asyncio.gather(self.bootstrap, return_exceptions=True)
        self.bootstrap = None

    async def _bootstrap(self, generation: int) -> None:
        for series in self.series:
            while self.epoch == generation:
                try:
                    async with self.lock:
                        if self.lease is None or self.epoch != generation:
                            return
                        lease = self.lease
                        async with (
                            asyncio.timeout(4),
                            market_data_session(self.engine) as session,
                        ):
                            await session.execute("SET LOCAL statement_timeout='500ms'")
                            await session.execute("SET LOCAL lock_timeout='200ms'")
                            await bootstrap_series(session, lease, series)
                            catalog = self.catalog[(series.base, series.quote)]
                            if catalog.mode == "PREPARING":
                                await record_timeframe_readiness(
                                    session,
                                    base=series.base,
                                    quote=series.quote,
                                    catalog_revision=catalog.revision,
                                    timeframe=series.timeframe,
                                    ready_at=datetime.now(UTC),
                                )
                    break
                except (InfraError, TimeoutError):
                    logging.getLogger(__name__).warning("candle preview bootstrap series retrying")
                    await asyncio.sleep(1)
        async with self.lock:
            if self.lease is None or self.epoch != generation:
                return
            async with asyncio.timeout(4), market_data_session(self.engine) as session:
                await session.execute("SET LOCAL statement_timeout='500ms'")
                await session.execute("SET LOCAL lock_timeout='200ms'")
                await complete_bootstrap(session, self.lease)

    async def _consume(self) -> None:
        async with aclosing(self.feed.events(self.series)) as events:
            async for event in events:
                if isinstance(event, FeedConnected):
                    if event.generation <= self.last_generation:
                        continue
                    self.last_generation = event.generation
                    await self._cancel_bootstrap()
                    await self._connection(True)
                    self.epoch = event.generation
                    self.bootstrap = asyncio.create_task(self._bootstrap(event.generation))
                elif isinstance(event, FeedDisconnected):
                    if self.epoch is None or event.generation >= self.epoch:
                        if event.generation < self.last_generation or (
                            self.epoch is None and event.generation == self.last_generation
                        ):
                            continue
                        self.last_generation = event.generation
                        await self._cancel_bootstrap()
                        await self._connection(False, event.failure_code)
                        self.epoch = None
                else:
                    async with self.lock:
                        self.observe(event)

    async def _catalog_changed(self) -> None:
        revision = max((row.catalog_revision for row in self.catalog.values()), default=0)
        while True:
            await asyncio.sleep(1)
            async with market_data_session(self.engine) as session:
                current = await runtime_symbol_map(session, modes=PUBLIC_CATALOG_MODES)
            current_revision = max((row.catalog_revision for row in current.values()), default=0)
            if current_revision != revision or current.keys() != self.catalog.keys():
                return

    async def run(self) -> None:
        owner = uuid4()
        while True:
            await self._reload_catalog()
            async with market_data_session(self.engine) as session:
                self.lease = await acquire(session, owner)
            if self.lease is None:
                await asyncio.sleep(5)
                continue
            consumer = asyncio.create_task(self._consume())
            heartbeat = asyncio.create_task(self._heartbeat())
            catalog_watch = asyncio.create_task(self._catalog_changed())
            catalog_reloaded = False
            try:
                done, _ = await asyncio.wait(
                    (consumer, heartbeat, catalog_watch), return_when=asyncio.FIRST_COMPLETED
                )
                catalog_reloaded = catalog_watch in done
                for task in done:
                    task.result()
            except CandleConflictError:
                await self._connection(False, "ORDER_UNCONFIRMED")
            except (InfraError, PreviewLeaseLostError, TimeoutError):
                logging.getLogger(__name__).warning("candle preview writer unavailable")
            finally:
                await self._cancel_bootstrap()
                for task in (consumer, heartbeat, catalog_watch):
                    task.cancel()
                await asyncio.gather(consumer, heartbeat, catalog_watch, return_exceptions=True)
                # A cancelled owner relinquishes only its own current epoch.
                if self.lease is not None:
                    try:
                        async with market_data_session(self.engine) as session:
                            await fence(session, self.lease)
                            await session.execute(
                                """UPDATE market_candle_feed_state SET
                              connected=false,lease_until=clock_timestamp() WHERE source=:source""",
                                {"source": SOURCE},
                            )
                    except (InfraError, PreviewLeaseLostError):
                        pass  # Expired/fenced owners have no right to alter the current lease.
                self.lease = None
                self.epoch = None
            if not catalog_reloaded:
                await asyncio.sleep(30)
