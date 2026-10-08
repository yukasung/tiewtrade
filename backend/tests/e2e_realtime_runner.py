"""Test-only producer: real QuoteSupervisor, PostgreSQL role and Redis transport.

The control file affects the upstream fake feed only. outage-alert explicitly
seeds the real producer's durable outage onset using DB time minus 61 seconds.
This fixture avoids a minute-long test; production clocks/settings are unchanged.
"""

import argparse
import asyncio
import os
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from redis.asyncio import Redis

from tiewtrade.core.money import Money
from tiewtrade.core.realtime_prices import ObservationKind, QuoteObservation
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.catalog import SOURCE
from tiewtrade.infra.market_data.realtime_storage import database_now
from tiewtrade.infra.realtime.notifications import RedisNotifications
from tiewtrade.services.market_data.realtime import QuoteSupervisor
from tiewtrade.venues.errors import VenueUnavailableError
from tiewtrade.venues.fake import FakePriceFeed
from tiewtrade.venues.price_streams import FeedConnected, FeedDisconnected, FeedEvent, FeedQuote
from tiewtrade.venues.symbols import Symbol


class ControlledPriceFeed(FakePriceFeed):
    def __init__(self, control: Path) -> None:
        super().__init__(snapshots={})
        self.control = control
        self.trade_id = 0

    def mode(self) -> str:
        return self.control.read_text().strip()

    def quote(self, symbol: Symbol, kind: ObservationKind) -> QuoteObservation:
        self.trade_id += 1
        now = datetime.now(UTC) - timedelta(milliseconds=20)
        return QuoteObservation(
            SOURCE,
            symbol.base,
            symbol.quote,
            Money.of("83348.47000000", symbol.quote),
            self.trade_id,
            now,
            now,
            kind,
        )

    async def snapshot(self, symbol: Symbol) -> QuoteObservation:
        if self.mode() != "healthy":
            raise VenueUnavailableError()
        return self.quote(symbol, ObservationKind.SNAPSHOT)

    async def events(self, symbols: tuple[Symbol, ...]) -> AsyncIterator[FeedEvent]:
        generation = 0
        connected = False
        while True:
            mode = self.mode()
            if mode.startswith("outage"):
                if connected:
                    connected = False
                    yield FeedDisconnected(generation, "VENUE_UNAVAILABLE")
            else:
                if not connected:
                    generation += 1
                    connected = True
                    yield FeedConnected(generation)
                if mode == "healthy":
                    for symbol in symbols:
                        yield FeedQuote(generation, self.quote(symbol, ObservationKind.STREAM))
            await asyncio.sleep(0.2)


async def run(control: Path) -> None:
    # Same localhost/database guard as the browser fixture. Never operate on a dev/live DB.
    name = os.environ["TIEWTRADE_E2E_DATABASE_NAME"]
    target = urlparse(os.environ["TIEWTRADE_DATABASE_URL_MARKET_DATA"])
    if (
        not name.startswith("tiewtrade_e2e")
        or target.scheme != "postgresql+asyncpg"
        or target.hostname not in {"127.0.0.1", "localhost", "::1"}
        or target.path != f"/{name}"
        or target.username != "tiewtrade_market_data"
        or target.query
        or target.fragment
    ):
        raise RuntimeError("E2E_DATABASE_REJECTED")
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    redis = Redis.from_url(os.environ["TIEWTRADE_REDIS_URL_MARKET_DATA"])
    notifications = RedisNotifications(redis)
    feed = ControlledPriceFeed(control)
    supervisor = QuoteSupervisor(engine, feed, notifications)

    async def fixture_outage_onset() -> None:
        seeded = False
        while True:
            await asyncio.sleep(0.1)
            if feed.mode() != "outage-alert":
                seeded = False
                continue
            async with supervisor.lock:
                if seeded or supervisor.lease is None or supervisor.lease.connected:
                    continue
                async with market_data_session(engine) as session:
                    actual = (await session.execute("SELECT current_database()")).scalar_one()
                    if actual != name:
                        raise RuntimeError("E2E_DATABASE_REJECTED")
                    onset = await database_now(session) - timedelta(seconds=61)
                supervisor.rows = {
                    pair: replace(row, unavailable_since=onset)
                    for pair, row in supervisor.rows.items()
                }
                supervisor.dirty.update(supervisor.rows)
                await supervisor._flush()
                seeded = True

    tasks = [asyncio.create_task(supervisor.run()), asyncio.create_task(fixture_outage_onset())]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await notifications.close()
        await redis.aclose()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-file", type=Path, required=True)
    asyncio.run(run(parser.parse_args().control_file))
