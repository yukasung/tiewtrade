"""Explicit R2-C1 measurement on dedicated capacity services; never a normal test.

Requires fresh migrated PG at 55434 and Redis at 56380. Leaves source/derived
evidence in that dedicated DB. Runtime containers are stopped after measurement.
C1 failure blocks dependent phases; it never becomes a passing availability gate.
"""

import argparse
import asyncio
import base64
import hashlib
import json
import os
import sys
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import UUID, uuid4

import httpx
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.market_data import CandleWindow, Timeframe, align_ceil, align_floor
from tiewtrade.core.money import Money, Scalar
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import indicator_read_session, market_data_session
from tiewtrade.infra.indicators.prepared import proof_valid
from tiewtrade.infra.market_data.catalog import PAIRS
from tiewtrade.infra.market_data.indicator_reader import query_budget, read_indicators
from tiewtrade.services.api.indicator_routes import IndicatorPointView, IndicatorValueView
from tiewtrade.services.api.settings import CSRF_COOKIE, CSRF_HEADER

SERIES = [(base, tf) for base, _ in sorted(PAIRS) for tf in Timeframe]
NETWORK = "tiewtrade-f11-capacity-net"
PG = "tiewtrade-f11-capacity-postgres"
REDIS = "tiewtrade-f11-capacity-redis"
INSERT = """INSERT INTO market_candles
 (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,finality,
 observed_at,fetch_started_at,last_checked_at,ingestion_generation)
 SELECT 'primary_spot',:base,'USDT',:tf,moment,moment+make_interval(secs=>:seconds),
 100.125+mod(n,17)/100.0,101.375+mod(n,17)/100.0,
 99.025+mod(n,17)/100.0,100.225+mod(n,17)/100.0,1.125,
 CASE WHEN moment+make_interval(secs=>:seconds)<=CAST(:now AS timestamptz)-interval '24 hours'
 THEN 'CLOSED' ELSE 'UNCONFIRMED' END,CAST(:now AS timestamptz),
 CAST(:now AS timestamptz),CAST(:now AS timestamptz),1
 FROM (SELECT moment,floor(extract(epoch FROM moment)/:seconds)::bigint AS n
 FROM generate_series(CAST(:lo AS timestamptz),
 CAST(:hi AS timestamptz)-make_interval(secs=>:seconds),
 make_interval(secs=>:seconds)) moment) slots
 ON CONFLICT(source,base,quote,timeframe,open_at) DO NOTHING"""


async def docker(*args: str, timeout: float = 20) -> str:
    process = await asyncio.create_subprocess_exec(
        "docker", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout)
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    if process.returncode:
        raise RuntimeError("CAPACITY_DOCKER_FAILED")
    return output.decode().strip()


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, default=str, indent=2) + "\n", encoding="utf-8")


def progress(*values: object) -> None:
    sys.stdout.write(" ".join(map(str, values)) + "\n")
    sys.stdout.flush()


async def insert_range(
    connection: Any, base: str, tf: Timeframe, lo: datetime, hi: datetime, now: datetime
) -> None:
    await connection.execute(
        text(INSERT),
        {
            "base": base,
            "tf": tf.value,
            "seconds": int(tf.span.total_seconds()),
            "lo": lo,
            "hi": hi,
            "now": now,
        },
    )


async def seed(engine: AsyncEngine) -> dict[str, datetime]:
    async with engine.connect() as c:
        assert (
            await c.execute(text("SELECT count(*) FROM indicator_build_jobs"))
        ).scalar_one() == 0
        assert (
            await c.execute(text("SELECT count(*) FROM indicator_generations"))
        ).scalar_one() == 0
        assert (await c.execute(text("SELECT count(*) FROM market_candles"))).scalar_one() == 0
        now: datetime = (await c.execute(text("SELECT clock_timestamp()"))).scalar_one()
    ends: dict[str, datetime] = {}
    for base, tf in SERIES:
        hi = align_floor(now, tf)
        lo = align_floor(now - timedelta(days=365, hours=6, minutes=15), tf)
        while lo < hi:
            stop = min(hi, lo + 50000 * tf.span)
            async with engine.begin() as c:
                await insert_range(c, base, tf, lo, stop, now)
            lo = stop
        ends[base + "/" + tf.value] = hi
        progress("seeded", base, tf.value)
    async with engine.begin() as c:
        await c.execute(text("ANALYZE market_candles"))
        await c.execute(text("SELECT activate_indicator_source_proof()"))
        # Isolated acceptance mode only: no synthetic heads and no production
        # activation bundle. Empty-derived API readiness must be observable.
        await c.execute(
            text("""UPDATE indicator_rollout_control SET mode='PREPARED',
          retention_policy='GRACE',codec_version=1,protocol_version=1,
          active_cursor_format=2 WHERE id=1""")
        )
    return ends


