"""Controlled public feed through the real fenced supervisor, disposable DB only."""

import argparse
import asyncio
import os
import sys
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.candle_preview import CandleObservation
from tiewtrade.core.market_data import Candle, CandleFinality, CandleSeries, Timeframe, align_floor
from tiewtrade.core.money import Money, Quantity
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.realtime.notifications import RedisNotifications
from tiewtrade.services.market_data.candle_realtime import CandleSupervisor
from tiewtrade.services.market_data.ingestion import _seed_initial_demand, run_round
from tiewtrade.venues.candle_streams import CandleFeedEvent, FeedCandle
from tiewtrade.venues.candles import CandleSource
from tiewtrade.venues.price_streams import FeedConnected, FeedDisconnected


class ControlledCandleFeed:
    def __init__(self, control: Path) -> None:
        self.control = control

    async def events(
        self, series: tuple[CandleSeries, ...]
    ) -> AsyncGenerator[CandleFeedEvent, None]:
        assert len(series) == 2 * len(Timeframe)
        generation, count = 0, 0
        connected = False
        while True:
            mode = self.control.read_text().strip()
            if mode == "disconnected":
                if connected:
                    connected = False
                    yield FeedDisconnected(generation, "VENUE_UNAVAILABLE")
            elif mode == "healthy":
                if not connected:
                    connected = True
                    generation += 1
                    yield FeedConnected(generation)
                count += 1
                now = datetime.now(UTC)
                for base, tf, prices in (
                    ("BTC", Timeframe.H1, ("100.000000000000000001", "101", "99", "100.5")),
                    ("BTC", Timeframe.M3, ("200.000000000000000001", "201", "199", "200.5")),
                    ("ETH", Timeframe.M3, ("300.000000000000000001", "301", "299", "300.5")),
                ):
                    opened = align_floor(now, tf)
                    open_price, high, low, close = prices
                    candle = Candle(
                        base,
                        "USDT",
                        tf,
                        opened,
                        opened + tf.span,
                        Money.of(open_price, "USDT"),
                        Money.of(high, "USDT"),
                        Money.of(low, "USDT"),
                        Money.of(close, "USDT"),
                        Quantity.of(count, base),
                        CandleFinality.OPEN,
                        now,
                    )
                    yield FeedCandle(
                        generation, CandleObservation(candle, now, now, count, 1, count, False)
                    )
            await asyncio.sleep(0.2)


def browser_repair_source() -> CandleSource:
    # Reuse the same FakeVenue/prices as seed-3m, never a live exchange adapter.
    fixture = Path(__file__).resolve().parents[2] / (
        "specs/features/2026-10-12-candlestick-chart/evidence"
    )
    sys.path.insert(0, str(fixture))
    try:
        fixture_module = import_module("browser_fixture")
    finally:
        sys.path.pop(0)
    return cast(CandleSource, fixture_module.RepairSource())


async def repair_native_3m(engine: AsyncEngine, control: Path) -> None:
    source = browser_repair_source()
    while control.read_text().strip() != "stop":
        async with market_data_session(engine) as session:
            await _seed_initial_demand(session)
            # This opt-in composition owns a disposable E2E database. Other
            # timeframes must not consume this synthetic native-3m worker budget.
            await session.execute(
                """UPDATE market_candle_demand
                SET next_attempt_at=greatest(next_attempt_at,clock_timestamp()+interval '1 hour')
                WHERE timeframe<>'3m'"""
            )
        await run_round(engine, source, "f12-native-3m-rest", datetime.now(UTC))
        await asyncio.sleep(0.2)


async def run(control: Path, *, repair_three_minute: bool = False) -> None:
    name = os.environ["TIEWTRADE_E2E_DATABASE_NAME"]
    target = urlparse(os.environ["TIEWTRADE_DATABASE_URL_MARKET_DATA"])
    if (
        not name.startswith("tiewtrade_e2e")
        or target.path != "/" + name
        or target.hostname not in ("localhost", "127.0.0.1")
        or target.query
        or target.fragment
    ):
        raise RuntimeError("E2E_DATABASE_REJECTED")
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    redis = Redis.from_url(os.environ["TIEWTRADE_REDIS_URL_MARKET_DATA"])
    notifications = RedisNotifications(redis, channel="market.candles.changed")
    supervisor = CandleSupervisor(engine, ControlledCandleFeed(control), notifications)
    tasks = [asyncio.create_task(supervisor.run())]
    if repair_three_minute:
        tasks.append(asyncio.create_task(repair_native_3m(engine, control)))
    try:
        while control.read_text().strip() != "stop":
            for task in tasks:
                if task.done():
                    await task
                    raise RuntimeError("E2E_CANDLE_WORKER_STOPPED")
            await asyncio.sleep(0.1)
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
    parser.add_argument("--repair-native-3m", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.control_file, repair_three_minute=args.repair_native_3m))
