"""Explicit isolated diagnostic; not a capacity acceptance runner."""

import argparse
import asyncio
import os
from pathlib import Path
from time import monotonic

from redis.asyncio import Redis
from sqlalchemy import text

from tests.services.indicator_builder import profile_capacity as capacity
from tests.services.indicator_builder import profile_capacity_steady as steady
from tiewtrade.infra.db import DatabaseRole, create_engine_for

maintain_source = capacity.maintain_source


async def next_admission_window(redis):
    # Use the same Redis clock as production admission; never clear its keys.
    seconds, micros = await redis.time()
    await asyncio.sleep(60 - seconds % 60 - micros / 1_000_000 + 0.1)


async def smoke_docker(*args, **kwargs):
    return await capacity.docker(
        *(a.replace("tiewtrade-f11-capacity-api", "tiewtrade-f11-smoke-api") for a in args),
        **kwargs,
    )


async def main(output, setup_seconds=600):
    for role in (DatabaseRole.MIGRATOR, DatabaseRole.API, DatabaseRole.MARKET_DATA):
        assert "@127.0.0.1:55434/tiewtrade" in os.environ[role.url_variable]
    assert os.environ["TIEWTRADE_TEST_REDIS_URL"] == "redis://127.0.0.1:56380/0"
    output.mkdir(parents=True, exist_ok=False)  # Never overwrite earlier evidence.
    steady.docker = smoke_docker
    engines = [
        create_engine_for(role)
        for role in (DatabaseRole.MIGRATOR, DatabaseRole.API, DatabaseRole.MARKET_DATA)
    ]
    migrator, api, source = engines
    clients = []
    redis = Redis.from_url(os.environ["TIEWTRADE_TEST_REDIS_URL"])
    stop = asyncio.Event()
    producer = None
    setup = monotonic()
    try:
        async with migrator.connect() as connection:
            ends = {
                r.base + "/" + r.timeframe: r.end_at
                for r in await connection.execute(
                    text(
                        "SELECT base,timeframe,max(end_at) AS end_at FROM market_candles "
                        "GROUP BY base,timeframe"
                    )
                )
            }
        assert len(ends) == 30
        capacity.save(output / "source-before.json", ends)
        await capacity.append(source, ends)
        producer = asyncio.create_task(maintain_source(source, ends, stop))
        clients, users = await steady.login()
        await capacity.docker("start", "tiewtrade-f11-smoke-builder")
        readiness = []
        while True:
            if producer.done():
                await producer  # Propagate source failures instead of timing out silently.
            observed = await capacity.observe(api, users[0])
            readiness.append({"seconds": monotonic() - setup, "series": observed})
            capacity.save(output / "readiness.json", readiness)
            snapshot = await capacity.snapshot(migrator)
            capacity.save(output / "snapshot.json", snapshot)
            ready = sum(r["valid"] for r in observed)
            capacity.progress("setup", round(monotonic() - setup, 1), "ready", ready)
            if ready == 30:
                break
            terminal = [job for job in snapshot["jobs"] if job["status"].startswith("FAILED_")]
            if terminal or monotonic() - setup >= setup_seconds:
                capacity.save(
                    output / "result.json",
                    {
                        "status": "SETUP_TERMINAL_FAILURE" if terminal else "SETUP_NOT_READY",
                        "seconds": monotonic() - setup,
                        "terminal_jobs": terminal,
                    },
                )
                return
            await asyncio.sleep(min(10, max(0, setup_seconds - (monotonic() - setup))))
        setup_seconds = monotonic() - setup
        started = monotonic()
        batches = []
        # Run alone: 5 users x 6 requests consumes the entire 30-request window.
        # Browser smoke must run after this runner, never share its window.
        async with asyncio.timeout(300):
            for _ in range(2):
                await next_admission_window(redis)
                if producer.done():
                    await producer
                batch = await capacity.probes(clients, started)
                for probe in batch:
                    body = probe.pop("body")
                    probe["generation_id"] = body.get("generation_id")
                    probe["rows"] = len(body.get("rows", []))
                    probe["as_of"] = body.get("as_of")
                batches.extend(batch)
                capacity.save(output / "probes.json", batches)
        capacity.save(
            output / "result.json",
            {
                "status": "DIAGNOSTIC_ONLY",
                "setup_seconds": setup_seconds,
                "measured_seconds": monotonic() - started,
                "responses": len(batches),
                "http_200": sum(p["status"] == 200 for p in batches),
                "note": "No full-scan parity audit in timed phase; not C1/C2/C6 acceptance.",
            },
        )
    finally:
        stop.set()
        if producer is not None:
            producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)
        for client in clients:
            await client.aclose()
        for engine in engines:
            await engine.dispose()
        await redis.aclose()
        await capacity.docker("stop", "--time", "130", "tiewtrade-f11-smoke-builder", timeout=140)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--setup-seconds", type=int, choices=range(1, 601), default=600)
    args = parser.parse_args()
    asyncio.run(main(args.output, args.setup_seconds))