async def append(engine: AsyncEngine, ends: dict[str, datetime]) -> None:
    async with market_data_session(engine) as session:
        await session.execute("SELECT begin_indicator_source_write()")
        now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
        changed = {}
        for base, tf in SERIES:
            key = base + "/" + tf.value
            hi = align_floor(now, tf)
            if hi > ends[key]:
                await session.execute(
                    INSERT,
                    {
                        "base": base,
                        "tf": tf.value,
                        "seconds": int(tf.span.total_seconds()),
                        "lo": ends[key],
                        "hi": hi,
                        "now": now,
                    },
                )
                changed[key] = hi
    ends.update(changed)  # Advance only after commit; never rewrite existing input.


async def snapshot(engine: AsyncEngine) -> dict[str, Any]:
    async with engine.connect() as c:
        result = {}
        for name, sql in {
            "jobs": """SELECT base,timeframe,status,generation_sequence,first_eligible_at,
              availability_deadline,attempts_used,retry_not_before,last_served_round,
              deadline_missed_at,failure_category,failure_reason,failed_at
              FROM indicator_build_jobs ORDER BY base,timeframe""",
            "generations": """SELECT id,base,timeframe,as_of,status,checkpoint_count,
              prepared_at,failed_at,failure_code,candidate_sequence,
              calculation_start,calculation_end FROM indicator_generations""",
            "slot": """SELECT state,fence,dispatch_round,dispatch_cursor,attempt_deadline,
              last_heartbeat,generation_id FROM indicator_build_slot""",
        }.items():
            result[name] = [dict(r) for r in (await c.execute(text(sql))).mappings()]
        return result


async def observe(engine: AsyncEngine, user: UUID) -> list[dict[str, Any]]:
    rows = []
    async with indicator_read_session(engine, user) as s:
        await query_budget(s, monotonic() + 10)
        now = (await s.execute("SELECT clock_timestamp()")).scalar_one()
        generations = {
            (g["base"], g["timeframe"]): g
            for g in (
                await s.execute("""SELECT g.* FROM indicator_ready_heads h
                JOIN indicator_ready_generations g ON g.id=h.generation_id""")
            ).mappings()
        }
        for base, tf in SERIES:
            g = generations.get((base, tf.value))
            age = (now - g["as_of"]).total_seconds() if g is not None else None
            valid = g is not None and age is not None and 0 <= age <= 600
            if valid:
                assert g is not None
                valid = await proof_valid(s, g, now)
            rows.append(
                {
                    "base": base,
                    "timeframe": tf.value,
                    "valid": valid,
                    "age_seconds": age,
                    "observed_at": now,
                }
            )
    return rows


