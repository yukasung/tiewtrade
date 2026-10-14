"""Controlled public feed through the real fenced supervisor, disposable DB only."""

import argparse
import asyncio
import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from redis.asyncio import Redis

from tiewtrade.core.candle_preview import CandleObservation
from tiewtrade.core.market_data import Candle, CandleFinality, CandleSeries, Timeframe, align_floor
from tiewtrade.core.money import Money, Quantity
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.realtime.notifications import RedisNotifications
from tiewtrade.services.market_data.candle_realtime import CandleSupervisor
from tiewtrade.venues.candle_streams import CandleFeedEvent, FeedCandle
from tiewtrade.venues.price_streams import FeedConnected, FeedDisconnected


class ControlledCandleFeed:
    def __init__(self, control: Path) -> None:
        self.control = control

    async def events(
        self, series: tuple[CandleSeries, ...]
    ) -> AsyncGenerator[CandleFeedEvent, None]:
        assert len(series) == 40
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
                opened = align_floor(now, Timeframe.H1)
                candle = Candle(
                    "BTC",
                    "USDT",
                    Timeframe.H1,
                    opened,
                    opened + Timeframe.H1.span,
                    Money.of("100.000000000000000001", "USDT"),
                    Money.of(101, "USDT"),
                    Money.of(99, "USDT"),
                    Money.of("100.5", "USDT"),
                    Quantity.of(count, "BTC"),
                    CandleFinality.OPEN,
                    now,
                )
                yield FeedCandle(
                    generation, CandleObservation(candle, now, now, count, 1, count, False)
                )
            await asyncio.sleep(0.2)


async def run(control: Path) -> None:
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
    task = asyncio.create_task(supervisor.run())
    try:
        while control.read_text().strip() != "stop":
            if task.done():
                await task
                raise RuntimeError("E2E_CANDLE_WORKER_STOPPED")
            await asyncio.sleep(0.1)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await notifications.close()
        await redis.aclose()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-file", type=Path, required=True)
    asyncio.run(run(parser.parse_args().control_file))
