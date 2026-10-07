"""Manual public-market-data runner; scheduling belongs to F-31."""

import argparse
import asyncio
import logging
import os
import socket
from contextlib import suppress
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.services.market_data.ingestion import MARKET_TIMEOUT, run_round
from tiewtrade.venues import live_candle_source
from tiewtrade.venues.candles import CandleSource

ROUND_INTERVAL = timedelta(seconds=30)


def _now() -> datetime:
    return datetime.now(UTC)


async def serve(
    *, once: bool = False, source: CandleSource | None = None, engine: AsyncEngine | None = None
) -> None:
    owned = engine is None
    engine = engine or create_engine_for(DatabaseRole.MARKET_DATA)
    worker = f"{socket.gethostname()}:{os.getpid()}"
    try:
        async with httpx.AsyncClient() as client:
            source = source or live_candle_source(client=client, clock=_now, timeout=MARKET_TIMEOUT)
            while True:
                summary = await run_round(engine, source, worker, _now())
                logging.getLogger(__name__).info("market-data round: %s", summary)
                if once:
                    break
                await asyncio.sleep(ROUND_INTERVAL.total_seconds())
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