async def create_runtime(image: str, kind: str, metrics: Path | None = None) -> str:
    args = [
        "create",
        "--name",
        "tiewtrade-f11-capacity-" + kind,
        "--network",
        NETWORK,
        "--restart=no",
        "--cpus=2",
        "--memory=1g",
    ]
    if kind == "api":
        args += ["-p", "127.0.0.1::8000"]
        environment = {
            "TIEWTRADE_DATABASE_URL_API": f"postgresql+asyncpg://tiewtrade_api:dev_api@{PG}:5432/tiewtrade",
            "TIEWTRADE_DATABASE_URL_AUTH": f"postgresql+asyncpg://tiewtrade_auth:dev_auth@{PG}:5432/tiewtrade",
            "TIEWTRADE_REDIS_URL_API": f"redis://{REDIS}:6379/0",
            "TIEWTRADE_SIGNUP_OPEN": "1",
            "TIEWTRADE_COOKIE_SECURE": "0",
            "TIEWTRADE_PRICE_ORIGINS": "http://localhost:5173",
        }
        for purpose, byte in (
            ("TOTP_SECRET", b"T"),
            ("VENUE_API_SECRET", b"V"),
            ("INDICATOR_CURSOR", b"I"),
        ):
            environment["TIEWTRADE_SEALING_KEY_" + purpose] = (
                "1:" + base64.b64encode(byte * 32).decode()
            )
        command = [
            "uvicorn",
            "tiewtrade.services.api.app:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--no-access-log",
        ]
    else:
        environment = {
            "TIEWTRADE_DATABASE_URL_INDICATOR_BUILDER": f"postgresql+asyncpg://tiewtrade_indicator_builder:dev_indicator_builder@{PG}:5432/tiewtrade"
        }
        command = ["python", "-m", "tiewtrade.services.indicator_builder.main", "run"]
    if metrics is not None:
        metrics.mkdir(parents=True, exist_ok=True)
        scripts = Path(__file__).resolve().parent.as_posix()
        args += [
            "--mount",
            f"type=bind,source={scripts},target=/capacity,readonly",
            "--mount",
            f"type=bind,source={metrics.resolve().as_posix()},target=/evidence",
        ]
        environment["PYTHONPATH"] = (
            "/capacity" if kind == "api" else "/capacity/capacity_instrumentation"
        )
        if kind == "api":
            command[1] = "profile_capacity_app:app"
    for key, value in environment.items():
        args += ["-e", key + "=" + value]
    return await docker(*args, image, *command)


async def authenticate(container: str) -> tuple[list[httpx.AsyncClient], list[UUID]]:
    port = (await docker("port", container, "8000/tcp")).rsplit(":", 1)[1]
    clients = []
    users = []
    try:
        for index in range(5):
            client = httpx.AsyncClient(base_url="http://127.0.0.1:" + port, timeout=32)
            clients.append(client)
            async with asyncio.timeout(20):
                while True:
                    try:
                        response = await client.get("/auth/csrf")
                        if response.status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    await asyncio.sleep(0.1)
            response = await client.post(
                "/auth/register",
                json={
                    "email": f"capacity-{uuid4().hex}-{index}@example.com",
                    "password": "capacity fixture password only",
                },
                headers={CSRF_HEADER: str(client.cookies.get(CSRF_COOKIE))},
            )
            assert response.status_code == 201
            users.append(UUID(response.json()["user_id"]))
        return clients, users
    except BaseException:
        for client in clients:
            await client.aclose()
        raise


async def probes(
    clients: list[httpx.AsyncClient],
    started: float,
    barrier: Callable[[], Awaitable[None]] | None = None,
) -> list[dict[str, Any]]:
    results = []
    for index, (base, tf) in enumerate(SERIES):
        before = monotonic()
        try:
            request = clients[index // 6].get(
                "/market-data/indicators",
                params={"base": base, "quote": "USDT", "timeframe": tf.value},
                headers={"x-capacity-barrier": "1"} if index == 0 and barrier else None,
            )
            if index == 0 and barrier is not None:
                pending = asyncio.create_task(request)
                try:
                    await barrier()
                    response = await pending
                except BaseException:
                    pending.cancel()
                    await asyncio.gather(pending, return_exceptions=True)
                    raise
            else:
                response = await request
            body = response.json()
            body.pop("next_cursor", None)  # Never persist signed tokens.
            result = {
                "status": response.status_code,
                "body": body,
                "body_bytes": len(response.content),
            }
        except (httpx.TransportError, ValueError):
            result = {"status": 0, "body": {}, "body_bytes": 0}
        results.append(
            {
                "base": base,
                "timeframe": tf.value,
                "started_seconds": before - started,
                "finished_seconds": monotonic() - started,
                "elapsed_seconds": monotonic() - before,
                **result,
            }
        )
    return results


