"""Dedicated real-runtime R2-S5 fairness validation for the F-38 workload.

This is an explicit release-checkpoint command, not a normal pytest.  It reuses
the approved fixture builder but requires a fresh, migrated isolated PostgreSQL
database, an empty unauthenticated Redis database, and the already-created Docker
network named by ``TIEWTRADE_CAPACITY_PREFIX``.  It does not reuse the C1/C2/C3
database.  BTC/1m receives continuous historical writes while all other runtime
series receive append-only source maintenance.  Two real builder processes
contend through the production global slot and scheduler.
"""

import argparse
import asyncio
import json
import math
import os
from collections.abc import Sequence
from contextlib import suppress
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from time import monotonic
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text

from tests.services.indicator_builder.profile_capacity import (
    CAPACITY_HOST,
    CAPACITY_POSTGRES_PORT,
    CAPACITY_PREFIX,
    CAPACITY_REDIS_PORT,
    READINESS_SERIES,
    SERIES,
    audit,
    authenticate,
    capacity_scope_metadata,
    create_runtime,
    docker,
    maintain_source,
    observe,
    probes,
    runtime_name,
    save,
    seed,
    snapshot,
)
from tests.services.indicator_builder.profile_capacity_steady import workload_readiness
from tiewtrade.core.market_data import (
    Timeframe,
    advance,
    align_ceil,
    retention_cutoff,
)
from tiewtrade.infra.db.engine import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import market_data_session

EXPECTED_DATABASE_REVISION = "0042"
S5_SERIES = {(base, timeframe.value) for base, timeframe in SERIES}
CHURN_SERIES = ("BTC", Timeframe.M1)
S5_DEADLINE_SECONDS = 600
HISTORICAL_CHURN_MAX_GAP_SECONDS = 10
WORKER_SECONDS = 120
RSS_LIMIT = 128 * 1024**2
RUNTIME_ROLES = ("api", "builder", "builder-s5-peer")


def _moment(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value) if isinstance(value, str) else None


def _job_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("base")), str(row.get("timeframe"))


def _bounded_number(value: object, upper: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0 <= value <= upper
    )


