"""Explicit G1/G3/G4 container faults on disposable test PG; not normal CI collection."""

import asyncio
import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_claims import slot
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.profile_container_recovery import docker
from tests.services.indicator_builder.test_attempt import seed
from tiewtrade.infra.db.errors import IndicatorBuildOwnershipError
from tiewtrade.infra.indicators.claims import PublicationResult
from tiewtrade.infra.indicators.pinned import pinned_indicator_writer
from tiewtrade.infra.indicators.recovery import (
    OwnerStopUnverifiedError,
    ReapResult,
    reap_verified_container,
)
from tiewtrade.infra.indicators.scan import scan_staging
from tiewtrade.infra.indicators.session import indicator_writer_session


@dataclass
class Probes:
    containers: list[str] = field(default_factory=list)
    owners: dict[str, UUID] = field(default_factory=dict)
    severed_sources: set[int] = field(default_factory=set)

    async def start(self, stage: str = "none", *, clocked: bool = False) -> str:
        owner = uuid4()
        root = Path(__file__).resolve().parents[4]
        ident = await docker(
            "run",
            "-d",
            "--network",
            "tiewtrade-f11-test-net",
            "--restart=no",
            "-v",
            f"{root}:/workspace:ro",
            "-e",
            "PYTHONPATH=/workspace/backend/src:/workspace/backend",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            "-e",
            f"PROBE_STAGE={stage}",
            "-e",
            f"PROBE_DB_CLOCK={int(clocked)}",
            "-e",
            f"TIEWTRADE_INDICATOR_OWNER={owner}",
            "-e",
            "TIEWTRADE_DATABASE_URL_INDICATOR_BUILDER="
            "postgresql+asyncpg://tiewtrade_indicator_builder:dev_indicator_builder@"
            "tiewtrade-f11-test-postgres:5432/tiewtrade",
            "tiewtrade-api:latest",
            "python",
            "-m",
            "tests.services.indicator_builder.global_slot_probe",
        )
        self.containers.append(ident)
        self.owners[ident] = owner
        return ident

    async def logs(self, ident: str) -> list[dict[str, Any]]:
        return [json.loads(line) for line in (await docker("logs", ident)).splitlines()]

    async def wait(self, ident: str, step: str) -> list[dict[str, Any]]:
        async with asyncio.timeout(12):
            while True:
                rows = await self.logs(ident)
                if any(row.get("step") == step for row in rows):
                    return rows
                state = json.loads(await docker("inspect", "--format", "{{json .State}}", ident))
                assert state["Running"], "probe exited before expected event"
                await asyncio.sleep(0.05)

    async def finish(self, ident: str) -> list[dict[str, Any]]:
        rows = await self.wait(ident, "result")
        async with asyncio.timeout(5):
            while True:
                state = json.loads(await docker("inspect", "--format", "{{json .State}}", ident))
                if not state["Running"]:
                    assert state["ExitCode"] == 0
                    return rows
                await asyncio.sleep(0.05)

    async def release(self, ident: str) -> None:
        await docker(
            "exec",
            ident,
            "python",
            "-c",
            "from pathlib import Path; Path('/tmp/release-probe').touch()",
        )


@pytest_asyncio.fixture
async def probes(prepared: None, builder_engine: AsyncEngine) -> AsyncIterator[Probes]:
    assert "127.0.0.1:55433/" in os.environ["TIEWTRADE_DATABASE_URL_MIGRATOR"]
    group = Probes()
    try:
        yield group
    finally:
        for ident in group.containers:
            # Immutable IDs created here only; paused containers are force removed too.
            await docker("rm", "-f", ident)
        # Only after every owned process has stopped: clean severed read-only sessions
        # that PostgreSQL may otherwise retain until TCP keepalive expiry.
        for pid in group.severed_sources:
            async with indicator_writer_session(builder_engine) as session:
                await session.execute("SELECT pg_terminate_backend(:pid)", {"pid": pid})


def outcome(rows: list[dict[str, Any]]) -> str:
    return str(next(row["status"] for row in rows if row.get("step") == "result"))


def no_build(rows: list[dict[str, Any]]) -> None:
    assert not any(
        row.get("step") in {"claim_committed", "source_open", "cpu_start", "hash_start"}
        for row in rows
    )


def ordered_shutdown(rows: list[dict[str, Any]]) -> None:
    source = next(row for row in rows if row.get("step") == "source_closed")
    writer = next(row for row in rows if row.get("step") == "writer_closed")
    assert 0 < source["last_cpu_end"] <= source["time_ns"] <= writer["time_ns"]