async def audit(engine: AsyncEngine, user: UUID, probes: list[dict[str, Any]]) -> None:
    cache: dict[tuple[str, str, str], Any] = {}
    for probe in probes:
        probe["correct"] = False
        if probe["status"] != 200:
            continue
        body = probe["body"]
        tf = Timeframe(probe["timeframe"])
        requested_at = datetime.fromisoformat(body["refresh"]["observed_at"])
        async with indicator_read_session(engine, user) as session:
            await query_budget(session, monotonic() + 10)
            generation = (
                (
                    await session.execute(
                        "SELECT * FROM indicator_ready_generations WHERE id=:id",
                        {"id": UUID(body["generation_id"])},
                    )
                )
                .mappings()
                .one()
            )
            expected_end = generation["calculation_end"]
            expected_start = max(
                align_ceil(requested_at - timedelta(days=365), tf), expected_end - 1000 * tf.span
            )
            metadata_ok = (
                body["source"] == "primary_spot" == generation["source"]
                and body["base"] == probe["base"] == generation["base"]
                and body["quote"] == "USDT" == generation["quote"]
                and body["timeframe"] == tf.value == generation["timeframe"]
                and body["formula_version"] == generation["formula_version"]
                and all(
                    datetime.fromisoformat(body[k]) == generation[k]
                    for k in ("as_of", "prepared_at", "calculation_start", "calculation_end")
                )
                and datetime.fromisoformat(body["result_start"]) == expected_start
                and datetime.fromisoformat(body["result_end"]) == expected_end
                and len(body["rows"]) == (expected_end - expected_start) // tf.span
                and timedelta(0) <= requested_at - generation["as_of"] <= timedelta(seconds=600)
                and await proof_valid(session, generation, requested_at)
            )
        probe["generation_id"] = body["generation_id"]
        probe["calculation_slots"] = (
            generation["calculation_end"] - generation["calculation_start"]
        ) // tf.span
        probe["response_rows"] = len(body["rows"])
        probe["response_rows_sha256"] = hashlib.sha256(
            json.dumps(body["rows"], sort_keys=True).encode()
        ).hexdigest()
        probe["dataset_revision"] = body["dataset_revision"]
        if not metadata_ok:
            probe.pop("body")
            continue
        key = (body["generation_id"], body["result_start"], body["result_end"])
        if key not in cache:

            def moment(name: str, value: dict[str, Any] = body) -> datetime:
                return datetime.fromisoformat(value[name])

            async with indicator_read_session(engine, user) as s:
                result = await read_indicators(
                    s,
                    probe["base"],
                    "USDT",
                    Timeframe(probe["timeframe"]),
                    CandleWindow(moment("calculation_start"), moment("calculation_end")),
                    CandleWindow(moment("result_start"), moment("result_end")),
                    moment("as_of"),
                    monotonic() + 600,
                )
            expected = [
                IndicatorPointView(
                    open_at=p.open_at,
                    seed_open_at=p.seed_open_at,
                    finality=p.finality.value if p.finality else None,
                    values={
                        name: IndicatorValueView(
                            value=(
                                v.value.as_text()
                                if isinstance(v.value, Scalar)
                                else v.value.as_parts()["amount"]
                                if v.value is not None
                                else None
                            ),
                            unit=v.value.currency if isinstance(v.value, Money) else None,
                            status=v.status.value,
                        )
                        for name, v in p.values.items()
                    },
                ).model_dump(mode="json")
                for p in result.points
            ]
            cache[key] = (result.revision, expected)
            progress("audited", probe["base"], probe["timeframe"])
        revision, expected = cache[key]
        probe["correct"] = (
            body["rows"] == expected
            and body["dataset_revision"] == revision
            and body["generation_age_seconds"] <= 600
            and probe["elapsed_seconds"] <= 30
            and probe["body_bytes"] <= 2 * 1024**2
        )
        probe.pop("body")  # Keep diagnostics small after full comparison.


