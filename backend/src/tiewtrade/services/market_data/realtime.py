"""Fenced public quote ingestion with per-pair bounded recovery jobs."""

import asyncio
import logging
import random
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.realtime_prices import (
    MAX_PRICE_AGE,
    ObservationKind,
    QuoteState,
    Readiness,
    observe,
    readiness,
    reconcile,
)
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.catalog import PAIRS, SOURCE
from tiewtrade.infra.market_data.realtime_records import FeedLease, StoredPrice, WriterLeaseLost
from tiewtrade.infra.market_data.realtime_storage import (
    acquire_writer,
    begin_generation,
    database_now,
    read_snapshot,
    renew_writer,
    set_connected,
    write_price,
)
from tiewtrade.infra.realtime.notifications import RedisNotifications
from tiewtrade.venues.errors import VenueError, VenueProtocolError, VenueRateLimitedError
from tiewtrade.venues.price_streams import FeedConnected, FeedDisconnected, FeedQuote, PriceFeed
from tiewtrade.venues.symbols import Symbol


def project_price(
    old: StoredPrice,
    state: QuoteState,
    lease: FeedLease,
    now: datetime,
    *,
    reconciled: bool,
) -> StoredPrice:
    ready = readiness(
        quote=state.confirmed,
        connected=lease.connected,
        reconciled=reconciled and state.order_ambiguous_at is None and not state.protocol_error,
        producer_alive=lease.lease_until > now,
        now=now,
    )
    since = old.unavailable_since
    reason = ready.value
    if state.order_ambiguous_at is not None:
        reason = "VENUE_PROTOCOL" if state.protocol_error else "ORDER_UNCONFIRMED"
    if ready is Readiness.READY:
        since = None
    else:
        onset = now
        if ready is Readiness.STALE and state.confirmed is not None:
            onset = min(onset, state.confirmed.trade_time + MAX_PRICE_AGE)
        if lease.lease_until <= now:
            onset = min(onset, lease.lease_until)
        since = min(since, onset) if since is not None else onset
    return replace(
        old,
        observation=state.confirmed,
        reconciled_generation=lease.generation if reconciled else 0,
        effective_readiness=ready.value,
        reason=reason,
        unavailable_since=since,
        order_ambiguous_at=state.order_ambiguous_at,
    )


