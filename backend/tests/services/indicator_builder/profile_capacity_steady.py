"""Real-time R2-C2/C3/C5, using a measured C1 dataset and the real launcher.

Stops on an observed availability failure. An early failure never claims that
the required 60-minute success interval was completed. No clock acceleration.
"""

import argparse
import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import UUID

import httpx
from redis.asyncio import Redis
from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.services.indicator_builder.profile_capacity import (
    CAPACITY_HOST,
    CAPACITY_POSTGRES_PORT,
    CAPACITY_REDIS_PORT,
    PG,
    READINESS_SERIES,
    SERIES,
    append,
    audit,
    capacity_api_url,
    capacity_scope_metadata,
    docker,
    maintain_source,
    observe,
    probes,
    progress,
    runtime_name,
    save,
    snapshot,
)
from tiewtrade.core.market_data import Timeframe, advance
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import indicator_read_session, market_data_session
from tiewtrade.infra.indicators.prepared import proof_valid
from tiewtrade.infra.market_data.indicator_reader import query_budget
from tiewtrade.services.api.settings import CSRF_COOKIE, CSRF_HEADER


async def login() -> tuple[list[httpx.AsyncClient], list[UUID]]:
    # Only public synthetic fixture emails, in memory; no credential/hash query.
    emails = (
        await docker(
            "exec",
            PG,
            "psql",
            "-U",
            "postgres",
            "-d",
            "tiewtrade",
            "-Atc",
            "SELECT email FROM user_credentials "
            "WHERE email LIKE 'capacity-%@example.com' ORDER BY email",
        )
    ).splitlines()
    assert len(emails) == 5
    port = (await docker("port", runtime_name("api"), "8000/tcp")).rsplit(":", 1)[1]
    clients = []
    users = []
    try:
        for email in emails:
            client = httpx.AsyncClient(base_url=capacity_api_url(port), timeout=32)
            clients.append(client)
            async with asyncio.timeout(20):
                while True:
                    try:
                        if (await client.get("/auth/csrf")).status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    await asyncio.sleep(0.1)
            response = await client.post(
                "/auth/login",
                json={"email": email, "password": "capacity fixture password only"},
                headers={CSRF_HEADER: str(client.cookies.get(CSRF_COOKIE))},
            )
            assert response.status_code == 200
            users.append(UUID(response.json()["user_id"]))
        return clients, users
    except BaseException:
        for client in clients:
            await client.aclose()
        raise