async def run(
    output: Path, image: str, metrics: Path | None = None, reuse_source: bool = False
) -> int:
    for role in (DatabaseRole.MIGRATOR, DatabaseRole.API, DatabaseRole.MARKET_DATA):
        assert "@127.0.0.1:55434/tiewtrade" in os.environ[role.url_variable]
    assert os.environ["TIEWTRADE_TEST_REDIS_URL"] == "redis://127.0.0.1:56380/0"
    output.mkdir(parents=True, exist_ok=True)
    assert not (output / "result.json").exists()
    migrator = create_engine_for(DatabaseRole.MIGRATOR)
    api = create_engine_for(DatabaseRole.API)
    source = create_engine_for(DatabaseRole.MARKET_DATA)
    redis = Redis.from_url(os.environ["TIEWTRADE_TEST_REDIS_URL"])
    clients: list[httpx.AsyncClient] = []
    containers: list[str] = []
    observations: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    rounds: list[asyncio.Task[list[dict[str, Any]]]] = []
    cold_passed = metrics is None
    try:
        if reuse_source:
            async with migrator.connect() as c:
                for table in (
                    "indicator_build_jobs",
                    "indicator_generations",
                    "indicator_checkpoints",
                ):
                    assert (
                        await c.execute(text(f"SELECT count(*) FROM {table}"))
                    ).scalar_one() == 0
                ends = {
                    r["base"] + "/" + r["timeframe"]: r["end_at"]
                    for r in (
                        await c.execute(
                            text(
                                "SELECT base,timeframe,max(end_at) AS end_at "
                                "FROM market_candles GROUP BY base,timeframe"
                            )
                        )
                    ).mappings()
                }
                assert len(ends) == 30
        else:
            ends = await seed(migrator)
        image_id = await docker("image", "inspect", "--format", "{{.Id}}", image)
        save(
            output / "environment.json",
            {
                "image": image_id,
                "worker_api_cpu": 2,
                "worker_api_memory_bytes": 1024**3,
                "docker": await docker(
                    "info",
                    "--format",
                    "{{.OSType}} {{.Architecture}} CPUs={{.NCPU}} RAM={{.MemTotal}}",
                ),
                "c1_seconds": 600,
                "observer_interval_seconds": 10,
                "probe_interval_seconds": 60,
                "fixture": "365 days plus physical grace; fractional changing OHLC; append only",
            },
        )
        api_container = await create_runtime(image_id, "api", metrics)
        containers.append(api_container)
        await docker("start", api_container)
        if reuse_source:
            from tests.services.indicator_builder.profile_capacity_steady import login

            clients, users = await login()
        else:
            clients, users = await authenticate(api_container)
        worker = await create_runtime(image_id, "builder", metrics)
        containers.append(worker)
        while True:
            seconds, _ = await redis.time()
            if seconds % 60 <= 1:
                break
            await asyncio.sleep(0.25)
        await append(source, ends)
        async with migrator.connect() as c:
            db_t0: datetime = (await c.execute(text("SELECT clock_timestamp()"))).scalar_one()
        started = monotonic()  # Includes cold process startup; no excluded prewarm.
        await docker("start", worker)
        for tick in range(60):
            await asyncio.sleep(max(0, started + tick * 10 - monotonic()))
            if monotonic() - started >= 600:
                break
            await append(source, ends)
            observed = await observe(api, users[0])
            elapsed = monotonic() - started
            observations.append({"seconds": elapsed, "series": observed})
            trace.append({"seconds": elapsed, **await snapshot(migrator)})
            if tick % 6 == 0:
                # Any overlap is a failed schedule, not a skipped denominator.
                if rounds and not rounds[-1].done():
                    raise RuntimeError("CAPACITY_PROBE_ROUND_OVERLAP")
                rounds.append(asyncio.create_task(probes(clients, started)))
                progress(
                    "C1",
                    round(elapsed, 1),
                    "seconds; valid",
                    sum(r["valid"] for r in observed),
                    "/30",
                )
            save(output / "trace.json", trace)
            save(output / "observations.json", observations)
        await asyncio.sleep(max(0, started + 600 - monotonic()))
        cutoff_snapshot = await snapshot(migrator)
        for task in rounds:
            responses.extend(await task)
        save(output / "probes.json", responses)
        save(output / "cutoff.json", cutoff_snapshot)
        await docker("stop", "--time", "130", worker, timeout=140)
        save(
            output / "worker-log.json",
            {
                "log": await docker("logs", worker),
                "state": await docker("inspect", "--format", "{{json .State}}", worker),
            },
        )
        cold: list[dict[str, Any]] = []
        cold_offset = 0
        if metrics is not None:
            cold_offset = len((metrics / "api-metrics.jsonl").read_text().splitlines())
            await docker("restart", "--time", "5", api_container)
            port = (await docker("port", api_container, "8000/tcp")).rsplit(":", 1)[1]
            clients[0].base_url = httpx.URL("http://127.0.0.1:" + port)
            async with asyncio.timeout(20):
                while True:
                    try:
                        if (await clients[0].get("/auth/csrf")).status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    await asyncio.sleep(0.1)
            while True:
                seconds, _ = await redis.time()
                if seconds % 60 <= 1:
                    break
                await asyncio.sleep(0.2)
            for index in range(6):
                before = monotonic()
                response = await clients[0].get(
                    "/market-data/indicators",
                    params={"base": "BTC", "quote": "USDT", "timeframe": "1m"},
                )
                body = response.json()
                body.pop("next_cursor", None)
                cold.append(
                    {
                        "base": "BTC",
                        "timeframe": "1m",
                        "run": "cold" if index == 0 else "warm",
                        "status": response.status_code,
                        "body": body,
                        "body_bytes": len(response.content),
                        "elapsed_seconds": monotonic() - before,
                    }
                )
            save(output / "cold-warm.json", cold)
        await audit(api, users[0], responses + cold)
        if metrics is not None:
            cold_metrics = [
                json.loads(line)
                for line in (metrics / "api-metrics.jsonl").read_text().splitlines()[cold_offset:]
            ]
            save(output / "cold-warm-metrics.json", cold_metrics)
            save(output / "cold-warm.json", cold)
            cold_passed = (
                len(cold_metrics) == 6
                and all(
                    p["correct"] and p["calculation_slots"] == 525600 and p["response_rows"] == 1000
                    for p in cold
                )
                and all(
                    m["status"] == 200
                    and m["max_lag_seconds"] <= 0.1
                    and m["rss_delta_upper_bytes"] <= 128 * 1024**2
                    and m["candle_queries"] <= 2
                    for m in cold_metrics
                )
            )
            save(
                output / "r2-7.json",
                {"R2-7": "PASSED" if cold_passed else "FAILED"},
            )
        save(output / "probes.json", responses)
        summaries = []
        for base, tf in SERIES:
            samples = [
                s
                for o in observations
                for s in o["series"]
                if s["base"] == base and s["timeframe"] == tf.value
            ]
            accepted = [p for p in responses if p["base"] == base and p["timeframe"] == tf.value]
            ready = [p["finished_seconds"] for p in accepted if p["correct"]]
            summaries.append(
                {
                    "base": base,
                    "timeframe": tf.value,
                    "first_correct_200_seconds": min(ready) if ready else None,
                    "valid_samples": sum(s["valid"] for s in samples),
                    "scheduled_samples": 60,
                    "correct_probes": sum(p["correct"] for p in accepted),
                    "scheduled_probes": 10,
                    "passed": bool(ready)
                    and min(ready) <= 600
                    and len(samples) == 60
                    and len(accepted) == 10,
                }
            )
        passed = len(summaries) == 30 and all(s["passed"] for s in summaries)
        save(
            output / "result.json",
            {
                "R2-C1": "PASSED" if passed else "FAILED",
                "T0": db_t0,
                "R2-C2": "NOT_RUN",
                "R2-C3": "NOT_RUN",
                "R2-C4": "PARTIAL_TRACE",
                "R2-C5": "NOT_RUN",
                "R2-C6": "NOT_PASSED",
                "series": summaries,
                "note": "No capacity approval: C2-C6/resource gates require separate evidence.",
            },
        )
        return 0 if passed and cold_passed else 1
    finally:
        for task in rounds:
            if not task.done():
                task.cancel()
        await asyncio.gather(*rounds, return_exceptions=True)
        for client in clients:
            await client.aclose()
        for container in reversed(containers):
            await docker("stop", "--time", "130", container, timeout=140)
        await redis.aclose()
        for engine in (migrator, api, source):
            await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image", default="tiewtrade-f11-mixed-test:latest")
    parser.add_argument("--metrics", type=Path)
    parser.add_argument("--reuse-source", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.output, args.image, args.metrics, args.reuse_source)))