async def enable_other(admin: AsyncEngine, *, formula: bool = False) -> None:
    async with admin.begin() as c:
        await c.execute(
            text("""UPDATE indicator_build_jobs SET status='QUEUED',
          formula_version=CASE WHEN :different THEN 'probe-other-formula' ELSE formula_version END
          WHERE base='ETH' AND timeframe='4h'"""),
            {"different": formula},
        )


def evidence(name: str, payload: dict[str, Any]) -> None:
    target = os.environ.get("TIEWTRADE_GLOBAL_EVIDENCE_DIR")
    if target:
        Path(target, name + ".json").write_text(
            json.dumps(payload, default=str, indent=2), encoding="utf-8"
        )


async def derived_state(admin: AsyncEngine) -> dict[str, Any]:
    """Full derived rows, not just counts; retained privately for equality assertions."""
    async with admin.connect() as c:
        return {
            table: (
                await c.execute(
                    text(
                        f"SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text), "
                        f"'[]'::jsonb) FROM {table} t"
                    )
                )
            ).scalar_one()
            for table in ("indicator_generations", "indicator_checkpoints", "indicator_heads")
        }


@pytest.mark.parametrize(
    "fault", ["process_kill", "writer_backend", "network_partition", "db_restart"]
)
async def test_lost_session_requires_verified_stop_reap_and_rejects_all_old_writes(
    probes: Probes,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    fault: str,
) -> None:
    await seed(builder_engine, migrator_engine)
    first = await probes.start("cpu")
    started = await probes.wait(first, "barrier")
    source_pid = next(row["pid"] for row in started if row.get("step") == "source_open")
    held = await slot(migrator_engine)
    async with migrator_engine.connect() as c:
        checkpoint = (
            (
                await c.execute(
                    text(
                        "SELECT next_open_at,payload FROM indicator_checkpoints "
                        "WHERE generation_id=:id ORDER BY next_open_at LIMIT 1"
                    ),
                    {"id": held["generation_id"]},
                )
            )
            .mappings()
            .one()
        )
        old_job = dict(
            (
                await c.execute(
                    text("SELECT * FROM indicator_build_jobs WHERE id=:id"), {"id": held["job_id"]}
                )
            )
            .mappings()
            .one()
        )
    await enable_other(migrator_engine)
    with pytest.raises(OwnerStopUnverifiedError):
        await reap_verified_container(
            migrator_engine, first, probes.owners[first], held["slot_epoch"], held["fence"]
        )
    if fault == "db_restart":
        await builder_engine.dispose()
        await migrator_engine.dispose()
        # The named disposable DB is separate from app and capacity databases.
        await docker("restart", "tiewtrade-f11-test-postgres")
        async with asyncio.timeout(20):
            while True:
                try:
                    async with migrator_engine.connect() as c:
                        await c.execute(text("SELECT 1"))
                    break
                except Exception:
                    await asyncio.sleep(0.1)
    elif fault == "process_kill":
        await docker("kill", first)
        await docker("wait", first)
    else:
        if fault == "network_partition":
            probes.severed_sources.add(source_pid)
            await docker("network", "disconnect", "tiewtrade-f11-test-net", first)
            # A partition alone can leave the server session alive: no takeover.
            busy = await probes.finish(await probes.start())
            assert outcome(busy) == "LOCK_BUSY"
            no_build(busy)
        async with indicator_writer_session(builder_engine) as session:
            assert (
                await session.execute(
                    "SELECT pg_terminate_backend(:pid)", {"pid": held["owner_backend_pid"]}
                )
            ).scalar_one()
    blocked = await probes.finish(await probes.start())
    assert outcome(blocked) == "NO_JOB"
    no_build(blocked)
    assert (await slot(migrator_engine))["state"] == "RUNNING"
    if fault != "process_kill":
        with pytest.raises(OwnerStopUnverifiedError):
            await reap_verified_container(
                migrator_engine, first, probes.owners[first], held["slot_epoch"], held["fence"]
            )
        await docker("kill", first)
        await docker("wait", first)
    assert (
        await reap_verified_container(
            migrator_engine, first, probes.owners[first], held["slot_epoch"], held["fence"]
        )
        is ReapResult.REAPED
    )
    async with migrator_engine.connect() as c:
        current = dict(
            (
                await c.execute(
                    text("SELECT * FROM indicator_build_jobs WHERE id=:id"), {"id": held["job_id"]}
                )
            )
            .mappings()
            .one()
        )
    for key in (
        "attempts_used",
        "cycle_id",
        "last_served_round",
        "first_eligible_at",
        "availability_deadline",
    ):
        assert current[key] == old_job[key]
    params = {
        "epoch": held["slot_epoch"],
        "fence": held["fence"],
        "owner": held["owner_instance"],
        "job": held["job_id"],
        "generation": held["generation_id"],
        "token": held["claim_token"],
        "next": checkpoint["next_open_at"],
        "payload": json.dumps(checkpoint["payload"]),
    }
    identity = ":epoch,:fence,:owner,:job,:generation,:token"
    calls = [
        f"heartbeat_indicator_build_claim({identity})",
        f"append_indicator_checkpoint({identity},:next,CAST(:payload AS jsonb))",
        f"publish_indicator_ready({identity})",
        f"publish_indicator_numeric_failure({identity})",
        f"release_indicator_build_claim({identity},'TRANSIENT')",
    ]
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        successor = await writer.claim(uuid4())
        assert successor is not None and successor.fence > held["fence"]
        await scan_staging(builder_engine, writer, successor)
        live = await slot(migrator_engine)
        assert live["state"] == "RUNNING" and live["generation_id"] == successor.generation_id
        before = await derived_state(migrator_engine)
        async with migrator_engine.connect() as c:
            jobs: Any = (
                await c.execute(
                    text("SELECT jsonb_agg(to_jsonb(j) ORDER BY id) FROM indicator_build_jobs j")
                )
            ).scalar_one()
        # Use the successor's real physical owner session: denial cannot be explained
        # by an IDLE slot, missing advisory lock or a different caller backend alone.
        for call in calls:
            with pytest.raises(IndicatorBuildOwnershipError):
                async with writer.transaction() as session:
                    await session.execute("SELECT " + call, params)
            assert await slot(migrator_engine) == live
            assert await derived_state(migrator_engine) == before
            async with migrator_engine.connect() as c:
                assert (
                    await c.execute(
                        text(
                            "SELECT jsonb_agg(to_jsonb(j) ORDER BY id) FROM indicator_build_jobs j"
                        )
                    )
                ).scalar_one() == jobs
        # Positive controls on the exact same owner/session after every rejection.
        await writer.heartbeat()
        assert await writer.publish_ready(successor) is PublicationResult.READY
    assert (await slot(migrator_engine))["state"] == "IDLE"
    evidence(
        "g4-" + fault,
        {
            "blocked": blocked,
            "successor": {
                "status": "READY",
                "fence": successor.fence,
                "stale_probe_slot_state": live["state"],
                "same_owner_session": True,
                "state_unchanged": True,
            },
            "verified_stop_reap": True,
            "stale_operations_rejected": len(calls),
            "budget_preserved": True,
        },
    )