class QuoteSupervisor:
    def __init__(
        self,
        engine: AsyncEngine,
        feed: PriceFeed,
        notifications: RedisNotifications,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.engine, self.feed, self.notifications, self.clock = engine, feed, notifications, clock
        self.lease: FeedLease | None = None
        self.epoch: int | None = None
        self.states: dict[tuple[str, str], QuoteState] = {}
        self.rows: dict[tuple[str, str], StoredPrice] = {}
        self.reconciled: set[tuple[str, str]] = set()
        self.jobs: dict[tuple[str, str], asyncio.Task[None]] = {}
        self.recovery_failure: asyncio.Future[None] | None = None
        self.lock = asyncio.Lock()
        self.dirty: set[tuple[str, str]] = set()
        self.failures: dict[tuple[str, str], str] = {}
        self.ambiguity_versions: dict[tuple[str, str], int] = {}

    async def _load(self) -> None:
        async with market_data_session(self.engine) as session:
            snapshot = await read_snapshot(session)
        self.rows = {(r.base, r.quote): r for r in snapshot.rows}
        self.states = {}
        for pair, row in self.rows.items():
            q = row.observation
            # Durable quotes are recovery observations, not duplicate IDs of a new stream epoch.
            if q is not None:
                q = replace(q, observation_kind=ObservationKind.SNAPSHOT)
            self.states[pair] = QuoteState(q, q, row.order_ambiguous_at)
        self.reconciled.clear()
        self.ambiguity_versions = dict.fromkeys(self.states, 0)
        self.dirty.update(self.states)

    async def _flush(self) -> None:
        lease = self.lease
        if lease is None:
            return
        if not self.dirty:
            return
        changed = False
        pending: dict[tuple[str, str], StoredPrice] = {}
        async with market_data_session(self.engine) as session:
            now = await database_now(session)
            for pair in tuple(self.dirty):
                state = self.states[pair]
                row = project_price(
                    self.rows[pair], state, lease, now, reconciled=pair in self.reconciled
                )
                if pair in self.failures and pair not in self.reconciled:
                    row = replace(row, reason=self.failures[pair])
                written = await write_price(session, lease, row)
                changed = written or changed
                pending[pair] = replace(row, revision=row.revision + int(written))
        self.rows.update(pending)
        self.dirty.difference_update(pending)
        # Lost notifications are reconciled by API polling; memory changes only after commit.
        if changed:
            published = await self.notifications.publish(
                SOURCE, max(r.revision for r in self.rows.values())
            )
            if not published:
                logging.getLogger(__name__).warning("price notification unavailable")

    def _recover(self, pair: tuple[str, str]) -> None:
        existing = self.jobs.get(pair)
        if existing is None or existing.done():
            job = asyncio.create_task(self._recovery(pair))
            job.add_done_callback(self._recovery_done)
            self.jobs[pair] = job

    def _recovery_done(self, job: asyncio.Task[None]) -> None:
        if job.cancelled():
            return
        error = job.exception()
        failure = self.recovery_failure
        if error is not None and failure is not None and not failure.done():
            failure.set_exception(error)

    async def _recovery(self, pair: tuple[str, str]) -> None:
        lease = self.lease
        if lease is None:
            return
        generation = lease.generation
        attempt = 0
        while (
            self.lease is not None and self.lease.generation == generation and self.lease.connected
        ):
            started = self.clock()
            ambiguity_version = self.ambiguity_versions[pair]
            delay = random.uniform(0, min(30, 2 ** min(attempt, 5)))
            try:
                snapshot = await self.feed.snapshot(Symbol(*pair))
                async with self.lock:
                    current = self.lease
                    if current is None or current.generation != generation or not current.connected:
                        return
                    async with market_data_session(self.engine) as session:
                        now = await database_now(session)
                    attempt_current = ambiguity_version == self.ambiguity_versions[pair]
                    result = (
                        reconcile(self.states[pair], snapshot, started_at=started, now=now)
                        if attempt_current
                        else None
                    )
                    if result is not None:
                        self.states[pair] = result.state
                    self.dirty.add(pair)
                    if result is not None and result.succeeded:
                        self.reconciled.add(pair)
                        self.failures.pop(pair, None)
                        await self._flush()
                        return
                    await self._flush()
            except VenueRateLimitedError as error:
                self.failures[pair] = error.code
                self.dirty.add(pair)
                if error.retry_after is not None:
                    delay = max(delay, error.retry_after.total_seconds())
            except VenueProtocolError as error:
                self.failures[pair] = error.code
                self.dirty.add(pair)
                delay = max(delay, 30)
            except VenueError as error:
                self.failures[pair] = error.code
                self.dirty.add(pair)
                logging.getLogger(__name__).warning("price recovery unavailable")
            attempt += 1
            await asyncio.sleep(delay)

    def _cancel_recovery(self) -> tuple[asyncio.Task[None], ...]:
        jobs = tuple(self.jobs.values())
        for job in jobs:
            job.cancel()
        self.failures.clear()
        return jobs

    async def _events(self) -> None:
        async for event in self.feed.events(tuple(Symbol(*p) for p in sorted(PAIRS))):
            async with self.lock:
                lease = self.lease
                if lease is None:
                    return
                if isinstance(event, FeedConnected):
                    if self.epoch is not None and event.generation <= self.epoch:
                        continue
                    old_jobs = self._cancel_recovery()
                    async with market_data_session(self.engine) as session:
                        lease = await begin_generation(session, lease)
                        lease = await set_connected(session, lease, True)
                    self.lease, self.epoch = lease, event.generation
                    await self._load()
                    await self.notifications.publish(SOURCE, lease.generation)
                    await asyncio.gather(*old_jobs, return_exceptions=True)
                    self.jobs.clear()
                    for supported_pair in PAIRS:
                        self._recover(supported_pair)
                elif isinstance(event, FeedDisconnected):
                    if self.epoch is not None and event.generation < self.epoch:
                        continue
                    old_jobs = self._cancel_recovery()
                    new_attempt = self.epoch is None or event.generation > self.epoch
                    async with market_data_session(self.engine) as session:
                        if new_attempt:
                            lease = await begin_generation(session, lease)
                        self.lease = await set_connected(session, lease, False, event.failure_code)
                    self.epoch = event.generation
                    if new_attempt:
                        await self._load()
                    self.reconciled.clear()
                    self.dirty.update(self.states)
                    await self._flush()
                    await self.notifications.publish(SOURCE, lease.generation)
                    await asyncio.gather(*old_jobs, return_exceptions=True)
                    self.jobs.clear()
                elif isinstance(event, FeedQuote) and event.generation == self.epoch:
                    pair = (event.quote.base, event.quote.quote)
                    if pair not in PAIRS or not lease.connected:
                        continue
                    before = self.states[pair]
                    state = observe(before, event.quote)
                    candidate = before.candidate or before.confirmed
                    conflict = candidate is not None and (
                        (
                            candidate.trade_time == event.quote.trade_time
                            and candidate.amount != event.quote.amount
                        )
                        or (
                            candidate.observation_kind is ObservationKind.STREAM
                            and candidate.trade_id == event.quote.trade_id
                            and (
                                candidate.trade_time != event.quote.trade_time
                                or candidate.amount != event.quote.amount
                            )
                        )
                    )
                    if conflict:
                        self.ambiguity_versions[pair] += 1
                    self.states[pair] = state
                    self.dirty.add(pair)
                    if state.order_ambiguous_at is not None or state.protocol_error:
                        self.reconciled.discard(pair)
                        await self._flush()
                        self._recover(pair)

    async def _ticker(self) -> None:
        last_renew = asyncio.get_running_loop().time()
        while True:
            await asyncio.sleep(0.1)
            async with self.lock:
                lease = self.lease
                if lease is None:
                    return
                mono = asyncio.get_running_loop().time()
                if mono - last_renew >= 1:
                    async with market_data_session(self.engine) as session:
                        self.lease = await renew_writer(session, lease)
                    last_renew = mono
                    self.dirty.update(self.states)
                await self._flush()

    async def run(self) -> None:
        owner = uuid4()
        while True:
            async with market_data_session(self.engine) as session:
                self.lease = await acquire_writer(session, owner)
            if self.lease is None:
                await asyncio.sleep(1)
                continue
            await self._load()
            self.recovery_failure = asyncio.get_running_loop().create_future()
            tasks = [asyncio.create_task(self._events()), asyncio.create_task(self._ticker())]
            try:
                done, _ = await asyncio.wait(
                    [*tasks, self.recovery_failure], return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    task.result()
            except WriterLeaseLost:
                logging.getLogger(__name__).warning("price producer lease lost")
            finally:
                for task in [*tasks, *self.jobs.values()]:
                    task.cancel()
                await asyncio.gather(*tasks, *self.jobs.values(), return_exceptions=True)
                self.jobs.clear()
                self.recovery_failure.cancel()
                # Retrieve concurrent failures even if another task finished first.
                if not self.recovery_failure.cancelled():
                    self.recovery_failure.exception()
                self.recovery_failure = None
                self.epoch = None
            await asyncio.sleep(1)
