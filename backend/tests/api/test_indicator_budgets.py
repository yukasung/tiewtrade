"""Standalone V-15 Linux runner: prepare fixture in a separate process first."""

import asyncio
import json
import sys
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import httpx

from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.services.api.app import app
from tiewtrade.services.api.settings import CSRF_COOKIE, CSRF_HEADER


def _rss(name: str) -> int:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith(name + ":"):
            return int(line.split()[1])
    raise RuntimeError("Linux RSS counter unavailable")


async def prepare_fixture() -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(engine) as session:
            await session.execute("DELETE FROM market_candles")
            await session.execute("""INSERT INTO market_candles
                (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,
                 finality,observed_at,fetch_started_at,last_checked_at,ingestion_generation)
                SELECT 'primary_spot','BTC','USDT','1m',moment,moment+interval '1 minute',
                100,101,99,100,1,'UNCONFIRMED',clock_timestamp(),clock_timestamp(),
                clock_timestamp(),1 FROM generate_series(
                date_trunc('minute',clock_timestamp())-interval '365 days',
                date_trunc('minute',clock_timestamp())-interval '1 minute',
                interval '1 minute') AS moment""")
    finally:
        await engine.dispose()


async def benchmark() -> None:
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
                "email": f"benchmark-{uuid4().hex}@example.com",
                "password": "BenchmarkPasswordLongEnoughForTests123!",
            },
            headers={CSRF_HEADER: str(client.cookies.get(CSRF_COOKIE, ""))},
        )
        registered.raise_for_status()
        baseline = _rss("VmRSS")
        results: list[dict[str, object]] = []
        for run in range(6):
            lag: list[float] = []

            async def monitor(samples: list[float] = lag) -> None:
                previous = perf_counter()
                while True:
                    await asyncio.sleep(0.01)
                    current = perf_counter()
                    samples.append(max(0, current - previous - 0.01))
                    previous = current

            watcher = asyncio.create_task(monitor())
            started = perf_counter()
            try:
                response = await client.get(
                    "/market-data/indicators",
                    params={"base": "BTC", "quote": "USDT", "timeframe": "1m"},
                )
                elapsed = perf_counter() - started
            finally:
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
            peak_delta = _rss("VmHWM") - baseline
            maximum_lag = max(lag, default=0)
            result = {
                "run": run,
                "status": response.status_code,
                "elapsed_seconds": elapsed,
                "idle_rss_kib": baseline,
                "peak_rss_delta_kib": peak_delta,
                "event_loop_lag_seconds": maximum_lag,
                "response_bytes": len(response.content),
                "error": response.json().get("detail"),
            }
            results.append(result)
            sys.stdout.write(json.dumps(result) + "\n")
            sys.stdout.flush()
            Path("/results/benchmark.json").write_text(json.dumps(results, indent=2) + "\n")
            if (
                response.status_code != 200
                or elapsed > 30
                or maximum_lag > 0.1
                or peak_delta > 128 * 1024
                or len(response.content) > 2 * 1024 * 1024
            ):
                raise RuntimeError("V-15 full-size benchmark failed")
            body = response.json()
            if len(body["rows"]) != 1000:
                raise RuntimeError("incorrect output size")
            for row in body["rows"]:
                for name, value in row["values"].items():
                    if value["status"] == "READY":
                        expected = (
                            "100"
                            if name.startswith("ema")
                            else "50"
                            if name == "rsi14"
                            else "2"
                            if name == "atr14"
                            else "0"
                        )
                        if value["value"] != expected:
                            raise RuntimeError("incorrect constant-price result")
                    elif value["status"] != "GAP" or value["value"] is not None:
                        raise RuntimeError("unexpected constant-price status")


if __name__ == "__main__":
    asyncio.run(prepare_fixture() if "--prepare" in sys.argv else benchmark())
