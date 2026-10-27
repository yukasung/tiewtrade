"""Explicit R2-C1 measurement on dedicated capacity services; never a normal test.

Requires fresh migrated PG and Redis at the configured isolated ports. Leaves
source/derived evidence in that dedicated DB. Runtime containers are stopped after measurement.
C1 failure blocks dependent phases; it never becomes a passing availability gate.
"""

import argparse
import asyncio
import base64
import hashlib
import json
import os
import sys
from collections.abc import Awaitable, Callable, Sequence
from contextlib import suppress
from datetime import datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import UUID, uuid4

import httpx
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.market_data import (
    CandleWindow,
    Timeframe,
    advance,
    align_ceil,
    align_floor,
    retention_cutoff,
    slot_count,
)
from tiewtrade.core.money import Money, Scalar
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.errors import DatabaseTimeoutError
from tiewtrade.infra.db.session import indicator_read_session, market_data_session
from tiewtrade.infra.indicators.prepared import proof_valid
from tiewtrade.infra.market_data.catalog import PAIRS
from tiewtrade.infra.market_data.indicator_reader import query_budget, read_indicators
from tiewtrade.services.api.indicator_routes import IndicatorPointView, IndicatorValueView
from tiewtrade.services.api.settings import CSRF_COOKIE, CSRF_HEADER

CAPACITY_TIMEFRAMES = tuple(Timeframe)
READINESS_SERIES = [(base, tf) for base, _ in sorted(PAIRS) for tf in CAPACITY_TIMEFRAMES]
# Long-running accepted/rejected load is deliberately BTC-only. Runtime readiness
# remains all supported pairs so PREPARED never certifies an unprepared ETH series.
SERIES = [("BTC", tf) for tf in CAPACITY_TIMEFRAMES]
CAPACITY_PREFIX = os.environ.get("TIEWTRADE_CAPACITY_PREFIX", "tiewtrade-f11-capacity")
CAPACITY_HOST = os.environ.get("TIEWTRADE_CAPACITY_HOST", "127.0.0.1")
CAPACITY_API_HOST = os.environ.get("TIEWTRADE_CAPACITY_API_HOST", "127.0.0.1")
CAPACITY_POSTGRES_PORT = int(os.environ.get("TIEWTRADE_CAPACITY_POSTGRES_PORT", "55434"))
CAPACITY_REDIS_PORT = int(os.environ.get("TIEWTRADE_CAPACITY_REDIS_PORT", "56380"))
NETWORK = CAPACITY_PREFIX + "-net"
PG = CAPACITY_PREFIX + "-postgres"
REDIS = CAPACITY_PREFIX + "-redis"


def runtime_name(kind: str) -> str:
    return CAPACITY_PREFIX + "-" + kind


def capacity_api_url(port: str) -> str:
    return f"http://{CAPACITY_API_HOST}:{port}"


def exact_build_terminal_failure(job: Any) -> str | None:
    """Return a terminal exact-fixture failure without rejecting queued retries."""
    status = str(job["status"])
    reason = job["failure_reason"]
    if status.startswith("FAILED_") and reason:
        return f"{status}:{job['failure_category']}:{reason}"
    return None


def exact_build_retry_is_eligible(job: Any, observed: datetime) -> bool:
    """Return whether an exact-fixture retry can be claimed by a fresh worker."""
    return (
        str(job["status"]) == "QUEUED"
        and job["retry_not_before"] is not None
        and job["retry_not_before"] <= observed
    )


def exact_retry_requires_clock_release(
    job: Any, observed: datetime, pinned_boundary: datetime
) -> bool:
    """Bridge elapsed wall backoff into the deliberately pinned fixture clock."""
    eligible = exact_build_retry_is_eligible(job, observed)
    return eligible and job["retry_not_before"] > pinned_boundary


def capacity_scope_metadata() -> dict[str, int]:
    """Describe the approved F-38 runtime and measured workload inventories."""
    return {
        "supported_runtime_pairs": len(PAIRS),
        "runtime_readiness_series": len(READINESS_SERIES),
        "profile_pairs": len({base for base, _ in SERIES}),
        "profile_series": len(SERIES),
    }


