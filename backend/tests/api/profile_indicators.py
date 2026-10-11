"""Diagnostic F-11 profiling; does not alter production resource limits.

Run directly on Linux against the disposable F-11 benchmark database.
The existing fixture is read only. Instrumentation is confined to this process.
"""

import asyncio
import cProfile
import hashlib
import json
import platform
import pstats
import sys
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from typing import Protocol, cast
from unittest.mock import patch
from uuid import uuid4

import httpx
from sqlalchemy import RowMapping

from tiewtrade.core.indicators import IndicatorStream, StreamBatch
from tiewtrade.core.market_data import Candle, CandleWindow, Timeframe
from tiewtrade.core.money.types import Money, Quantity
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import UserSession, indicator_read_session, market_data_session
from tiewtrade.infra.market_data import indicator_reader, storage
from tiewtrade.services.api.app import app
from tiewtrade.services.api.settings import CSRF_COOKIE, CSRF_HEADER


@dataclass
class Metric:
    calls: int = 0
    seconds: float = 0
    max_seconds: float = 0

    def add(self, elapsed: float) -> None:
        self.calls += 1
        self.seconds += elapsed
        self.max_seconds = max(self.max_seconds, elapsed)


class ProfileStats(Protocol):
    stats: dict[tuple[str, int, str], tuple[int, int, float, float, object]]
    total_tt: float


def timed[**P, T](function: Callable[P, T], metric: Metric) -> Callable[P, T]:
    def measure(*args: P.args, **kwargs: P.kwargs) -> T:
        started = perf_counter()
        try:
            return function(*args, **kwargs)
        finally:
            metric.add(perf_counter() - started)

    return measure


async def api_run(client: httpx.AsyncClient, instrumented: bool) -> dict[str, object]:
    metrics = {
        name: Metric()
        for name in (
            "db",
            "decode",
            "fetch_buffer",
            "core",
            "hash_timestamp",
            "hash_numbers",
            "hash_json",
            "hash_update",
        )
    }
    original_execute = UserSession.execute
    original_rows = indicator_reader.fetch_rows
    original_hash = hashlib.sha256

    async def execute(
        self: UserSession, statement: str, parameters: Mapping[str, object] | None = None
    ) -> object:
        started = perf_counter()
        try:
            return await original_execute(self, statement, parameters)
        finally:
            metrics["db"].add(perf_counter() - started)

    async def rows(
        session: UserSession, base: str, quote: str, timeframe: Timeframe, window: CandleWindow
    ) -> tuple[RowMapping, ...]:
        before = metrics["db"].seconds
        started = perf_counter()
        result = await original_rows(session, base, quote, timeframe, window)
        metrics["fetch_buffer"].add(perf_counter() - started - (metrics["db"].seconds - before))
        return result

    processed = [0]
    original_feed = IndicatorStream.feed_batch

    def feed(
        self: IndicatorStream,
        slots: tuple[tuple[datetime, Candle | None, datetime | None], ...],
        *,
        output_indices: tuple[int, ...],
    ) -> StreamBatch:
        started = perf_counter()
        try:
            result = original_feed(self, slots, output_indices=output_indices)
            processed[0] += len(slots)
            return result
        finally:
            metrics["core"].add(perf_counter() - started)

    class Hash:
        def __init__(self) -> None:
            self.inner = original_hash()

        def update(self, value: bytes) -> None:
            timed(self.inner.update, metrics["hash_update"])(value)

        def hexdigest(self) -> str:
            return self.inner.hexdigest()

    lag: list[float] = []

    async def monitor() -> None:
        previous = perf_counter()
        while True:
            await asyncio.sleep(0.01)
            current = perf_counter()
            lag.append(max(0, current - previous - 0.01))
            previous = current

    watcher = asyncio.create_task(monitor())
    started = perf_counter()
    try:
        if instrumented:
            with (
                patch.object(UserSession, "execute", execute),
                patch.object(
                    indicator_reader,
                    "decode_row",
                    timed(indicator_reader.decode_row, metrics["decode"]),
                ),
                patch.object(indicator_reader, "fetch_rows", rows),
                patch.object(IndicatorStream, "feed_batch", feed),
                patch.object(
                    indicator_reader,
                    "timestamp",
                    timed(indicator_reader.timestamp, metrics["hash_timestamp"]),
                ),
                patch.object(Money, "as_parts", timed(Money.as_parts, metrics["hash_numbers"])),
                patch.object(
                    Quantity, "as_parts", timed(Quantity.as_parts, metrics["hash_numbers"])
                ),
                patch.object(
                    indicator_reader,
                    "json",
                    SimpleNamespace(dumps=timed(json.dumps, metrics["hash_json"])),
                ),
                patch.object(indicator_reader, "hashlib", SimpleNamespace(sha256=Hash)),
            ):
                response = await client.get(
                    "/market-data/indicators",
                    params={"base": "BTC", "quote": "USDT", "timeframe": "1m"},
                )
        else:
            response = await client.get(
                "/market-data/indicators",
                params={"base": "BTC", "quote": "USDT", "timeframe": "1m"},
            )
        return {
            "instrumented": instrumented,
            "processed_slots": processed[0] if instrumented else None,
            "http_status": response.status_code,
            "error": response.json().get("detail"),
            "elapsed_seconds": perf_counter() - started,
            "event_loop_lag_seconds": max(lag, default=0),
            "metrics": {name: asdict(value) for name, value in metrics.items()},
        }
    finally:
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)


