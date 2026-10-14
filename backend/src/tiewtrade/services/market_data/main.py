"""Manual public-market-data runner; scheduling belongs to F-31."""

import argparse
import asyncio
import logging
import os
import socket
from contextlib import suppress
from datetime import UTC, datetime, timedelta

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.realtime.notifications import RedisNotifications
from tiewtrade.services.market_data.candle_realtime import CandleSupervisor
from tiewtrade.services.market_data.ingestion import MARKET_TIMEOUT, run_round
from tiewtrade.services.market_data.realtime import QuoteSupervisor
from tiewtrade.venues import (
    live_candle_feed,
    live_candle_source,
    live_price_feed,
    public_rate_limit_guard,
)
from tiewtrade.venues.candles import CandleSource
from tiewtrade.venues.price_streams import PriceFeed

ROUND_INTERVAL = timedelta(seconds=30)


def _now() -> datetime:
    return datetime.now(UTC)


async def serve(
    *,
    once: bool = False,
    source: CandleSource | None = None,
    engine: AsyncEngine | None = None,
    price_feed: PriceFeed | None = None,
) -> None:
    owned = engine is None
    engine = engine or create_engine_for(DatabaseRole.MARKET_DATA)
    worker = f"{socket.gethostname()}:{os.getpid()}"
    try:
        async with httpx.AsyncClient() as client:
            guard = public_rate_limit_guard(clock=_now)
            source = source or live_candle_source(
                client=client, clock=_now, timeout=MARKET_TIMEOUT, guard=guard
            )

            async def candles() -> None:
                while True:
                    summary = await run_round(engine, source, worker, _now())
                    logging.getLogger(__name__).info("market-data round: %s", summary)
                    if once:
                        return
                    await asyncio.sleep(ROUND_INTERVAL.total_seconds())

            if once:
                await candles()
                return
            feed = price_feed or live_price_feed(
                client=client, clock=_now, timeout=MARKET_TIMEOUT, guard=guard
            )
            url = os.environ.get("TIEWTRADE_REDIS_URL_MARKET_DATA", "")
            if not url:
                raise ValueError("TIEWTRADE_REDIS_URL_MARKET_DATA is required")
            redis = Redis.from_url(url)
            notification = RedisNotifications(redis)
            tasks = [
                asyncio.create_task(candles()),
                asyncio.create_task(QuoteSupervisor(engine, feed, notification).run()),
            ]
            if os.environ.get("TIEWTRADE_CHART_ENABLED") == "1":
                tasks.append(
                    asyncio.create_task(
                        CandleSupervisor(
                            engine,
                            live_candle_feed(clock=_now),
                            RedisNotifications(redis, channel="market.candles.changed"),
                        ).run()
                    )
                )
            try:
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                await notification.close()
                await redis.aclose()

    finally:
        if owned:
            await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    with suppress(KeyboardInterrupt):
        asyncio.run(serve(once=args.once))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