INSERT = """INSERT INTO market_candles
 (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,finality,
 observed_at,fetch_started_at,last_checked_at,ingestion_generation)
 SELECT 'primary_spot',:base,'USDT',:tf,moment,
 CASE WHEN :tf='1M' THEN moment+interval '1 month'
 ELSE moment+make_interval(secs=>:seconds) END,
 100.125+mod(n,17)/100.0,101.375+mod(n,17)/100.0,
 99.025+mod(n,17)/100.0,100.225+mod(n,17)/100.0,1.125,
 CASE WHEN (CASE WHEN :tf='1M' THEN moment+interval '1 month'
 ELSE moment+make_interval(secs=>:seconds) END)<=CAST(:now AS timestamptz)-interval '24 hours'
 THEN 'CLOSED' ELSE 'UNCONFIRMED' END,CAST(:now AS timestamptz),
 CAST(:now AS timestamptz),CAST(:now AS timestamptz),1
 FROM (SELECT moment,row_number() OVER (ORDER BY moment)::bigint AS n
 FROM generate_series(CAST(:lo AS timestamptz),
 CAST(:hi AS timestamptz)-CASE WHEN :tf='1M' THEN interval '1 month'
 ELSE make_interval(secs=>:seconds) END,
 CASE WHEN :tf='1M' THEN interval '1 month'
 ELSE make_interval(secs=>:seconds) END) moment) slots
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
            "seconds": int(tf.fixed_span.total_seconds()) if tf.fixed_span else 0,
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
    for base, tf in READINESS_SERIES:
        hi = align_floor(now, tf)
        lo = align_floor(retention_cutoff(now, tf) - timedelta(hours=6, minutes=15), tf)
        while lo < hi:
            stop = min(hi, advance(lo, tf, 50000))
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
          retention_policy='GRACE',codec_version=2,protocol_version=1,
          active_cursor_format=2 WHERE id=1""")
        )
    return ends


async def append(
    engine: AsyncEngine,
    ends: dict[str, datetime],
    series: Sequence[tuple[str, Timeframe]] = READINESS_SERIES,
) -> None:
    async with engine.connect() as connection:
        current: datetime = (
            await connection.execute(text("SELECT clock_timestamp()"))
        ).scalar_one()
    pending = [
        (base, tf, base + "/" + tf.value, align_floor(current, tf))
        for base, tf in series
        if align_floor(current, tf) > ends[base + "/" + tf.value]
    ]
    if not pending:
        return
    async with market_data_session(engine) as session:
        await session.execute("SELECT begin_indicator_source_write()")
        now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
        changed = {}
        for base, tf, key, hi in pending:
            await session.execute(
                INSERT,
                {
                    "base": base,
                    "tf": tf.value,
                    "seconds": int(tf.fixed_span.total_seconds()) if tf.fixed_span else 0,
                    "lo": ends[key],
                    "hi": hi,
                    "now": now,
                },
            )
            changed[key] = hi
    ends.update(changed)  # Advance only after commit; never rewrite existing input.


async def maintain_source(
    engine: AsyncEngine,
    ends: dict[str, datetime],
    stop: asyncio.Event,
    series: Sequence[tuple[str, Timeframe]] = READINESS_SERIES,
) -> None:
    """Keep source arrivals independent of HTTP probes and readiness polling."""
    while not stop.is_set():
        await append(engine, ends, series)
        with suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), 0.25)


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
        for base, tf in READINESS_SERIES:
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
        runtime_name(kind),
        "--network",
        NETWORK,
        "--restart=no",
        "--cpus=2",
        "--memory=1g",
    ]
    cpuset = os.environ.get("TIEWTRADE_CAPACITY_" + kind.upper() + "_CPUSET")
    if cpuset:
        args += ["--cpuset-cpus", cpuset]
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
            client = httpx.AsyncClient(base_url=capacity_api_url(port), timeout=32)
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
                barrier_task = asyncio.ensure_future(barrier())
                try:
                    done, _ = await asyncio.wait(
                        (pending, barrier_task), return_when=asyncio.FIRST_COMPLETED
                    )
                    if (
                        pending in done
                        and pending.result().status_code != 200
                        and not (
                            pending.result().status_code == 503
                            and pending.result().json().get("detail") == "INDICATOR_DATA_NOT_READY"
                        )
                    ):
                        raise RuntimeError(
                            "CAPACITY_BARRIER_REQUEST_REJECTED_" + str(pending.result().status_code)
                        )
                    await barrier_task
                    response = await pending
                except BaseException:
                    pending.cancel()
                    barrier_task.cancel()
                    await asyncio.gather(pending, barrier_task, return_exceptions=True)
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