async def components() -> dict[str, object]:
    engine = create_engine_for(DatabaseRole.API)
    try:
        async with indicator_read_session(engine, uuid4()) as session:
            end = (
                await session.execute(
                    "SELECT max(end_at) FROM market_candles WHERE base='BTC' AND timeframe='1m'"
                )
            ).scalar_one()
            window = CandleWindow(end - timedelta(minutes=1000), end)
            rows = await storage.stored_rows(session, "BTC", "USDT", Timeframe.M1, window)
            if len(rows) != 1000:
                raise RuntimeError("benchmark fixture incomplete")
            stream = IndicatorStream("BTC", "USDT", Timeframe.M1, end)
            profile = cProfile.Profile()
            profile.enable()
            for offset in range(0, len(rows), 16):
                stream.feed_batch(
                    tuple(
                        (row.candle.open_at, row.candle, row.fetch_started_at)
                        for row in rows[offset : offset + 16]
                    ),
                    output_indices=(),
                )
            profile.disable()
            profile.dump_stats("/results/core.pstats")
            stats = cast(ProfileStats, pstats.Stats(profile))
            top = sorted(stats.stats.items(), key=lambda item: item[1][3], reverse=True)[:20]
            result = {
                "rows": len(rows),
                "profile_total_seconds": stats.total_tt,
                "top_cumulative": [
                    {
                        "file": Path(key[0]).name,
                        "line": key[1],
                        "function": key[2],
                        "calls": value[1],
                        "self_seconds": value[2],
                        "cumulative_seconds": value[3],
                    }
                    for key, value in top
                ],
            }
            started = perf_counter()
            sample_window = CandleWindow(end - timedelta(minutes=10000), end)
            sample = await indicator_reader.read_indicators(
                session,
                "BTC",
                "USDT",
                Timeframe.M1,
                sample_window,
                CandleWindow(end - timedelta(minutes=1000), end),
                end,
                perf_counter() + 30,
            )
            result["pipeline_10000"] = {
                "elapsed_seconds": perf_counter() - started,
                "output_rows": len(sample.points),
                "revision": sample.revision,
            }
            return result
    finally:
        await engine.dispose()


async def main() -> None:
    check = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(check) as session:
            count = (
                await session.execute(
                    "SELECT count(*) FROM market_candles WHERE base='BTC' AND timeframe='1m'"
                )
            ).scalar_one()
            pg = (await session.execute("SHOW server_version")).scalar_one()
            if count != 525600:
                raise RuntimeError("use existing full-size disposable benchmark fixture")
    finally:
        await check.dispose()
    result: dict[str, object] = {
        "python": platform.python_version(),
        "postgres": pg,
        "fixture_rows": count,
        "cpu_limit": "2vCPU",
        "memory_limit": "1GiB",
    }
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client,
    ):
        await client.get("/auth/csrf")
        registered = await client.post(
            "/auth/register",
            json={
                "email": f"profile-{uuid4().hex}@example.com",
                "password": "ProfilePasswordLongEnoughForTesting123!",
            },
            headers={CSRF_HEADER: str(client.cookies.get(CSRF_COOKIE, ""))},
        )
        registered.raise_for_status()
        runs = []
        for instrumented in (True,) if "--instrumented-only" in sys.argv else (False, True):
            run = await api_run(client, instrumented)
            runs.append(run)
            sys.stdout.write(json.dumps(run) + "\n")
            sys.stdout.flush()
        result["api_runs"] = runs
    result["core_cprofile"] = await components()
    Path("/results/profile.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