def signature(body: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                k: body[k]
                for k in (
                    "source",
                    "generation_id",
                    "prepared_at",
                    "rows",
                    "dataset_revision",
                    "base",
                    "quote",
                    "timeframe",
                    "formula_version",
                    "as_of",
                    "calculation_start",
                    "calculation_end",
                    "result_start",
                    "result_end",
                )
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()


def workload_readiness(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Restrict long-running phase decisions to the approved BTC-only workload."""
    workload = {(base, timeframe.value) for base, timeframe in SERIES}
    selected = [row for row in rows if (row["base"], row["timeframe"]) in workload]
    assert len(selected) == len(SERIES)
    return selected


def capacity_gates(phase: str, *, under_load: bool, combined: bool) -> tuple[str, ...]:
    """Return the machine gates emitted by one measured phase."""
    if phase not in {"steady", "dirty"}:
        raise ValueError("unknown capacity phase")
    if combined:
        if not under_load:
            raise ValueError("combined capacity evidence requires rejected load")
        return ("R2-C3", "R2-C5-dirty") if phase == "dirty" else ("R2-C2", "R2-C5-steady")
    if under_load:
        return ("R2-C5-" + phase,)
    return ("R2-C3",) if phase == "dirty" else ("R2-C2",)


def capacity_prerequisites(phase: str, *, under_load: bool, combined: bool) -> tuple[str, ...]:
    """Return gates that must already be passed before a measured phase."""
    if combined:
        return ("R2-C2", "R2-C5-steady") if phase == "dirty" else ()
    if under_load:
        return ("R2-C5-steady",) if phase == "dirty" else ("R2-C3",)
    return ("R2-C2",) if phase == "dirty" else ()


def readiness_baseline_is_quiescent(rows: list[dict[str, Any]], metadata: dict[str, Any]) -> bool:
    """Require the 16-series refresh to finish before a measured BTC phase."""
    return (
        all(row["valid"] for row in rows)
        and len(metadata["jobs"]) == len(READINESS_SERIES)
        and all(job["status"] == "READY" for job in metadata["jobs"])
        and len(metadata["slot"]) == 1
        and metadata["slot"][0]["state"] == "IDLE"
    )


def rejected_load_is_complete(
    rejected: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    *,
    expected_each: int = 1200,
) -> bool:
    """Require every scheduled rejection, response contract, and zero-query proof."""
    busy = [item for item in rejected if item["kind"] == "busy"]
    rate = [item for item in rejected if item["kind"] == "rate"]
    negative_metrics = [item for item in metrics if item["kind"].startswith("rejected-")]
    return (
        len(rejected) == expected_each * 2
        and len(busy) == expected_each
        and len(rate) == expected_each
        and all(item["status"] == 503 and item["detail"] == "INDICATOR_BUSY" for item in busy)
        and all(
            item["status"] == 429 and item["detail"] == "INDICATOR_RATE_LIMITED" for item in rate
        )
        and len(negative_metrics) == expected_each * 2
        and all(
            item["status"] == (503 if item["kind"] == "rejected-busy" else 429)
            and item["candle_queries"] == 0
            for item in negative_metrics
        )
    )


async def dirty_burst(migrator: AsyncEngine, source: AsyncEngine) -> list[RowMapping]:
    async with migrator.connect() as c:
        rows = (
            await c.execute(
                text(
                    "SELECT g.* FROM indicator_ready_heads h "
                    "JOIN indicator_generations g ON g.id=h.generation_id"
                )
            )
        ).mappings()
        generations = [
            generation
            for generation in rows
            if (generation["base"], Timeframe(generation["timeframe"])) in SERIES
        ]
    assert len(generations) == len(SERIES)
    async with market_data_session(source) as session:
        await session.execute("SELECT begin_indicator_source_write()")
        for g in generations:
            changed = await session.execute(
                """UPDATE market_candles SET
                close=CASE WHEN close=100.625 THEN 100.725 ELSE 100.625 END,
                fetch_started_at=clock_timestamp(),last_checked_at=clock_timestamp(),
                observed_at=clock_timestamp()
                WHERE source='primary_spot' AND base=:base AND quote='USDT'
                  AND timeframe=:tf AND open_at=:moment RETURNING 1""",
                {
                    "base": g["base"],
                    "tf": g["timeframe"],
                    "moment": advance(g["calculation_start"], Timeframe(g["timeframe"]), 10),
                },
            )
            assert changed.scalar_one() == 1
    return generations


async def loaded_probes(
    clients: list[httpx.AsyncClient], started: float, rejected: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    container = runtime_name("api")
    await docker(
        "exec",
        container,
        "python",
        "-c",
        "from pathlib import Path; "
        "[Path('/tmp/capacity-'+n).unlink(missing_ok=True) for n in ('entered','release')]",
    )

    async def barrier() -> None:
        async with asyncio.timeout(5):
            while (
                await docker(
                    "exec",
                    container,
                    "python",
                    "-c",
                    "from pathlib import Path; print(Path('/tmp/capacity-entered').exists())",
                )
            ) != "True":
                await asyncio.sleep(0.02)
        try:
            for _ in range(20):
                response = await clients[0].get(
                    "/market-data/indicators",
                    params={"base": "BTC", "quote": "USDT", "timeframe": "1m"},
                    headers={"x-capacity-kind": "rejected-busy"},
                )
                payload = response.json()
                rejected.append(
                    {
                        "kind": "busy",
                        "status": response.status_code,
                        "detail": payload.get("detail") if isinstance(payload, dict) else None,
                    }
                )
        finally:
            await docker(
                "exec",
                container,
                "python",
                "-c",
                "from pathlib import Path; Path('/tmp/capacity-release').touch()",
            )

    result = await probes(clients, started, barrier)
    for _ in range(20):
        response = await clients[0].get(
            "/market-data/indicators",
            params={"base": "BTC", "quote": "USDT", "timeframe": "1m"},
            headers={"x-capacity-kind": "rejected-rate"},
        )
        payload = response.json()
        rejected.append(
            {
                "kind": "rate",
                "status": response.status_code,
                "detail": payload.get("detail") if isinstance(payload, dict) else None,
            }
        )
    return result


def phase_plan(phase: str, loaded: bool, smoke: bool) -> tuple[str, str | None, int]:
    """Keep short diagnostic results outside the full-acceptance prerequisite chain."""
    assert phase in ("steady", "dirty")
    if smoke:
        assert (phase == "dirty") == loaded
        return "SMOKE-" + phase, "SMOKE-steady" if phase == "dirty" else None, 300
    if loaded:
        return "R2-C5-" + phase, "R2-C5-steady" if phase == "dirty" else "R2-C3", 3600
    return ("R2-C3", "R2-C2", 3600) if phase == "dirty" else ("R2-C2", None, 3600)


async def run(
    output: Path,
    c1: Path,
    phase: str = "steady",
    load_metrics: Path | None = None,
    requires: Path | None = None,
    metrics_directory: Path | None = None,
    smoke: bool = False,
    combined: bool = False,
) -> int:
    assert json.loads((c1 / "result.json").read_text(encoding="utf-8"))["R2-C1"] == "PASSED"
    gates: tuple[str, ...]
    required: tuple[str, ...]
    if smoke:
        if combined:
            raise ValueError("smoke evidence cannot emit combined acceptance gates")
        smoke_gate, smoke_required, duration = phase_plan(phase, load_metrics is not None, smoke)
        gates = (smoke_gate,)
        required = (smoke_required,) if smoke_required is not None else ()
    else:
        gates = capacity_gates(phase, under_load=load_metrics is not None, combined=combined)
        required = capacity_prerequisites(
            phase, under_load=load_metrics is not None, combined=combined
        )
        duration = 3600
    gate = "+".join(gates)
    sample_count, probe_count = duration // 10, duration // 60
    if required:
        assert requires is not None
        prerequisite = json.loads((requires / "result.json").read_text(encoding="utf-8"))
        assert all(prerequisite[name] == "PASSED" for name in required)
    for role in (DatabaseRole.API, DatabaseRole.MIGRATOR, DatabaseRole.MARKET_DATA):
        assert (
            f"@{CAPACITY_HOST}:{CAPACITY_POSTGRES_PORT}/tiewtrade" in os.environ[role.url_variable]
        )
    assert os.environ["TIEWTRADE_TEST_REDIS_URL"] == (
        f"redis://{CAPACITY_HOST}:{CAPACITY_REDIS_PORT}/0"
    )
    assert not (output / "result.json").exists()
    output.mkdir(parents=True, exist_ok=True)
    migrator = create_engine_for(DatabaseRole.MIGRATOR)
    api = create_engine_for(DatabaseRole.API)
    source = create_engine_for(DatabaseRole.MARKET_DATA)
    redis = Redis.from_url(os.environ["TIEWTRADE_TEST_REDIS_URL"])
    clients: list[httpx.AsyncClient] = []
    samples: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    references: dict[str, bool] = {}
    queued: set[str] = set()
    queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()
    consumer: asyncio.Task[None] | None = None
    pending: asyncio.Task[list[dict[str, Any]]] | None = None
    failure: str | None = None
    recovered_at: float | None = None
    rejected: list[dict[str, Any]] = []
    metric_offset = 0
    source_stop = asyncio.Event()
    producer: asyncio.Task[None] | None = None
    worker_offset = 0
    metric_file = load_metrics or (
        metrics_directory / "api-metrics.jsonl" if metrics_directory else None
    )
    worker_file = metric_file.parent / "worker-attempts.jsonl" if metric_file is not None else None

    def measured_resources() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        api_rows = (
            [json.loads(line) for line in metric_file.read_text().splitlines()[metric_offset:]]
            if metric_file is not None
            else []
        )
        worker_rows = (
            [json.loads(line) for line in worker_file.read_text().splitlines()[worker_offset:]]
            if worker_file is not None
            else []
        )
        return api_rows, worker_rows

    def resource_failure() -> str | None:
        api_rows, worker_rows = measured_resources()
        if any(
            m["max_lag_seconds"] > 0.1 or m["rss_delta_upper_bytes"] > 128 * 1024**2
            for m in api_rows
        ):
            return "API_RESOURCE_LIMIT"
        if any(
            m["seconds_including_acquire_cleanup"] > 120
            or m["rss_delta_upper_bytes"] > 128 * 1024**2
            for m in worker_rows
        ):
            return "WORKER_RESOURCE_LIMIT"
        return None

    try:
        async with migrator.connect() as c:
            ends = {
                r["base"] + "/" + r["timeframe"]: r["end_at"]
                for r in (
                    await c.execute(
                        text(
                            "SELECT base,timeframe,max(end_at) AS end_at FROM market_candles "
                            "GROUP BY base,timeframe"
                        )
                    )
                ).mappings()
            }
        await docker("start", runtime_name("api"))
        clients, users = await login()
        await append(source, ends)
        await docker("start", runtime_name("builder"))
        # C1 has passed already. Record any pre-phase refresh needed after the
        # independent C1 audit; this is not an excluded C1 prewarm.
        warm_started = monotonic()
        warm = []
        while True:
            await append(source, ends)
            ready = await observe(api, users[0])
            if smoke:
                ready = [s for s in ready if (s["base"], Timeframe(s["timeframe"])) in SERIES]
                assert len(ready) == len(SERIES)
            metadata = await snapshot(migrator)
            warm.append(
                {
                    "seconds": monotonic() - warm_started,
                    "series": ready,
                    "metadata": metadata,
                }
            )
            save(output / "before-phase.json", warm)
            if readiness_baseline_is_quiescent(ready, metadata):
                break
            if monotonic() - warm_started > 600:
                raise RuntimeError("CAPACITY_C2_BASELINE_NOT_READY")
            await asyncio.sleep(1)
        workload_ends = {
            base + "/" + timeframe.value: ends[base + "/" + timeframe.value]
            for base, timeframe in SERIES
        }
        producer = asyncio.create_task(maintain_source(source, workload_ends, source_stop, SERIES))
        # Warm process/DB paths with separate fixture actors so the measured
        # clients begin with untouched production admission quotas.
        prephase_probes = await probes(clients[2:], monotonic())
        await audit(api, users[2], prephase_probes)
        save(
            output / "before-phase-probes.json",
            [
                {key: value for key, value in probe.items() if key not in {"body"}}
                for probe in prephase_probes
            ],
        )
        if not all(probe["status"] == 200 and probe["correct"] for probe in prephase_probes):
            raise RuntimeError("CAPACITY_C2_PREPHASE_PROBE_NOT_READY")

        async def oracle() -> None:
            while (item := await queue.get()) is not None:
                key, probe = item
                try:
                    await audit(api, users[0], [probe])
                    references[key] = probe["correct"]
                    save(output / "oracle.json", references)
                finally:
                    queue.task_done()

        async def accept(batch: list[dict[str, Any]]) -> None:
            nonlocal failure
            for p in batch:
                body = p.pop("body")
                p["reference"] = None
                if p["status"] == 200:
                    key = signature(body)
                    p["reference"] = key
                    p["generation_id"] = body["generation_id"]
                    p["dataset_revision"] = body["dataset_revision"]
                    age = (
                        datetime.fromisoformat(body["refresh"]["observed_at"])
                        - datetime.fromisoformat(body["as_of"])
                    ).total_seconds()
                    p["envelope_ok"] = (
                        body["source"] == "primary_spot"
                        and body["base"] == p["base"]
                        and body["quote"] == "USDT"
                        and body["timeframe"] == p["timeframe"]
                        and 0 <= age <= 600
                        and body["generation_age_seconds"] == int(age)
                        and p["elapsed_seconds"] <= 30
                        and p["body_bytes"] <= 2 * 1024**2
                    )
                    if key not in queued:
                        queued.add(key)
                        await queue.put((key, p | {"body": body}))
                    if not p["envelope_ok"]:
                        failure = "API_ENVELOPE_OR_RESOURCE"
                else:
                    p["error"] = body.get("detail")
                    if (
                        phase != "dirty"
                        or p["status"] != 503
                        or body.get("detail") != "INDICATOR_DATA_NOT_READY"
                    ):
                        failure = "ACCEPTED_PROBE_NOT_200"
                responses.append(p)
            save(output / "probes.json", responses)

        started = monotonic()
        phase_utc = datetime.now(UTC)
        if metric_file is not None:
            metric_offset = len(metric_file.read_text(encoding="utf-8").splitlines())
            assert worker_file is not None
            worker_offset = len(worker_file.read_text(encoding="utf-8").splitlines())
        if phase == "dirty":
            old_generations = await dirty_burst(migrator, source)
            # Timer starts before commit, conservatively including the burst.
            async with indicator_read_session(api, users[0]) as session:
                await query_budget(session, monotonic() + 10)
                now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
                for old in old_generations:
                    assert not await proof_valid(session, old, now)
        consumer = asyncio.create_task(oracle())
        for tick in range(sample_count):
            await asyncio.sleep(max(0, started + tick * 10 - monotonic()))
            if producer.done():
                await producer
            ready = await observe(api, users[0])
            if smoke:
                ready = [s for s in ready if (s["base"], Timeframe(s["timeframe"])) in SERIES]
                assert len(ready) == len(SERIES)
            samples.append({"seconds": monotonic() - started, "series": ready})
            save(output / "observations.json", samples)
            workload_ready = workload_readiness(ready)
            all_valid = all(s["valid"] for s in workload_ready)
            if all_valid and recovered_at is None:
                recovered_at = monotonic() - started
            if not all_valid and (phase == "steady" or recovered_at is not None):
                failure = "VALID_FRESH_HEAD_GAP"
            if phase == "dirty" and recovered_at is None and monotonic() - started > 600:
                failure = "RECOVERY_DEADLINE"
            if pending is not None and pending.done():
                await accept(await pending)
                pending = None
            if consumer.done():
                await consumer  # Surface an oracle error; never silently lose coverage.
            if any(not valid for valid in references.values()):
                failure = "FULL_SCAN_PARITY"
            failure = failure or resource_failure()
            if failure is not None:
                break
            if tick % 6 == 0:
                if pending is not None:
                    failure = "PROBE_ROUND_OVERLAP"
                    break
                pending = asyncio.create_task(
                    loaded_probes(clients, started, rejected)
                    if load_metrics
                    else probes(clients, started)
                )
                progress(
                    gate,
                    round(monotonic() - started),
                    "seconds; valid",
                    sum(s["valid"] for s in workload_ready),
                    "/" + str(len(workload_ready)),
                )
            metadata = {"seconds": monotonic() - started, **await snapshot(migrator)}
            save(output / "latest-metadata.json", metadata)
            with (output / "metadata.jsonl").open("a", encoding="utf-8") as history:
                history.write(json.dumps(metadata, default=str) + "\n")
            if load_metrics:
                save(output / "rejected.json", rejected)
        if failure is None:
            await asyncio.sleep(max(0, started + duration - monotonic()))
        measured_seconds = monotonic() - started
        if pending is not None:
            await accept(await pending)
            pending = None
        await docker("stop", "--time", "130", runtime_name("builder"), timeout=140)
        await queue.put(None)
        await consumer
        consumer = None
        api_metrics, worker_metrics = measured_resources()
        save(output / "api-metrics.json", api_metrics)
        save(output / "worker-attempts.json", worker_metrics)
        failure = failure or resource_failure()
        save(output / "drained-metadata.json", await snapshot(migrator))
        summaries = []
        for base, tf in SERIES:
            series_samples = [
                s
                for sample in samples
                for s in sample["series"]
                if s["base"] == base and s["timeframe"] == tf.value
            ]
            series_probes = [
                p for p in responses if p["base"] == base and p["timeframe"] == tf.value
            ]
            correct = sum(
                p.get("envelope_ok", False) and references.get(p["reference"], False)
                for p in series_probes
            )
            first_correct = min(
                (
                    p["finished_seconds"]
                    for p in series_probes
                    if p.get("envelope_ok", False) and references.get(p["reference"], False)
                ),
                default=None,
            )
            valid_count = sum(s["valid"] for s in series_samples)
            post_recovery_ok = all(
                p.get("envelope_ok", False) and references.get(p["reference"], False)
                for p in series_probes
                if recovered_at is not None and p["started_seconds"] >= recovered_at
            )
            threshold_ok = (
                valid_count * 5 >= sample_count * 4
                and correct * 5 >= probe_count * 4
                and first_correct is not None
                and first_correct <= 600
                and post_recovery_ok
                if phase == "dirty"
                else valid_count == sample_count and correct == probe_count
            )
            summaries.append(
                {
                    "base": base,
                    "timeframe": tf.value,
                    "valid_samples": valid_count,
                    "first_correct_200_seconds": first_correct,
                    "scheduled_samples": sample_count,
                    "correct_probes": correct,
                    "scheduled_probes": probe_count,
                    "passed": len(series_samples) == sample_count
                    and len(series_probes) == probe_count
                    and threshold_ok,
                }
            )
        if load_metrics is not None:
            metrics = [
                json.loads(line)
                for line in load_metrics.read_text(encoding="utf-8").splitlines()[metric_offset:]
            ]
            save(output / "api-metrics.json", metrics)
            if not rejected_load_is_complete(rejected, metrics, expected_each=probe_count * 20):
                failure = failure or "REJECTED_LOAD_COVERAGE_STATUS_OR_QUERY"
            if any(
                m["max_lag_seconds"] > 0.1 or m["rss_delta_upper_bytes"] > 128 * 1024**2
                for m in metrics
            ):
                failure = failure or "API_RESOURCE_LIMIT"
        passed = (
            measured_seconds >= duration and failure is None and all(s["passed"] for s in summaries)
        )
        gate_result = "PASSED" if passed else "FAILED"
        save(
            output / "result.json",
            {
                **dict.fromkeys(gates, gate_result),
                "T0": phase_utc,
                "recovered_seconds": recovered_at,
                "measured_seconds": measured_seconds,
                "failure": failure,
                **capacity_scope_metadata(),
                "series": summaries,
                "smoke": smoke,
                "scheduled_seconds": duration,
                "readiness_scope": "BTCUSDT 8 timeframes" if smoke else "runtime catalog",
                "full_validation_credit": False if smoke else passed,
                "note": (
                    "Combined gates share one 60-minute run and always have the same result. "
                    if combined
                    else ""
                )
                + "Early failure is not a completed 60-minute acceptance run.",
            },
        )
        return 0 if passed else 1
    finally:
        source_stop.set()
        if producer is not None:
            producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)
        if pending is not None:
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
        if consumer is not None:
            consumer.cancel()
            await asyncio.gather(consumer, return_exceptions=True)
        for client in clients:
            await client.aclose()
        for kind in ("builder", "api"):
            await docker("stop", "--time", "130", runtime_name(kind), timeout=140)
        await redis.aclose()
        for engine in (migrator, api, source):
            await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--c1", type=Path, required=True)
    parser.add_argument("--phase", choices=("steady", "dirty"), default="steady")
    parser.add_argument("--load-metrics", type=Path)
    parser.add_argument("--requires", type=Path)
    parser.add_argument("--metrics", type=Path)
    parser.add_argument("--combined", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    raise SystemExit(
        asyncio.run(
            run(
                args.output,
                args.c1,
                args.phase,
                args.load_metrics,
                args.requires,
                args.metrics,
                args.smoke,
                args.combined,
            )
        )
    )
