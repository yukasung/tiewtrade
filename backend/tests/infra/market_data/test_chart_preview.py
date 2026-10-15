from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.candle_preview import CandleObservation
from tiewtrade.core.market_data import (
    Candle,
    CandleFinality,
    Timeframe,
    advance,
    align_floor,
    next_open,
)
from tiewtrade.core.money import Money, Quantity
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.candle_preview import (
    PreviewLeaseLostError,
    acquire,
    connection,
    enqueue_ended,
    flush,
)
from tiewtrade.infra.market_data.catalog import PAIRS


def observation() -> CandleObservation:
    now = datetime.now(UTC)
    opened = align_floor(now, Timeframe.H1)
    candle = Candle(
        "BTC",
        "USDT",
        Timeframe.H1,
        opened,
        opened + timedelta(hours=1),
        Money.of("100.000000000000000001", "USDT"),
        Money.of(101, "USDT"),
        Money.of(99, "USDT"),
        Money.of(100, "USDT"),
        Quantity.of(1, "BTC"),
        CandleFinality.OPEN,
        now,
    )
    return CandleObservation(candle, now, now, 1, 1, 1, False)


@pytest_asyncio.fixture
async def market_data_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        yield engine
    finally:
        await engine.dispose()


async def test_single_owner_fencing_and_buffer_cap(
    market_data_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.begin() as c:
        await c.execute(text("UPDATE market_candle_feed_state SET lease_until=clock_timestamp()"))
        await c.execute(text("DELETE FROM market_candle_preview"))
    async with market_data_session(market_data_engine) as s:
        lease = await acquire(s, uuid4())
        assert lease is not None
    async with market_data_session(market_data_engine) as s:
        assert await acquire(s, uuid4()) is None
        active = await connection(s, lease, True)
    with pytest.raises(PreviewLeaseLostError):
        async with market_data_session(market_data_engine) as s:
            await flush(s, lease, ((observation(), 1),))
    initial = observation()
    for number in range(121):
        candle = replace(
            initial.candle,
            open_at=initial.candle.open_at + number * timedelta(hours=1),
            end_at=initial.candle.end_at + number * timedelta(hours=1),
        )
        async with market_data_session(market_data_engine) as s:
            await flush(s, active, ((replace(initial, candle=candle), number + 1),))
    async with market_data_session(market_data_engine) as s:
        rows = (await s.execute("SELECT open_at FROM market_candle_preview ORDER BY open_at")).all()
        assert len(rows) == 120 and rows[0][0] == initial.candle.open_at + timedelta(hours=1)


async def test_new_owner_starts_recovering_even_after_previous_bootstrap(
    market_data_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.begin() as c:
        await c.execute(
            text(
                """UPDATE market_candle_feed_state SET bootstrapped=true,connected=true,
                failure_code=NULL,lease_until=clock_timestamp()"""
            )
        )
    async with market_data_session(market_data_engine) as s:
        lease = await acquire(s, uuid4())
        assert lease is not None
    async with migrator_engine.connect() as c:
        state = (
            await c.execute(
                text(
                    """SELECT bootstrapped,connected,failure_code
                    FROM market_candle_feed_state"""
                )
            )
        ).one()
    assert state == (False, False, "RECOVERING")


async def test_failed_preview_transaction_rolls_back_and_old_owner_cannot_publish(
    market_data_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.begin() as c:
        await c.execute(text("UPDATE market_candle_feed_state SET lease_until=clock_timestamp()"))
        await c.execute(text("DELETE FROM market_candle_preview"))
    async with market_data_session(market_data_engine) as s:
        lease = await acquire(s, uuid4())
        assert lease is not None
    with pytest.raises(RuntimeError, match="rollback"):
        async with market_data_session(market_data_engine) as s:
            await flush(s, lease, ((observation(), 1),))
            raise RuntimeError("rollback")
    async with migrator_engine.begin() as c:
        assert (
            await c.execute(text("SELECT count(*) FROM market_candle_preview"))
        ).scalar_one() == 0
        await c.execute(text("UPDATE market_candle_feed_state SET lease_until=clock_timestamp()"))
    async with market_data_session(market_data_engine) as s:
        successor = await acquire(s, uuid4())
        assert successor is not None and successor.epoch > lease.epoch
        await flush(s, successor, ((observation(), 1),))
    with pytest.raises(PreviewLeaseLostError):
        async with market_data_session(market_data_engine) as s:
            await flush(s, lease, ((observation(), 2),))
    async with migrator_engine.connect() as c:
        assert (
            await c.execute(text("SELECT epoch FROM market_candle_preview"))
        ).scalar_one() == successor.epoch


async def test_supported_series_obey_buffer_cap(
    market_data_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.begin() as c:
        await c.execute(text("UPDATE market_candle_feed_state SET lease_until=clock_timestamp()"))
        await c.execute(text("DELETE FROM market_candle_preview"))
    async with market_data_session(market_data_engine) as s:
        lease = await acquire(s, uuid4())
        assert lease is not None
    now = datetime.now(UTC)
    for slot in range(121):
        batch = []
        for base, _ in sorted(PAIRS):
            for tf in Timeframe:
                opened = advance(align_floor(now, tf), tf, slot)
                original = observation()
                candle = replace(
                    original.candle,
                    base=base,
                    timeframe=tf,
                    open_at=opened,
                    end_at=next_open(opened, tf),
                    volume=Quantity.of(1, base),
                )
                batch.append((replace(original, candle=candle), slot + 1))
        async with market_data_session(market_data_engine) as s:
            await flush(s, lease, tuple(batch))
    async with migrator_engine.connect() as c:
        assert (
            await c.execute(text("SELECT count(*) FROM market_candle_preview"))
        ).scalar_one() == len(PAIRS) * len(Timeframe) * 120
        counts = [
            int(row[0])
            for row in (
                await c.execute(
                    text("SELECT count(*) FROM market_candle_preview GROUP BY base,quote,timeframe")
                )
            ).all()
        ]
        assert len(counts) == len(PAIRS) * len(Timeframe) and set(counts) == {120}


async def test_ended_demand_is_transactional_and_never_resets_a_worker_claim(
    market_data_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    from tiewtrade.core.market_data import CandleWindow

    async with migrator_engine.begin() as c:
        await c.execute(
            text("UPDATE market_candle_feed_state SET lease_until=clock_timestamp(),metadata='{}'")
        )
    async with market_data_session(market_data_engine) as s:
        lease = await acquire(s, uuid4())
        assert lease is not None
    now = datetime.now(UTC)
    end = align_floor(now, Timeframe.H1)
    window = CandleWindow(end - Timeframe.H1.span, end)
    demands = {("BTC", "USDT", Timeframe.H1): window}
    with pytest.raises(RuntimeError, match="rollback"):
        async with market_data_session(market_data_engine) as s:
            await enqueue_ended(s, lease, demands)
            raise RuntimeError("rollback")
    async with migrator_engine.connect() as c:
        assert (
            await c.execute(text("SELECT count(*) FROM market_candle_demand"))
        ).scalar_one() == 0
        assert (
            await c.execute(text("SELECT metadata FROM market_candle_feed_state"))
        ).scalar_one() == {}
    async with market_data_session(market_data_engine) as s:
        await enqueue_ended(s, lease, demands)
    from tiewtrade.infra.market_data.claims import claim_next, update_claim

    async with market_data_session(market_data_engine) as s:
        claim = await claim_next(s, "f12-active-fetch")
        assert claim is not None
        await update_claim(
            s,
            claim,
            attemptcount=2,
            fetch_unit_id=uuid4(),
            fetch_start=window.start,
            fetch_end=window.end,
            next_attempt_at=now + timedelta(minutes=1),
        )
        before = (await s.execute("SELECT * FROM market_candle_demand")).mappings().one()
        await enqueue_ended(s, lease, demands)
        after = (await s.execute("SELECT * FROM market_candle_demand")).mappings().one()
        assert dict(before) == dict(after)


async def test_competing_owners_have_exactly_one_winner(
    market_data_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    import asyncio

    async with migrator_engine.begin() as c:
        await c.execute(text("UPDATE market_candle_feed_state SET lease_until=clock_timestamp()"))

    async def claim() -> object:
        async with market_data_session(market_data_engine) as s:
            return await acquire(s, uuid4())

    results = await asyncio.gather(claim(), claim())
    assert sum(result is not None for result in results) == 1


@pytest.mark.parametrize("tf", [Timeframe.M1, Timeframe.W1, Timeframe.MN1])
async def test_chart_overlay_bridges_rest_lag_preserves_real_gap_and_rest_precedence(
    tf: Timeframe,
    market_data_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    api_engine: AsyncEngine,
) -> None:
    from tiewtrade.core.market_data import CandleWindow
    from tiewtrade.infra.db.session import indicator_read_session
    from tiewtrade.infra.market_data.chart_overlay import overlay_preview
    from tiewtrade.infra.market_data.storage import read_candles

    now = align_floor(datetime.now(UTC), tf)
    start = advance(now, tf, -8)
    window = CandleWindow(start, now)
    async with migrator_engine.begin() as c:
        await c.execute(text("UPDATE market_candle_feed_state SET lease_until=clock_timestamp()"))
        await c.execute(text("DELETE FROM market_candle_preview"))
        await c.execute(
            text("DELETE FROM market_candles WHERE base='BTC' AND timeframe=:tf"), {"tf": tf.value}
        )
    async with market_data_session(market_data_engine) as s:
        lease = await acquire(s, uuid4())
        assert lease is not None
    original = observation()
    for minute in range(8):
        if minute == 3:
            continue  # An event never received must remain a real gap.
        opened = advance(start, tf, minute)
        candle = replace(
            original.candle,
            timeframe=tf,
            open_at=opened,
            end_at=next_open(opened, tf),
        )
        async with market_data_session(market_data_engine) as s:
            await flush(s, lease, ((replace(original, candle=candle), minute + 1),))
    async with indicator_read_session(api_engine, uuid4()) as s:
        canonical = await read_candles(s, "BTC", "USDT", tf, window, 1000)
        merged = await overlay_preview(s, "BTC", "USDT", tf, window, canonical)
        assert len(canonical.candles) == 0
        assert len(merged.candles) == 7
        assert merged.gaps == (CandleWindow(advance(start, tf, 3), advance(start, tf, 4)),)
        assert all(row.candle.finality is CandleFinality.UNCONFIRMED for row in merged.candles)
    async with migrator_engine.begin() as c:
        await c.execute(
            text("""INSERT INTO market_candles
          (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,finality,
           observed_at,fetch_started_at,last_checked_at,ingestion_generation)
          SELECT source,base,quote,timeframe,open_at,end_at,open,high,low,100.75,volume,
           'UNCONFIRMED',clock_timestamp(),clock_timestamp(),clock_timestamp(),1
          FROM market_candle_preview WHERE base='BTC' AND timeframe=:tf AND open_at=:start"""),
            {"start": start, "tf": tf.value},
        )
    # A new read represents cold reload and must prefer settled canonical data.
    async with indicator_read_session(api_engine, uuid4()) as s:
        canonical = await read_candles(s, "BTC", "USDT", tf, window, 1000)
        merged = await overlay_preview(s, "BTC", "USDT", tf, window, canonical)
        assert len(merged.candles) == 7
        assert merged.candles[0].candle.close == Money.of("100.75", "USDT")
        assert len(canonical.candles) == 1


async def test_buffer_rejects_older_event_even_after_epoch_takeover(
    market_data_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.begin() as c:
        await c.execute(text("UPDATE market_candle_feed_state SET lease_until=clock_timestamp()"))
        await c.execute(text("DELETE FROM market_candle_preview"))
    initial = observation()
    async with market_data_session(market_data_engine) as s:
        lease = await acquire(s, uuid4())
        assert lease is not None
        await flush(s, lease, ((initial, 10),))
        await flush(
            s,
            lease,
            ((replace(initial, candle=replace(initial.candle, close=Money.of(99, "USDT"))), 9),),
        )
    async with migrator_engine.begin() as c:
        await c.execute(text("UPDATE market_candle_feed_state SET lease_until=clock_timestamp()"))
    async with market_data_session(market_data_engine) as s:
        successor = await acquire(s, uuid4())
        assert successor is not None
        await flush(
            s,
            successor,
            (
                (
                    replace(
                        initial,
                        event_at=initial.event_at - timedelta(seconds=1),
                        candle=replace(initial.candle, close=Money.of(99, "USDT")),
                    ),
                    11,
                ),
            ),
        )
    async with migrator_engine.connect() as c:
        assert (
            str((await c.execute(text("SELECT close FROM market_candle_preview"))).scalar_one())
            == "100"
        )