@pytest.mark.parametrize(
    "stage", ["before_scan", "cpu", "after_staging", "before_publish", "source_cleanup"]
)
@pytest.mark.parametrize("target", ["same", "other_series", "other_formula"])
async def test_global_slot_excludes_second_process_at_every_build_barrier(
    probes: Probes,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    stage: str,
    target: str,
) -> None:
    await seed(builder_engine, migrator_engine)
    first = await probes.start(stage)
    await probes.wait(first, "barrier")
    held = await slot(migrator_engine)
    if target != "same":
        await enable_other(migrator_engine, formula=target == "other_formula")
    second = await probes.start()
    blocked = await probes.finish(second)
    assert outcome(blocked) == "LOCK_BUSY"
    no_build(blocked)
    assert await slot(migrator_engine) == held
    async with migrator_engine.connect() as c:
        assert (
            await c.execute(
                text("SELECT count(*) FROM indicator_build_jobs WHERE status='RUNNING'")
            )
        ).scalar_one() == 1
        assert (
            await c.execute(
                text(
                    "SELECT count(*) FROM pg_locks WHERE pid=:pid AND locktype='advisory' "
                    "AND classid=711 AND objid=1 AND granted"
                ),
                {"pid": held["owner_backend_pid"]},
            )
        ).scalar_one() == 1
    # Claim has committed. No row guard may be retained over scan/CPU/staging.
    async with migrator_engine.begin() as c:
        for table in (
            "indicator_source_guard",
            "indicator_rollout_control",
            "indicator_build_slot",
            "indicator_build_jobs",
        ):
            await c.execute(text(f"SELECT 1 FROM {table} FOR UPDATE NOWAIT"))
    await probes.release(first)
    finished = await probes.finish(first)
    assert outcome(finished) == "READY"
    ordered_shutdown(finished)
    steps = [row.get("step") for row in finished]
    assert steps.index("source_closed") < steps.index("actual_unlock_sql")
    assert steps.index("actual_unlock_sql") < steps.index("writer_closed")
    if target == "other_formula":
        # The alternate metadata key tests lock scope, not support for a new formula.
        async with migrator_engine.begin() as c:
            await c.execute(
                text(
                    "UPDATE indicator_build_jobs SET formula_version=(SELECT formula_version "
                    "FROM indicator_build_jobs WHERE base='BTC' AND timeframe='4h') "
                    "WHERE base='ETH' AND timeframe='4h'"
                )
            )
    await enable_other(migrator_engine)
    resumed = await probes.start()
    fresh = await probes.finish(resumed)
    assert outcome(fresh) == "READY"
    ordered_shutdown(fresh)
    assert next(r["time_ns"] for r in fresh if r.get("step") == "cpu_start") > next(
        r["time_ns"] for r in finished if r.get("step") == "writer_closed"
    )
    evidence(f"g1-{target}-{stage}", {"holder": finished, "blocked": blocked, "successor": fresh})