async def audit(engine: AsyncEngine, user: UUID, probes: list[dict[str, Any]]) -> int:
    cache: dict[tuple[str, str, str], Any] = {}
    timeout_retries = 0
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
                align_ceil(retention_cutoff(requested_at, tf), tf),
                advance(expected_end, tf, -1000),
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
                and len(body["rows"]) == slot_count(CandleWindow(expected_start, expected_end), tf)
                and timedelta(0) <= requested_at - generation["as_of"] <= timedelta(seconds=600)
                and await proof_valid(session, generation, requested_at)
            )
        probe["generation_id"] = body["generation_id"]
        probe["calculation_slots"] = slot_count(
            CandleWindow(generation["calculation_start"], generation["calculation_end"]), tf
        )
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

            for attempt in range(3):
                try:
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
                    break
                except DatabaseTimeoutError:
                    if attempt == 2:
                        raise
                    timeout_retries += 1
                    progress("audit timeout; retrying", probe["base"], probe["timeframe"])
                    await asyncio.sleep(1)
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
    return timeout_retries


async def prepare_exact_r2_7_generation(
    migrator: AsyncEngine, source: AsyncEngine, worker: str, clock_marker: Path
) -> dict[str, Any]:
    """Build the approved 525,600-slot fixture at an exact minute boundary.

    A live scheduler snapshot intentionally excludes the candle intersecting a
    non-aligned retention cutoff, so it contains 525,599 one-minute slots.  R2-7
    instead requires the existing exact max-input fixture.  Pin only the
    calculation bounds in this isolated database while the source is idle;
    production clock/window behavior remains unchanged.
    """
    originals: list[str] = []
    async with migrator.connect() as connection:
        observed: datetime = (
            await connection.execute(text("SELECT clock_timestamp()"))
        ).scalar_one()
        boundary: datetime = (
            await connection.execute(
                text(
                    "SELECT max(end_at) FROM market_candles "
                    "WHERE source='primary_spot' AND base='BTC' AND quote='USDT' "
                    "AND timeframe='1m'"
                )
            )
        ).scalar_one()
        assert boundary is not None and boundary == align_floor(boundary, Timeframe.M1)
        boundary_age = observed - boundary
        assert timedelta(0) <= boundary_age <= timedelta(seconds=10)
        ready_end: datetime = (
            await connection.execute(
                text(
                    "SELECT g.calculation_end FROM indicator_ready_heads h "
                    "JOIN indicator_generations g ON g.id=h.generation_id "
                    "WHERE g.source='primary_spot' AND g.base='BTC' "
                    "AND g.quote='USDT' AND g.timeframe='1m'"
                )
            )
        ).scalar_one()
        start = boundary - timedelta(days=365)
        source_rows = int(
            (
                await connection.execute(
                    text(
                        "SELECT count(*) FROM market_candles "
                        "WHERE source='primary_spot' AND base='BTC' AND quote='USDT' "
                        "AND timeframe='1m' AND open_at>=:start AND open_at<:end"
                    ),
                    {"start": start, "end": boundary},
                )
            ).scalar_one()
        )
        assert source_rows == 525600

    invalidation_open_at = advance(ready_end, Timeframe.M1, -1)
    async with market_data_session(source) as session:
        await session.execute("SELECT begin_indicator_source_write()")
        changed = await session.execute(
            """UPDATE market_candles SET
              close=CASE WHEN close=100.625 THEN 100.725 ELSE 100.625 END,
              last_checked_at=clock_timestamp()
            WHERE source='primary_spot' AND base='BTC' AND quote='USDT'
              AND timeframe='1m' AND open_at=:moment RETURNING 1""",
            {"moment": invalidation_open_at},
        )
        assert changed.scalar_one() == 1

    async with migrator.begin() as connection:
        await connection.execute(
            text("CREATE TABLE capacity_indicator_clock_state(moment timestamptz NOT NULL)")
        )
        await connection.execute(
            text("INSERT INTO capacity_indicator_clock_state VALUES(:moment)"),
            {"moment": boundary},
        )
        await connection.execute(
            text(
                """CREATE FUNCTION capacity_indicator_clock() RETURNS timestamptz
                LANGUAGE sql VOLATILE SECURITY DEFINER
                SET search_path=pg_catalog,public AS $$
                SELECT moment FROM public.capacity_indicator_clock_state $$"""
            )
        )
        await connection.execute(
            text("REVOKE ALL ON FUNCTION capacity_indicator_clock() FROM PUBLIC")
        )
        await connection.execute(
            text(
                "GRANT EXECUTE ON FUNCTION capacity_indicator_clock() "
                "TO tiewtrade_indicator_builder"
            )
        )
        originals = list(
            (
                await connection.execute(
                    text(
                        """SELECT pg_get_functiondef(p.oid)
                        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                        WHERE n.nspname='public' AND p.proname='indicator_calculation_bounds'
                        ORDER BY p.proname"""
                    )
                )
            ).scalars()
        )
        assert len(originals) == 1
        for definition in originals:
            assert definition.count("BEGIN\n") == 1
            await connection.execute(
                text(
                    definition.replace("IMMUTABLE", "VOLATILE").replace(
                        "BEGIN\n", "BEGIN\n  p_as_of:=public.capacity_indicator_clock();\n", 1
                    )
                )
            )

    exact: dict[str, Any] | None = None
    released_retry_backoffs = 0
    try:
        clock_marker.write_text(str(boundary), encoding="ascii")
        await docker("start", worker)
        deadline = monotonic() + 600
        while monotonic() < deadline:
            async with migrator.connect() as connection:
                row = (
                    (
                        await connection.execute(
                            text(
                                """SELECT g.id,g.calculation_start,g.calculation_end,
                                g.as_of,g.checkpoint_count
                                FROM indicator_ready_heads h
                                JOIN indicator_generations g ON g.id=h.generation_id
                                WHERE g.source='primary_spot' AND g.base='BTC'
                                  AND g.quote='USDT' AND g.timeframe='1m'"""
                            )
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                job = (
                    (
                        await connection.execute(
                            text(
                                """SELECT id,status,attempts_used,retry_not_before,
                                failure_category,failure_reason,clock_timestamp() AS observed
                                FROM indicator_build_jobs
                                WHERE source='primary_spot' AND base='BTC'
                                  AND quote='USDT' AND timeframe='1m'"""
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
            if (
                row is not None
                and row["calculation_start"] == start
                and row["calculation_end"] == boundary
                and slot_count(CandleWindow(start, boundary), Timeframe.M1) == 525600
            ):
                exact = dict(row)
                break
            if failure := exact_build_terminal_failure(job):
                raise RuntimeError("CAPACITY_EXACT_FIXTURE_BUILD_FAILED:" + failure)
            if exact_retry_requires_clock_release(job, job["observed"], boundary):
                # The exact fixture pins the indicator SQL clock so the input remains
                # exactly 525,600 slots. Honor the production backoff against real DB
                # time first, then expose that elapsed backoff to the pinned clock.
                async with migrator.begin() as connection:
                    released = (
                        await connection.execute(
                            text(
                                """UPDATE indicator_build_jobs SET retry_not_before=:boundary
                                WHERE id=:id AND status='QUEUED'
                                  AND retry_not_before=:retry_not_before RETURNING id"""
                            ),
                            {
                                "boundary": boundary,
                                "id": job["id"],
                                "retry_not_before": job["retry_not_before"],
                            },
                        )
                    ).scalar_one_or_none()
                released_retry_backoffs += int(released is not None)
            if exact_build_retry_is_eligible(job, job["observed"]):
                running = await docker("inspect", "--format", "{{.State.Running}}", worker)
                if running != "true":
                    await docker("start", worker)
            await asyncio.sleep(0.5)
        if exact is None:
            raise RuntimeError("CAPACITY_EXACT_FIXTURE_NOT_READY")
    finally:
        await docker("stop", "--time", "130", worker, timeout=140)
        clock_marker.unlink(missing_ok=True)
        async with migrator.begin() as connection:
            for definition in originals:
                await connection.execute(text(definition))
            await connection.execute(text("DROP FUNCTION capacity_indicator_clock()"))
            await connection.execute(text("DROP TABLE capacity_indicator_clock_state"))

    return {
        "boundary": boundary,
        "boundary_age_seconds": boundary_age.total_seconds(),
        "source_rows": source_rows,
        "logical_slots": 525600,
        "released_retry_backoffs": released_retry_backoffs,
        "invalidation_open_at": invalidation_open_at,
        "generation": exact,
    }


async def run(
    output: Path, image: str, metrics: Path | None = None, reuse_source: bool = False
) -> int:
    for role in (DatabaseRole.MIGRATOR, DatabaseRole.API, DatabaseRole.MARKET_DATA):
        assert (
            f"@{CAPACITY_HOST}:{CAPACITY_POSTGRES_PORT}/tiewtrade" in os.environ[role.url_variable]
        )
    assert os.environ["TIEWTRADE_TEST_REDIS_URL"] == (
        f"redis://{CAPACITY_HOST}:{CAPACITY_REDIS_PORT}/0"
    )
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
    source_stop = asyncio.Event()
    producer: asyncio.Task[None] | None = None
    try:
        if reuse_source:
            async with migrator.begin() as c:
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
                assert len(ends) == len(READINESS_SERIES)
                await c.execute(
                    text("""UPDATE indicator_rollout_control SET mode='PREPARED',
                    retention_policy='GRACE',codec_version=2,protocol_version=1,
                    active_cursor_format=2 WHERE id=1""")
                )
        else:
            ends = await seed(migrator)
        image_id = await docker("image", "inspect", "--format", "{{.Id}}", image)
        save(
            output / "environment.json",
            {
                "image": image_id,
                "worker_api_cpu": 2,
                "worker_api_memory_bytes": 1024**3,
                "api_cpuset": os.environ.get("TIEWTRADE_CAPACITY_API_CPUSET"),
                "builder_cpuset": os.environ.get("TIEWTRADE_CAPACITY_BUILDER_CPUSET"),
                "docker": await docker(
                    "info",
                    "--format",
                    "{{.OSType}} {{.Architecture}} CPUs={{.NCPU}} RAM={{.MemTotal}}",
                ),
                "c1_seconds": 600,
                "observer_interval_seconds": 10,
                "probe_interval_seconds": 60,
                "fixture": "365 days plus physical grace; fractional changing OHLC; append only",
                "capacity_prefix": CAPACITY_PREFIX,
                "api_probe_host": CAPACITY_API_HOST,
                "postgres_endpoint": f"{CAPACITY_HOST}:{CAPACITY_POSTGRES_PORT}/tiewtrade",
                "redis_endpoint": f"{CAPACITY_HOST}:{CAPACITY_REDIS_PORT}/0",
                **capacity_scope_metadata(),
            },
        )
        api_container = await create_runtime(image_id, "api", metrics)
        containers.append(api_container)
        await docker("start", api_container)
        if reuse_source:
            from tests.services.indicator_builder.profile_capacity_steady import login

            account_count = int(
                await docker(
                    "exec",
                    PG,
                    "psql",
                    "-U",
                    "postgres",
                    "-d",
                    "tiewtrade",
                    "-Atc",
                    "SELECT count(*) FROM user_credentials "
                    "WHERE email LIKE 'capacity-%@example.com'",
                )
            )
            if account_count == 0:
                clients, users = await authenticate(api_container)
            else:
                assert account_count == 5
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
        producer = asyncio.create_task(maintain_source(source, ends, source_stop))
        await docker("start", worker)
        for tick in range(60):
            await asyncio.sleep(max(0, started + tick * 10 - monotonic()))
            if monotonic() - started >= 600:
                break
            if producer.done():
                await producer
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
                    "/" + str(len(READINESS_SERIES)),
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
            while True:
                seconds, _ = await redis.time()
                if seconds % 60 <= 1:
                    break
                await asyncio.sleep(0.2)
            source_stop.set()
            if producer is not None:
                await producer
                producer = None
            await append(source, ends)
            save(
                output / "exact-fixture-preparation.json",
                await prepare_exact_r2_7_generation(
                    migrator, source, worker, metrics / "exact-clock-enabled"
                ),
            )
            cold_offset = len((metrics / "api-metrics.jsonl").read_text().splitlines())
            await docker("restart", "--time", "5", api_container)
            port = (await docker("port", api_container, "8000/tcp")).rsplit(":", 1)[1]
            clients[0].base_url = httpx.URL(capacity_api_url(port))
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
        audit_timeout_retries = await audit(api, users[0], responses + cold)
        save(output / "audit.json", {"database_timeout_retries": audit_timeout_retries})
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
                    and m["candle_queries"] <= 8
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
        readiness_passed = all(
            any(
                sample["valid"]
                for observation in observations
                for sample in observation["series"]
                if sample["base"] == base and sample["timeframe"] == tf.value
            )
            for base, tf in READINESS_SERIES
        )
        passed = (
            readiness_passed
            and len(summaries) == len(SERIES)
            and all(s["passed"] for s in summaries)
        )
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
                **capacity_scope_metadata(),
                "runtime_readiness_passed": readiness_passed,
                "series": summaries,
                "note": "No capacity approval: C2-C6/resource gates require separate evidence.",
            },
        )
        return 0 if passed and cold_passed else 1
    finally:
        active_error = sys.exception()
        source_stop.set()
        if producer is not None:
            producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)
        for task in rounds:
            if not task.done():
                task.cancel()
        await asyncio.gather(*rounds, return_exceptions=True)
        for client in clients:
            await client.aclose()
        for container in reversed(containers):
            try:
                await docker("stop", "--time", "130", container, timeout=140)
            except BaseException:
                # Preserve the workload/setup failure that triggered cleanup;
                # otherwise a later Docker timeout hides the actionable cause.
                if active_error is None:
                    raise
                await docker("kill", container)
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
