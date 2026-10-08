import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.money import Money
from tiewtrade.core.realtime_prices import ObservationKind, QuoteObservation, QuoteState, observe
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import MarketDataSession, market_data_session
from tiewtrade.infra.market_data.catalog import PAIRS
from tiewtrade.infra.market_data.realtime_records import FeedLease, PriceSnapshot, StoredPrice
from tiewtrade.infra.market_data.realtime_storage import (
    acquire_writer,
    begin_generation,
    database_now,
    read_snapshot,
    set_connected,
)
from tiewtrade.infra.realtime.notifications import RedisNotifications
from tiewtrade.services.market_data.realtime import QuoteSupervisor, project_price
from tiewtrade.venues.price_streams import FeedConnected, FeedDisconnected, FeedEvent, FeedQuote
from tiewtrade.venues.symbols import Symbol


def test_stale_interval_starts_at_trade_deadline_not_tick_receipt() -> None:
    now = datetime(2026, 10, 7, tzinfo=UTC)
    q = QuoteObservation(
        "primary_spot", "BTC", "USDT", Money.of("1", "USDT"), 1, now, now, ObservationKind.STREAM
    )
    lease = FeedLease("primary_spot", 1, UUID(int=1), now + timedelta(seconds=100), True)
    old = StoredPrice("primary_spot", "BTC", "USDT", q, 1, 1, "READY")
    row = project_price(old, QuoteState(q, q), lease, now + timedelta(seconds=20), reconciled=True)
    assert row.effective_readiness == "STALE"
    assert row.unavailable_since == now + timedelta(seconds=10)


def test_reconnect_keeps_unready_interval_and_real_ready_resets_it() -> None:
    now = datetime(2026, 10, 7, tzinfo=UTC)
    q = QuoteObservation(
        "primary_spot", "BTC", "USDT", Money.of("1", "USDT"), 1, now, now, ObservationKind.SNAPSHOT
    )
    lease = FeedLease("primary_spot", 2, UUID(int=1), now + timedelta(seconds=5), True)
    old = StoredPrice(
        "primary_spot",
        "BTC",
        "USDT",
        q,
        0,
        1,
        "RECOVERING",
        unavailable_since=now - timedelta(seconds=50),
    )
    state = QuoteState(q, q)
    assert (
        project_price(old, state, lease, now, reconciled=False).unavailable_since
        == old.unavailable_since
    )
    assert project_price(old, state, lease, now, reconciled=True).unavailable_since is None


class ControlledFeed:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[FeedEvent] = asyncio.Queue()
        self.requests: asyncio.Queue[tuple[Symbol, asyncio.Future[QuoteObservation]]] = (
            asyncio.Queue()
        )
        self.closed = asyncio.Event()

    async def snapshot(self, symbol: Symbol) -> QuoteObservation:
        reply: asyncio.Future[QuoteObservation] = asyncio.get_running_loop().create_future()
        await self.requests.put((symbol, reply))
        return await reply

    async def events(self, symbols: tuple[Symbol, ...]) -> AsyncIterator[FeedEvent]:
        assert {(s.base, s.quote) for s in symbols} == PAIRS
        try:
            while True:
                yield await self.queue.get()
        finally:
            self.closed.set()


class CommittedNotifications:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.snapshots: list[PriceSnapshot] = []

    async def publish(self, source: str, revision: int) -> bool:
        async with market_data_session(self.engine) as session:
            self.snapshots.append(await read_snapshot(session))
        return True


@pytest_asyncio.fixture
async def price_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    async with market_data_session(engine) as session:
        await session.execute(
            "UPDATE market_price_feed SET lease_until=clock_timestamp()-interval '1 second'"
        )
        await session.execute("""UPDATE market_latest_prices SET amount=NULL, trade_id=NULL,
          trade_at=NULL, received_at=NULL, observation_kind=NULL, reconciled_generation=0,
          effective_readiness='MISSING', reason=NULL, order_ambiguous_at=NULL,
          unavailable_since=clock_timestamp()""")
    try:
        yield engine
    finally:
        await engine.dispose()


async def wait_for(predicate: Callable[[], bool]) -> None:
    async with asyncio.timeout(2):
        while not predicate():
            await asyncio.sleep(0.001)


async def snapshot_row(engine: AsyncEngine, base: str = "BTC") -> StoredPrice:
    async with market_data_session(engine) as session:
        return next(r for r in (await read_snapshot(session)).rows if r.base == base)


