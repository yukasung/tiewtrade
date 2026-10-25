"""Actual-role FakeVenue/browser fixtures, guarded to a disposable E2E database."""

import asyncio
import os
import re
import sys
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text

from tiewtrade.core.candle_preview import CandleObservation
from tiewtrade.core.market_data import Candle, CandleFinality, CandleWindow, Timeframe, align_floor
from tiewtrade.core.money import Money, Quantity
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import market_data_session, presented_session
from tiewtrade.infra.market_data.candle_preview import acquire
from tiewtrade.infra.market_data.storage import coalesce_demand
from tiewtrade.services.market_data.candle_realtime import CandleSupervisor
from tiewtrade.services.market_data.ingestion import _seed_initial_demand, run_round
from tiewtrade.venues import FakeVenue, Symbol
from tiewtrade.venues.candle_streams import FeedCandle
from tiewtrade.venues.candles import CandlePage
from tiewtrade.venues.errors import VenueUnavailableError
from tiewtrade.venues.fake import FakeCandleFeed
from tiewtrade.venues.price_streams import FeedConnected


def candle(opened: datetime, now: datetime) -> Candle:
    return Candle(
        "BTC",
        "USDT",
        Timeframe.H1,
        opened,
        opened + Timeframe.H1.span,
        Money.of("100.000000000000000001", "USDT"),
        Money.of(101, "USDT"),
        Money.of(99, "USDT"),
        Money.of("100.5", "USDT"),
        Quantity.of(1, "BTC"),
        CandleFinality.UNCONFIRMED if opened + Timeframe.H1.span <= now else CandleFinality.OPEN,
        now,
    )


class RepairSource(FakeVenue):
    async def fetch_candles(
        self, symbol: Symbol, timeframe: Timeframe, start: datetime, end: datetime, limit: int
    ) -> CandlePage:
        if symbol.base not in ("BTC", "ETH") or timeframe is not Timeframe.H1:
            raise VenueUnavailableError()
        now = datetime.now(UTC)
        window = CandleWindow(start, end)
        rows = tuple(
            replace(
                candle(start + index * timeframe.span, now),
                base=symbol.base,
                volume=Quantity.of(1, symbol.base),
                close=Money.of("100.75", "USDT"),
            )
            for index in range(min(limit, int((end - start) / timeframe.span)))
        )
        return CandlePage(symbol, timeframe, window, rows, now)


class LostNotifications:
    async def publish(self, source: str, revision: int) -> bool:
        return False  # GET must read committed PG previews despite missing invalidations.