def _series_rows(rows: Sequence[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {_job_key(row): row for row in rows if _job_key(row) in S5_SERIES}


def s5_environment_valid(environment: dict[str, Any], c1_environment: dict[str, Any]) -> bool:
    """Validate the retained fresh-runtime provenance required by strict S5."""
    containers = environment.get("runtime_containers_created")
    derived = environment.get("derived_counts_before_runtime")
    return (
        isinstance(environment.get("image"), str)
        and environment["image"] != ""
        and environment["image"] == c1_environment.get("image")
        and isinstance(containers, dict)
        and set(containers) == set(RUNTIME_ROLES)
        and all(isinstance(containers[role], str) and containers[role] for role in RUNTIME_ROLES)
        and len(set(containers.values())) == len(RUNTIME_ROLES)
        and environment.get("redis_dbsize_before_runtime") == 0
        and environment.get("redis_url_mode") == "plain-unauthenticated"
        and environment.get("database_revision") == EXPECTED_DATABASE_REVISION
        and environment.get("source_fixture")
        == "fresh 16-series source; empty derived/jobs before runtime start"
        and environment.get("source_runtime_series") == len(READINESS_SERIES)
        and derived
        == {
            "indicator_build_jobs": 0,
            "indicator_generations": 0,
            "indicator_checkpoints": 0,
        }
        and environment.get("historical_series") == f"{CHURN_SERIES[0]}/{CHURN_SERIES[1].value}"
        and environment.get("append_only_runtime_series") == len(READINESS_SERIES) - 1
        and all(
            environment.get(name) == expected
            for name, expected in capacity_scope_metadata().items()
        )
    )


def evaluate_s5(
    trace: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    probe_rounds: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    historical_writes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Fail closed on the approved S5 episode and return machine evidence."""
    failures: list[str] = []
    if not trace or not observations or not probe_rounds:
        failures.append("MISSING_TRACE_OBSERVATION_OR_PROBE")
    if any(
        len(sample.get("series", [])) != len(S5_SERIES)
        or {_job_key(row) for row in sample.get("series", [])} != S5_SERIES
        for sample in observations
    ):
        failures.append("INCOMPLETE_OBSERVATION_SCOPE")
    if any(
        len(sample.get("series", [])) != len(S5_SERIES)
        or {_job_key(row) for row in sample.get("series", [])} != S5_SERIES
        for sample in probe_rounds
    ):
        failures.append("INCOMPLETE_PROBE_SCOPE")
    committed_writes = [row for row in historical_writes if row.get("committed_at") is not None]
    if len(committed_writes) < 2:
        failures.append("HISTORICAL_WRITES_NOT_CONTINUOUS")

    episode_history: dict[
        tuple[str, str], list[tuple[datetime, tuple[datetime, datetime], bool]]
    ] = {key: [] for key in S5_SERIES}
    for sample in trace:
        recorded = _moment(sample.get("recorded_at"))
        if recorded is None:
            continue
        jobs = _series_rows(sample.get("jobs", []))
        for key in S5_SERIES:
            job = jobs.get(key)
            if job is None:
                continue
            first = _moment(job.get("first_eligible_at"))
            deadline = _moment(job.get("availability_deadline"))
            if first is None or deadline is None:
                continue
            episode_history[key].append(
                (recorded, (first, deadline), job.get("deadline_missed_at") is not None)
            )

    first_valid: dict[tuple[str, str], datetime] = {}
    healthy_observer_preserved = dict.fromkeys(S5_SERIES, True)
    sample_counts = {key: {"valid": 0, "unavailable": 0} for key in S5_SERIES}
    for sample in observations:
        recorded = _moment(sample.get("recorded_at"))
        if recorded is None:
            continue
        for row in sample.get("series", []):
            key = _job_key(row)
            if key not in S5_SERIES:
                continue
            if row.get("valid") is True:
                sample_counts[key]["valid"] += 1
                first_valid.setdefault(key, recorded)
            else:
                sample_counts[key]["unavailable"] += 1
                if key in first_valid:
                    healthy_observer_preserved[key] = False

    episodes: dict[tuple[str, str], tuple[datetime, datetime]] = {}
    deadline_preserved = dict.fromkeys(S5_SERIES, True)
    deadline_missed = dict.fromkeys(S5_SERIES, False)
    for key, history in episode_history.items():
        if not history:
            continue
        episodes[key] = history[0][1]
        recovery = first_valid.get(key)
        initial_episode = [row for row in history if recovery is None or row[0] <= recovery]
        deadline_preserved[key] = all(row[1] == episodes[key] for row in initial_episode)
        deadline_missed[key] = any(row[2] for row in initial_episode)

    first_200: dict[tuple[str, str], datetime] = {}
    healthy_get_preserved = dict.fromkeys(S5_SERIES, True)
    for probe_round in probe_rounds:
        recorded = _moment(probe_round.get("recorded_at"))
        if recorded is None:
            continue
        for row in probe_round.get("series", []):
            key = _job_key(row)
            if key not in S5_SERIES:
                continue
            correct = row.get("status") == 200 and row.get("correct") is True
            if correct:
                first_200.setdefault(key, recorded)
            elif key in first_200:
                healthy_get_preserved[key] = False

    attempt_series = {_job_key(row) for row in attempts}
    ready_series = {_job_key(row) for row in attempts if row.get("status") == "READY"}
    attempt_statuses_ok = all(
        (
            row.get("status") in {"READY", "RELEASED"}
            or (
                _job_key(row) == (CHURN_SERIES[0], CHURN_SERIES[1].value)
                and row.get("status") == "SUPERSEDED"
            )
        )
        and _bounded_number(row.get("seconds_including_acquire_cleanup"), WORKER_SECONDS)
        and _bounded_number(row.get("rss_delta_upper_bytes"), RSS_LIMIT)
        for row in attempts
    )

    series: list[dict[str, Any]] = []
    for key in sorted(S5_SERIES):
        first, deadline = episodes.get(key, (None, None))
        valid = first_valid.get(key)
        get_200 = first_200.get(key)
        valid_seconds = (valid - first).total_seconds() if first and valid else None
        get_200_seconds = (get_200 - first).total_seconds() if first and get_200 else None
        is_churn = key == (CHURN_SERIES[0], CHURN_SERIES[1].value)
        episode_ok = (
            first is not None
            and deadline is not None
            and (deadline - first).total_seconds() == S5_DEADLINE_SECONDS
            and deadline_preserved[key]
            and healthy_observer_preserved[key]
            and healthy_get_preserved[key]
            and key in attempt_series
        )
        recovered = (
            first is not None
            and valid is not None
            and get_200 is not None
            and _bounded_number(valid_seconds, S5_DEADLINE_SECONDS)
            and _bounded_number(get_200_seconds, S5_DEADLINE_SECONDS)
            and not deadline_missed[key]
            and key in ready_series
        )
        passed = (
            episode_ok and recovered and (not is_churn or sample_counts[key]["unavailable"] > 0)
        )
        series.append(
            {
                "base": key[0],
                "timeframe": key[1],
                "role": "continuous-historical" if is_churn else "append-only",
                "first_eligible_at": first,
                "availability_deadline": deadline,
                "first_valid_at": valid,
                "first_get_200_at": get_200,
                "deadline_preserved": deadline_preserved[key],
                "deadline_missed": deadline_missed[key],
                "valid_samples": sample_counts[key]["valid"],
                "unavailable_samples": sample_counts[key]["unavailable"],
                "healthy_observer_preserved": healthy_observer_preserved[key],
                "healthy_get_preserved": healthy_get_preserved[key],
                "passed": passed,
            }
        )
    if not all(row["passed"] for row in series):
        failures.append("SERIES_STARVED_OR_EPISODE_RESET")
    churn_summary = next(
        row
        for row in series
        if (row["base"], row["timeframe"]) == (CHURN_SERIES[0], CHURN_SERIES[1].value)
    )
    if churn_summary["unavailable_samples"] == 0:
        failures.append("CHURN_UNAVAILABLE_NOT_OBSERVED")
    if not attempts or not attempt_statuses_ok:
        failures.append("ATTEMPT_STATUS_OR_RESOURCE_LIMIT")
    committed_moments = sorted(
        moment
        for row in committed_writes
        if (moment := _moment(row.get("committed_at"))) is not None
    )
    stop_moments = [
        moment
        for row in historical_writes
        if (moment := _moment(row.get("churn_stopped_at"))) is not None
    ]
    churn_finished = stop_moments[0] if len(stop_moments) == 1 else None
    other_recovered = [
        row["first_get_200_at"]
        for row in series
        if (row["base"], row["timeframe"]) != (CHURN_SERIES[0], CHURN_SERIES[1].value)
    ]
    first_eligibility = min((episode[0] for episode in episodes.values()), default=None)
    churn_gaps = [
        (later - earlier).total_seconds() for earlier, later in pairwise(committed_moments)
    ]
    if (
        churn_finished is None
        or first_eligibility is None
        or not committed_moments
        or committed_moments[0] > first_eligibility
        or committed_moments[-1] > churn_finished
        or (churn_finished - committed_moments[-1]).total_seconds()
        > HISTORICAL_CHURN_MAX_GAP_SECONDS
        or any(gap < 0 or gap > HISTORICAL_CHURN_MAX_GAP_SECONDS for gap in churn_gaps)
        or any(value is None for value in other_recovered)
        or churn_finished < max(other_recovered)
    ):
        failures.append("CHURN_DID_NOT_COVER_OTHER_SERIES_RECOVERY")

    return {
        "R2-S5": "PASSED" if not failures else "FAILED",
        **capacity_scope_metadata(),
        "historical_series": f"{CHURN_SERIES[0]}/{CHURN_SERIES[1].value}",
        "historical_writes": len(committed_writes),
        "attempts": len(attempts),
        "owners": len({row.get("owner") for row in attempts}),
        "series": series,
        "failures": failures,
    }


async def historical_churn(
    source: Any,
    moment: datetime,
    stop: asyncio.Event,
    evidence: list[dict[str, Any]],
) -> None:
    while not stop.is_set():
        async with market_data_session(source) as session:
            await session.execute("SELECT begin_indicator_source_write()")
            committed = (
                await session.execute(
                    """UPDATE market_candles SET
                    close=CASE WHEN close=100.625 THEN 100.725 ELSE 100.625 END,
                    fetch_started_at=clock_timestamp(),last_checked_at=clock_timestamp(),
                    observed_at=clock_timestamp()
                    WHERE source='primary_spot' AND base='BTC' AND quote='USDT'
                      AND timeframe='1m' AND open_at=:moment
                    RETURNING clock_timestamp() AS committed_at""",
                    {"moment": moment},
                )
            ).scalar_one()
        evidence.append({"committed_at": committed})
        with suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), 5)


def _require_companion_phase(path: Path, *gates: str) -> None:
    result = json.loads((path / "result.json").read_text(encoding="utf-8-sig"))
    if not all(result.get(gate) == "PASSED" for gate in gates):
        raise RuntimeError("R2_S5_REQUIRES_PASSED_COMBINED_PHASES")


async def run(
    output: Path,
    c1: Path,
    steady: Path,
    dirty: Path,
    image: str,
    metrics: Path,
) -> int:
    """Run the dedicated S5 episode; this function is never called by pytest."""
    _require_companion_phase(steady, "R2-C2", "R2-C5-steady")
    _require_companion_phase(dirty, "R2-C3", "R2-C5-dirty")
    c1_result = json.loads((c1 / "result.json").read_text(encoding="utf-8-sig"))
    if c1_result.get("R2-C1") != "PASSED":
        raise RuntimeError("R2_S5_REQUIRES_PASSED_C1")
    for role in (DatabaseRole.MIGRATOR, DatabaseRole.API, DatabaseRole.MARKET_DATA):
        if (
            f"@{CAPACITY_HOST}:{CAPACITY_POSTGRES_PORT}/tiewtrade"
            not in os.environ[role.url_variable]
        ):
            raise RuntimeError("R2_S5_POSTGRES_ENDPOINT_MISMATCH")
    if os.environ["TIEWTRADE_TEST_REDIS_URL"] != (
        f"redis://{CAPACITY_HOST}:{CAPACITY_REDIS_PORT}/0"
    ):
        raise RuntimeError("R2_S5_REDIS_ENDPOINT_MISMATCH")
    image_id = await docker("image", "inspect", "--format", "{{.Id}}", image)
    c1_environment = json.loads((c1 / "environment.json").read_text(encoding="utf-8-sig"))
    if c1_environment.get("image") != image_id:
        raise RuntimeError("R2_S5_CANDIDATE_IMAGE_MISMATCH")
    for kind in ("api", "builder", "builder-s5-peer"):
        check = await asyncio.create_subprocess_exec(
            "docker",
            "inspect",
            runtime_name(kind),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        if await check.wait() == 0:
            raise RuntimeError("R2_S5_RUNTIME_NAME_ALREADY_EXISTS")
    output.mkdir(parents=True, exist_ok=False)

    migrator = create_engine_for(DatabaseRole.MIGRATOR)
    api = create_engine_for(DatabaseRole.API)
    source = create_engine_for(DatabaseRole.MARKET_DATA)
    redis = Redis.from_url(os.environ["TIEWTRADE_TEST_REDIS_URL"])
    clients: list[Any] = []
    source_stop = asyncio.Event()
    churn_stop = asyncio.Event()
    producer: asyncio.Task[None] | None = None
    churn: asyncio.Task[None] | None = None
    created: dict[str, str] = {}
    observations: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    probe_rounds: list[dict[str, Any]] = []
    audit_timeout_retries = 0
    writes: list[dict[str, Any]] = []
    metrics.mkdir(parents=True, exist_ok=True)
    metric_file = metrics / "worker-attempts.jsonl"
    worker_offset = len(metric_file.read_text().splitlines()) if metric_file.exists() else 0
    try:
        redis_dbsize_before_runtime = await redis.dbsize()
        if redis_dbsize_before_runtime != 0:
            raise RuntimeError("R2_S5_REDIS_NOT_EMPTY")
        ends = await seed(migrator)
        async with migrator.connect() as connection:
            database_revision: str = (
                await connection.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one()
            source_runtime_series: int = (
                await connection.execute(
                    text(
                        """SELECT count(*) FROM (
                        SELECT DISTINCT base,timeframe FROM market_candles
                        WHERE source='primary_spot' AND quote='USDT'
                        ) AS runtime_series"""
                    )
                )
            ).scalar_one()
            database_now: datetime = (
                await connection.execute(text("SELECT clock_timestamp()"))
            ).scalar_one()
            derived_counts: dict[str, int] = {
                table: (
                    await connection.execute(text(f"SELECT count(*) FROM {table}"))
                ).scalar_one()
                for table in (
                    "indicator_build_jobs",
                    "indicator_generations",
                    "indicator_checkpoints",
                )
            }
        if any(derived_counts.values()):
            raise RuntimeError("R2_S5_DERIVED_FIXTURE_NOT_EMPTY")
        if source_runtime_series != len(READINESS_SERIES):
            raise RuntimeError("R2_S5_SOURCE_RUNTIME_SERIES_MISMATCH")
        churn_moment = advance(
            align_ceil(retention_cutoff(database_now, CHURN_SERIES[1]), CHURN_SERIES[1]),
            CHURN_SERIES[1],
            10,
        )
        api_container = await create_runtime(image_id, "api", metrics)
        created["api"] = api_container
        builder = await create_runtime(image_id, "builder", metrics)
        created["builder"] = builder
        peer = await create_runtime(image_id, "builder-s5-peer", metrics)
        created["builder-s5-peer"] = peer
        if cpuset := os.environ.get("TIEWTRADE_CAPACITY_BUILDER_CPUSET"):
            await docker("update", "--cpuset-cpus", cpuset, peer)
        environment = {
            "image": image_id,
            "capacity_prefix": CAPACITY_PREFIX,
            "postgres_endpoint": f"{CAPACITY_HOST}:{CAPACITY_POSTGRES_PORT}/tiewtrade",
            "redis_endpoint": f"{CAPACITY_HOST}:{CAPACITY_REDIS_PORT}/0",
            "redis_dbsize_before_runtime": redis_dbsize_before_runtime,
            "redis_url_mode": "plain-unauthenticated",
            "database_revision": database_revision,
            "api_cpuset": os.environ.get("TIEWTRADE_CAPACITY_API_CPUSET"),
            "builder_cpuset": os.environ.get("TIEWTRADE_CAPACITY_BUILDER_CPUSET"),
            "runtime_containers_created": created,
            "source_fixture": "fresh 16-series source; empty derived/jobs before runtime start",
            "source_runtime_series": source_runtime_series,
            "derived_counts_before_runtime": derived_counts,
            "historical_series": f"{CHURN_SERIES[0]}/{CHURN_SERIES[1].value}",
            "append_only_runtime_series": len(READINESS_SERIES) - 1,
            **capacity_scope_metadata(),
        }
        if not s5_environment_valid(environment, c1_environment):
            raise RuntimeError("R2_S5_ENVIRONMENT_EVIDENCE_INVALID")
        save(output / "environment.json", environment)
        await docker("start", api_container)
        clients, users = await authenticate(api_container)
        append_only = [series for series in READINESS_SERIES if series != CHURN_SERIES]
        producer = asyncio.create_task(maintain_source(source, ends, source_stop, append_only))
        churn = asyncio.create_task(historical_churn(source, churn_moment, churn_stop, writes))
        while len(writes) < 2:
            if churn.done():
                await churn
            await asyncio.sleep(0.1)
        await docker("start", builder, peer)

        started = monotonic()
        while monotonic() - started <= S5_DEADLINE_SECONDS:
            if producer.done():
                await producer
            if churn.done():
                await churn
            now = datetime.now(UTC)
            ready = workload_readiness(await observe(api, users[0]))
            observations.append({"recorded_at": now, "series": ready})
            trace.append({"recorded_at": now, **await snapshot(migrator)})
            other_ready = all(
                row["valid"]
                for row in ready
                if (row["base"], row["timeframe"]) != (CHURN_SERIES[0], CHURN_SERIES[1].value)
            )
            if other_ready:
                seconds, _ = await redis.time()
                if seconds % 60 <= 1 and not churn_stop.is_set():
                    batch = await probes(clients, started)
                    audit_timeout_retries += await audit(api, users[0], batch)
                    probe_rounds.append(
                        {
                            "recorded_at": datetime.now(UTC),
                            "series": [
                                {key: value for key, value in row.items() if key != "body"}
                                for row in batch
                            ],
                        }
                    )
                    other_200 = all(
                        row["status"] == 200 and row.get("correct") is True
                        for row in batch
                        if (row["base"], row["timeframe"])
                        != (CHURN_SERIES[0], CHURN_SERIES[1].value)
                    )
                    if other_200:
                        writes.append({"churn_stopped_at": datetime.now(UTC)})
                        churn_stop.set()
                elif seconds % 60 <= 1 and all(row["valid"] for row in ready):
                    batch = await probes(clients, started)
                    audit_timeout_retries += await audit(api, users[0], batch)
                    probe_rounds.append(
                        {
                            "recorded_at": datetime.now(UTC),
                            "series": [
                                {key: value for key, value in row.items() if key != "body"}
                                for row in batch
                            ],
                        }
                    )
                    if all(row["status"] == 200 and row.get("correct") is True for row in batch):
                        break
            await asyncio.sleep(1)
        churn_stop.set()
        if churn is not None:
            await churn
            churn = None
        attempts = (
            [json.loads(line) for line in metric_file.read_text().splitlines()[worker_offset:]]
            if metric_file.exists()
            else []
        )
        result = evaluate_s5(trace, observations, probe_rounds, attempts, writes)
        for name, value in (
            ("trace.json", trace),
            ("observations.json", observations),
            ("probes.json", probe_rounds),
            ("worker-attempts.json", attempts),
            ("historical-writes.json", writes),
            ("audit.json", {"database_timeout_retries": audit_timeout_retries}),
            ("result.json", result),
        ):
            save(output / name, value)
        return 0 if result["R2-S5"] == "PASSED" else 1
    except BaseException as error:
        for name, value in (
            ("trace.json", trace),
            ("observations.json", observations),
            ("probes.json", probe_rounds),
            ("historical-writes.json", writes),
            (
                "failure.json",
                {
                    "R2-S5": "FAILED",
                    "failure": type(error).__name__,
                    **capacity_scope_metadata(),
                },
            ),
        ):
            save(output / name, value)
        raise
    finally:
        source_stop.set()
        churn_stop.set()
        for task in (producer, churn):
            if task is not None:
                task.cancel()
        await asyncio.gather(
            *(task for task in (producer, churn) if task is not None),
            return_exceptions=True,
        )
        for client in clients:
            await client.aclose()
        if created:
            for container in created.values():
                with suppress(RuntimeError):
                    await docker("stop", "--time", "130", container, timeout=140)
        await redis.aclose()
        for engine in (migrator, api, source):
            await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--c1", type=Path, required=True)
    parser.add_argument("--steady", type=Path, required=True)
    parser.add_argument("--dirty", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    arguments = parser.parse_args()
    raise SystemExit(
        asyncio.run(
            run(
                arguments.output,
                arguments.c1,
                arguments.steady,
                arguments.dirty,
                arguments.image,
                arguments.metrics,
            )
        )
    )