async def connected_supervisor(
    engine: AsyncEngine,
) -> tuple[QuoteSupervisor, ControlledFeed, CommittedNotifications]:
    feed = ControlledFeed()
    notifications = CommittedNotifications(engine)
    supervisor = QuoteSupervisor(engine, feed, cast(RedisNotifications, notifications))
    async with market_data_session(engine) as session:
        lease = await acquire_writer(session, uuid4())
        assert lease is not None
        supervisor.lease = await set_connected(session, lease, True)
    supervisor.epoch = 1
    await supervisor._load()
    return supervisor, feed, notifications


def observation(
    now: datetime,
    price: str = "1",
    trade_id: int = 1,
    *,
    kind: ObservationKind = ObservationKind.STREAM,
) -> QuoteObservation:
    return QuoteObservation(
        "primary_spot", "BTC", "USDT", Money.of(price, "USDT"), trade_id, now, now, kind
    )


async def test_recovery_lease_loss_closes_upstream_before_renew_tick(
    price_engine: AsyncEngine,
) -> None:
    class RenewalPausedSupervisor(QuoteSupervisor):
        async def _ticker(self) -> None:
            await asyncio.Event().wait()

    feed = ControlledFeed()
    supervisor = RenewalPausedSupervisor(
        price_engine, feed, cast(RedisNotifications, CommittedNotifications(price_engine))
    )
    task = asyncio.create_task(supervisor.run())
    try:
        await feed.queue.put(FeedConnected(1))
        requests = [await asyncio.wait_for(feed.requests.get(), 2) for _ in PAIRS]
        _symbol, reply = next(r for r in requests if r[0].base == "BTC")
        async with market_data_session(price_engine) as session:
            now = await database_now(session)
            await session.execute("UPDATE market_price_feed SET owner=:owner", {"owner": uuid4()})
        reply.set_result(observation(now, kind=ObservationKind.SNAPSHOT))
        # The recovery job discovers fencing failure now; waiting for 1s renewal is too late.
        await asyncio.wait_for(feed.closed.wait(), 0.4)
        await wait_for(lambda: not supervisor.jobs)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_controlled_interleaving_latches_before_batch_and_rejects_pre_detection_rest(
    price_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    supervisor, feed, notifications = await connected_supervisor(price_engine)
    monkeypatch.setattr("tiewtrade.services.market_data.realtime.random.uniform", lambda *_: 0)
    events = asyncio.create_task(supervisor._events())
    pair = ("BTC", "USDT")
    async with market_data_session(price_engine) as session:
        now = await database_now(session)
    supervisor._recover(pair)
    _, old_reply = await feed.requests.get()
    try:
        await feed.queue.put(FeedQuote(1, observation(now, "1", 8)))
        await feed.queue.put(FeedQuote(1, observation(now, "2", 9)))
        await wait_for(lambda: supervisor.states[pair].order_ambiguous_at is not None)
        async with supervisor.lock:
            row = await snapshot_row(price_engine)
        assert row.order_ambiguous_at == now
        assert row.reason == "ORDER_UNCONFIRMED"
        newer = observation(now + timedelta(microseconds=1), "3", 2)
        await feed.queue.put(FeedQuote(1, newer))
        await wait_for(lambda: supervisor.states[pair].candidate == newer)
        old_reply.set_result(replace(newer, observation_kind=ObservationKind.SNAPSHOT))
        _, new_reply = await asyncio.wait_for(feed.requests.get(), 2)
        assert (await snapshot_row(price_engine)).order_ambiguous_at == now
        new_reply.set_result(replace(newer, trade_id=99, observation_kind=ObservationKind.SNAPSHOT))
        await wait_for(lambda: pair in supervisor.reconciled)
        await supervisor.jobs[pair]
        committed = await snapshot_row(price_engine)
        assert committed.order_ambiguous_at is None
        assert committed.effective_readiness == "READY"
        assert notifications.snapshots[-1].rows == (await _snapshot(price_engine)).rows
        assert len(supervisor.dirty) <= 5 and len(supervisor.states) == 5
    finally:
        events.cancel()
        for job in supervisor.jobs.values():
            job.cancel()
        await asyncio.gather(events, *supervisor.jobs.values(), return_exceptions=True)


async def _snapshot(engine: AsyncEngine) -> PriceSnapshot:
    async with market_data_session(engine) as session:
        return await read_snapshot(session)


async def test_failed_commit_rolls_back_quote_and_does_not_publish(
    price_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    supervisor, _, notifications = await connected_supervisor(price_engine)
    before = await snapshot_row(price_engine)
    async with market_data_session(price_engine) as session:
        now = await database_now(session)
    pair = ("BTC", "USDT")
    q = observation(now)
    supervisor.states[pair] = QuoteState(q, q)
    supervisor.reconciled.add(pair)

    @asynccontextmanager
    async def rollback_commit(engine: AsyncEngine) -> AsyncIterator[MarketDataSession]:
        async with market_data_session(engine) as session:
            yield session
            raise RuntimeError("controlled transaction failure")

    monkeypatch.setattr(
        "tiewtrade.services.market_data.realtime.market_data_session", rollback_commit
    )
    with pytest.raises(RuntimeError, match="controlled transaction failure"):
        await supervisor._flush()
    assert await snapshot_row(price_engine) == before
    assert supervisor.rows[pair] == before
    assert pair in supervisor.dirty
    assert not notifications.snapshots


async def test_restart_keeps_latch_and_generation_scopes_stream_ids(
    price_engine: AsyncEngine,
) -> None:
    supervisor, feed, _ = await connected_supervisor(price_engine)
    pair = ("BTC", "USDT")
    async with market_data_session(price_engine) as session:
        now = await database_now(session)
    first = observation(now, "1", 8)
    state = observe(QuoteState(), first)
    state = observe(state, observation(now, "2", 9))
    supervisor.states[pair] = state
    await supervisor._flush()
    # A new process loads the durable latch and treats old IDs as snapshot metadata.
    restarted = QuoteSupervisor(
        price_engine, feed, cast(RedisNotifications, CommittedNotifications(price_engine))
    )
    async with market_data_session(price_engine) as session:
        await session.execute(
            "UPDATE market_price_feed SET lease_until=clock_timestamp()-interval '1 second'"
        )
        takeover = await acquire_writer(session, uuid4())
        assert takeover is not None
        restarted.lease = await begin_generation(session, takeover)
        restarted.lease = await set_connected(session, restarted.lease, True)
    await restarted._load()
    assert supervisor.lease is not None
    assert restarted.lease.generation > supervisor.lease.generation
    assert restarted.states[pair].order_ambiguous_at == now
    persisted = restarted.states[pair].confirmed
    assert persisted is not None
    assert persisted.observation_kind is ObservationKind.SNAPSHOT
    next_epoch = observation(now + timedelta(microseconds=1), "3", 8)
    reobserved = observe(restarted.states[pair], next_epoch)
    assert not reobserved.protocol_error
    assert reobserved.order_ambiguous_at == now
    assert reobserved.confirmed is not None
    assert reobserved.confirmed.amount == Money.of("1", "USDT")


async def test_known_disconnect_commits_immediately_and_old_epoch_cannot_mutate(
    price_engine: AsyncEngine,
) -> None:
    supervisor, feed, notifications = await connected_supervisor(price_engine)
    async with market_data_session(price_engine) as session:
        now = await database_now(session)
    pair = ("BTC", "USDT")
    q = observation(now)
    supervisor.states[pair] = QuoteState(q, q)
    supervisor.reconciled.add(pair)
    await supervisor._flush()
    events = asyncio.create_task(supervisor._events())
    try:
        await feed.queue.put(FeedQuote(0, observation(now + timedelta(seconds=1), "2")))
        await feed.queue.put(FeedDisconnected(1, "VENUE_UNAVAILABLE"))
        await wait_for(lambda: supervisor.lease is not None and not supervisor.lease.connected)
        async with supervisor.lock:
            snapshot = await _snapshot(price_engine)
        row = next(r for r in snapshot.rows if r.base == "BTC")
        assert snapshot.feed is not None
        assert not snapshot.feed.connected
        assert row.effective_readiness == "RECOVERING"
        assert row.observation is not None
        assert row.observation.amount == Money.of("1", "USDT")
        assert row.unavailable_since is not None
        assert notifications.snapshots[-1].feed is not None
        assert notifications.snapshots[-1].feed.connected is False
        assert len(supervisor.dirty) <= 5
    finally:
        events.cancel()
        await asyncio.gather(events, return_exceptions=True)


async def test_failed_new_attempt_exposes_failure_and_old_connected_callback_is_ignored(
    price_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feed = ControlledFeed()
    supervisor = QuoteSupervisor(
        price_engine, feed, cast(RedisNotifications, CommittedNotifications(price_engine))
    )
    async with market_data_session(price_engine) as session:
        supervisor.lease = await acquire_writer(session, uuid4())
    assert supervisor.lease is not None
    initial = supervisor.lease.generation
    await supervisor._load()
    monkeypatch.setattr(supervisor, "_recover", lambda pair: None)
    task = asyncio.create_task(supervisor._events())
    try:
        await feed.queue.put(FeedConnected(1))
        await wait_for(lambda: supervisor.epoch == 1)
        await feed.queue.put(FeedDisconnected(1, "VENUE_UNAVAILABLE"))
        await feed.queue.put(FeedDisconnected(2, "SUBSCRIPTION_ACK_TIMEOUT"))
        await wait_for(lambda: feed.queue.empty())
        await asyncio.sleep(0.05)
        async with market_data_session(price_engine) as session:
            failed = await read_snapshot(session)
        assert failed.feed is not None
        assert failed.feed.last_failure_code == "SUBSCRIPTION_ACK_TIMEOUT"
        assert failed.feed.generation == initial + 2
        await feed.queue.put(FeedConnected(1))
        await feed.queue.put(FeedQuote(1, observation(datetime.now(UTC), "999", 999)))
        await wait_for(lambda: feed.queue.empty())
        await asyncio.sleep(0.05)
        async with market_data_session(price_engine) as session:
            after = await read_snapshot(session)
        assert after.feed is not None and not after.feed.connected
        assert after.feed.generation == failed.feed.generation
        assert all(row.observation is None for row in after.rows)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_disconnect_commits_before_waiting_for_recovery_cleanup(
    price_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervisor, feed, _ = await connected_supervisor(price_engine)
    monkeypatch.setattr(supervisor, "_recover", lambda pair: None)
    task = asyncio.create_task(supervisor._events())
    cleanup = asyncio.Event()
    blocked = asyncio.Event()

    async def recovery_cleanup() -> None:
        try:
            blocked.set()
            await asyncio.Event().wait()
        finally:
            await cleanup.wait()

    recovery = asyncio.create_task(recovery_cleanup())
    await blocked.wait()
    try:
        await feed.queue.put(FeedConnected(1))
        await wait_for(lambda: supervisor.epoch == 1)
        supervisor.jobs[("BTC", "USDT")] = recovery
        await feed.queue.put(FeedDisconnected(1, "VENUE_UNAVAILABLE"))
        async with asyncio.timeout(0.25):
            while True:
                async with market_data_session(price_engine) as session:
                    snapshot = await read_snapshot(session)
                if snapshot.feed is not None and not snapshot.feed.connected:
                    break
                await asyncio.sleep(0.001)
        assert not recovery.done()
    finally:
        cleanup.set()
        task.cancel()
        recovery.cancel()
        await asyncio.gather(task, recovery, return_exceptions=True)


async def test_future_rest_keeps_fresh_cached_quote_recovering_until_valid_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 10, 8, tzinfo=UTC)
    pair = ("BTC", "USDT")
    cached = observation(now)
    feed = ControlledFeed()
    supervisor = QuoteSupervisor(
        cast(AsyncEngine, None), feed, cast(RedisNotifications, None), clock=lambda: now
    )
    lease = FeedLease("primary_spot", 1, UUID(int=1), now + timedelta(seconds=5), True)
    supervisor.lease = lease
    supervisor.states[pair] = QuoteState(cached, cached)
    supervisor.ambiguity_versions[pair] = 0
    projected: list[StoredPrice] = []
    old = StoredPrice("primary_spot", "BTC", "USDT", cached, 0, 1, "RECOVERING")

    @asynccontextmanager
    async def session_stub(engine: AsyncEngine) -> AsyncIterator[MarketDataSession]:
        yield cast(MarketDataSession, None)

    async def database_time(session: MarketDataSession) -> datetime:
        return now

    async def capture_flush() -> None:
        projected.append(
            project_price(
                old, supervisor.states[pair], lease, now, reconciled=pair in supervisor.reconciled
            )
        )

    monkeypatch.setattr("tiewtrade.services.market_data.realtime.market_data_session", session_stub)
    monkeypatch.setattr("tiewtrade.services.market_data.realtime.database_now", database_time)
    monkeypatch.setattr("tiewtrade.services.market_data.realtime.random.uniform", lambda *_: 0)
    monkeypatch.setattr(supervisor, "_flush", capture_flush)
    supervisor._recover(pair)
    job = supervisor.jobs[pair]
    try:
        _, reply = await asyncio.wait_for(feed.requests.get(), 2)
        reply.set_result(observation(now + timedelta(seconds=60), kind=ObservationKind.SNAPSHOT))
        await wait_for(lambda: bool(projected))
        assert pair not in supervisor.reconciled
        assert projected[-1].effective_readiness == "RECOVERING"
        assert projected[-1].observation == cached
        _, retry = await asyncio.wait_for(feed.requests.get(), 2)
        retry.set_result(observation(now, kind=ObservationKind.SNAPSHOT))
        await asyncio.wait_for(job, 2)
        assert pair in supervisor.reconciled
        assert projected[-1].effective_readiness == "READY"
    finally:
        job.cancel()
        await asyncio.gather(job, return_exceptions=True)