async def main() -> None:
    expected = os.environ.get("TIEWTRADE_E2E_DATABASE_NAME", "")
    if not re.fullmatch(r"tiewtrade_e2e(?:_[a-zA-Z0-9]+)*", expected):
        raise RuntimeError("E2E_DATABASE_REJECTED")
    migrator = create_engine_for(DatabaseRole.MIGRATOR)
    market = create_engine_for(DatabaseRole.MARKET_DATA)
    action = sys.argv[1]
    try:
        async with migrator.begin() as c:
            if (await c.execute(text("SELECT current_database()"))).scalar_one() != expected:
                raise RuntimeError("E2E_DATABASE_REJECTED")
            if action == "seed":
                await c.execute(text("SELECT begin_indicator_source_write()"))
                await c.execute(text("DELETE FROM market_candles"))
                await c.execute(text("DELETE FROM market_candle_demand"))
                await c.execute(text("DELETE FROM market_candle_preview"))
                await c.execute(
                    text(
                        "UPDATE market_candle_feed_state SET connected=false,metadata='{}',"
                        "bootstrapped=false,lease_until=clock_timestamp()"
                    )
                )
            elif action == "disconnect":
                await c.execute(text("UPDATE market_candle_feed_state SET connected=false"))
            elif action == "preview":
                await c.execute(
                    text("UPDATE market_candle_feed_state SET lease_until=clock_timestamp()")
                )
            elif action == "mutate":
                await c.execute(text("SELECT begin_indicator_source_write()"))
                await c.execute(
                    text("""UPDATE market_candles SET close=100 WHERE
                  base='BTC' AND timeframe='1h' AND open_at=(SELECT min(open_at)
                    FROM market_candles WHERE base='BTC' AND timeframe='1h')""")
                )
            elif action == "gap":
                await c.execute(text("SELECT begin_indicator_source_write()"))
                await c.execute(
                    text("""DELETE FROM market_candles WHERE base='BTC' AND timeframe='1h'
                  AND open_at=(SELECT max(open_at)-interval '1 hour' FROM market_candles
                    WHERE base='BTC' AND timeframe='1h')""")
                )
            elif action == "needs-refresh":
                await c.execute(text("SELECT begin_indicator_source_write()"))
                await c.execute(
                    text("""UPDATE market_candles
                  SET fetch_started_at=end_at-interval '1 second'
                  WHERE base='BTC' AND timeframe='1h' AND open_at=(
                    SELECT max(open_at) FROM market_candles WHERE base='BTC' AND timeframe='1h')""")
                )
        if action == "seed":
            auth = create_engine_for(DatabaseRole.AUTH)
            try:
                async with presented_session(auth, role=DatabaseRole.AUTH) as s:
                    await s.execute("DELETE FROM auth_throttle")
            finally:
                await auth.dispose()
            now = datetime.now(UTC)
            upper = align_floor(now, Timeframe.H1)
            window = CandleWindow(upper - 1000 * Timeframe.H1.span, upper)
            async with market_data_session(market) as s:
                for base in ("BTC", "ETH"):
                    await coalesce_demand(s, base, "USDT", Timeframe.H1, window)
                await _seed_initial_demand(s)
                await s.execute("""UPDATE market_candle_demand
                    SET next_attempt_at=clock_timestamp()+interval '1 hour'
                    WHERE NOT(base IN ('BTC','ETH') AND timeframe='1h')""")
            # The scheduler may split a demand into recent and deep-history
            # windows. Generate the exact window it requests instead of
            # coupling this browser fixture to the scheduler's batching order.
            result = await run_round(market, RepairSource(), "f12-browser", now)
            if result.stored != 2000:
                raise RuntimeError("F12_FIXTURE_REJECTED")
        elif action == "repair":
            result = await run_round(market, RepairSource(), "f12-repair", datetime.now(UTC))
            if result.stored == 0:
                raise RuntimeError("F12_REPAIR_REJECTED")
        elif action == "rollover":
            now = datetime.now(UTC)
            opened = align_floor(now, Timeframe.H1)
            previous = CandleObservation(
                replace(candle(opened - Timeframe.H1.span, now), close=Money.of("100.75", "USDT")),
                now,
                now,
                2,
                1,
                2,
                True,
            )
            current = CandleObservation(candle(opened, now), now, now, 1, 1, 1, False)
            async with migrator.begin() as c:
                await c.execute(
                    text("UPDATE market_candle_feed_state SET lease_until=clock_timestamp()")
                )
            feed = FakeCandleFeed(
                (FeedConnected(1), FeedCandle(1, previous), FeedCandle(1, current))
            )
            supervisor = CandleSupervisor(market, feed, LostNotifications())  # type: ignore[arg-type]
            await supervisor._reload_catalog()
            async with market_data_session(market) as s:
                supervisor.lease = await acquire(s, uuid4())
            async for event in feed.events(()):
                if isinstance(event, FeedConnected):
                    await supervisor._connection(True)
                    supervisor.epoch = event.generation
                else:
                    supervisor.observe(event)
                    await supervisor._flush()
        elif action == "preview":
            now = datetime.now(UTC)
            observation = CandleObservation(
                candle(align_floor(now, Timeframe.H1), now), now, now, 1, 1, 1, False
            )
            feed = FakeCandleFeed((FeedConnected(1), FeedCandle(1, observation)))

            supervisor = CandleSupervisor(market, feed, LostNotifications())  # type: ignore[arg-type]
            await supervisor._reload_catalog()
            async with market_data_session(market) as s:
                supervisor.lease = await acquire(s, uuid4())
            async for event in feed.events(()):
                if isinstance(event, FeedConnected):
                    await supervisor._connection(True)
                    supervisor.epoch = event.generation
                else:
                    supervisor.observe(event)  # type: ignore[arg-type]
            await supervisor._flush()
    finally:
        await market.dispose()
        await migrator.dispose()


if __name__ == "__main__":
    asyncio.run(main())