async def test_paused_cpu_holder_exceeds_real_lease_without_takeover(
    probes: Probes,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    await seed(builder_engine, migrator_engine)
    first = await probes.start("cpu")
    paused_trace = await probes.wait(first, "barrier")
    held = await slot(migrator_engine)
    before = await derived_state(migrator_engine)
    await enable_other(migrator_engine)
    await docker("pause", first)
    began = monotonic()
    await asyncio.sleep(151)
    elapsed = monotonic() - began
    async with migrator_engine.connect() as c:
        expired: bool = (
            await c.execute(
                text(
                    "SELECT clock_timestamp()>lease_until AND clock_timestamp()>attempt_deadline "
                    "FROM indicator_build_slot"
                )
            )
        ).scalar_one()
        assert expired and elapsed > 150
        assert (
            await c.execute(
                text("SELECT count(*) FROM pg_stat_activity WHERE pid=:pid"),
                {"pid": held["owner_backend_pid"]},
            )
        ).scalar_one() == 1
    second = await probes.start()
    blocked = await probes.finish(second)
    assert outcome(blocked) == "LOCK_BUSY"
    no_build(blocked)
    with pytest.raises(OwnerStopUnverifiedError):
        await reap_verified_container(
            migrator_engine, first, probes.owners[first], held["slot_epoch"], held["fence"]
        )
    assert await slot(migrator_engine) == held
    await docker("unpause", first)
    await probes.release(first)
    finished = await probes.finish(first)
    assert outcome(finished) in {"RELEASED", "ORPHANED"}
    resumed_trace = finished[len(paused_trace) :]
    assert not any(
        row.get("step")
        in {
            "checkpoint_attempt",
            "checkpoint_committed",
            "ready_attempt",
            "published",
            "numeric_attempt",
            "numeric_published",
        }
        for row in resumed_trace
    )
    after = await derived_state(migrator_engine)
    # Safe terminal release may expire STAGING metadata, but cannot add/change a
    # checkpoint or publish READY/FAILED_NUMERIC. All other generation fields stay fixed.
    assert before["indicator_checkpoints"] == after["indicator_checkpoints"]
    assert before["indicator_heads"] == after["indicator_heads"]
    assert len(before["indicator_generations"]) == len(after["indicator_generations"]) == 1
    old_generation = before["indicator_generations"][0]
    new_generation = after["indicator_generations"][0]
    assert new_generation["status"] in {"STAGING", "EXPIRED"}
    assert {k: v for k, v in old_generation.items() if k != "status"} == {
        k: v for k, v in new_generation.items() if k != "status"
    }
    ordered_shutdown(finished)
    reaped = await reap_verified_container(
        migrator_engine, first, probes.owners[first], held["slot_epoch"], held["fence"]
    )
    assert reaped in {ReapResult.STALE, ReapResult.REAPED}
    fresh = await probes.finish(await probes.start())
    assert outcome(fresh) == "READY"
    assert (await slot(migrator_engine))["fence"] > held["fence"]
    assert next(r["time_ns"] for r in fresh if r.get("step") == "cpu_start") > next(
        r["time_ns"] for r in finished if r.get("step") == "writer_closed"
    )
    evidence(
        "g3-real-pause",
        {
            "elapsed_seconds": elapsed,
            "blocked": blocked,
            "resumed_owner": finished,
            "verified_reap": reaped,
            "successor": fresh,
            "resumed_mutation_attempts": 0,
            "checkpoint_and_head_rows_unchanged": True,
            "generation_status_after_resume": new_generation["status"],
        },
    )
