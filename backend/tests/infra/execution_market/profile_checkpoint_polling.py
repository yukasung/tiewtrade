"""NC-SET4-07: fixed writer, bounded concurrency and read-only polling probe."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
from contextlib import suppress
from pathlib import Path
from time import monotonic, time
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.pool import QueuePool

from tests.infra.execution_market import profile_checkpoint_isolation as iso
from tests.infra.execution_market import profile_runtime_observation as runtime
from tests.infra.execution_market.profile_checkpoint_fixture import checkpoint_snapshot
from tests.infra.execution_market.profile_workload import (
    RESULT_POLL_SECONDS,
    percentile,
    progress,
    save,
)
from tests.infra.risk_limits.profile_pool_timing import TransactionTrace, operation_scope
from tests.infra.risk_limits.profile_resources import (
    PoolEvidence,
    connection_budget,
    pool_configuration,
)
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.paper_orders.dispatch import get_order_command

MODULE = "tests.infra.execution_market.profile_checkpoint_polling"
PACE_SECONDS = 0.1


def conditions(profile: str = "concurrency-v1") -> list[tuple[int, int]]:
    if profile == runtime.PROFILE:
        return [(1, readers) for readers in (0, 100, 100, 0, 100, 0, 0, 100)]
    if profile != "concurrency-v1":
        raise ValueError("unknown checkpoint profile")
    forward = [(1, 0), (1, 100), (4, 0), (4, 100)]
    return forward + forward[::-1]


def assignments(writers: int) -> list[tuple[int, str, float]]:
    if writers not in (1, 4):
        raise ValueError("one or four writers required")
    return [
        ((i // 2) % writers, "command" if i % 2 == 0 else "status", i * RESULT_POLL_SECONDS / 100)
        for i in range(100)
    ]


def fixtures(directory: Path) -> list[dict[str, Any]]:
    documents = [json.loads((directory / f"fixture-{i}.json").read_text()) for i in range(4)]
    if len({d["owner"] for d in documents}) != 4 or len({d["wallet"] for d in documents}) != 4:
        raise ValueError("four distinct owners and wallets required")
    if any(len(d["operations"]) != 24 for d in documents):
        raise ValueError("24 checkpoints per owner required")
    return documents


async def close_engine(engine: AsyncEngine, path: Path, primary: BaseException | None) -> None:
    try:
        pool = cast(QueuePool, engine.pool)
        before = pool.checkedout()
        await engine.dispose()
        save(
            path, {"disposed": True, "checked_out_before": before, "checked_out": pool.checkedout()}
        )
        if before or pool.checkedout():
            raise RuntimeError("connection leak")
    except BaseException as error:
        if primary is None:
            raise
        save(path, {"cleanup_error": type(error).__name__, "primary": type(primary).__name__})


async def capture(command: list[str]) -> str:
    process = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, _ = await process.communicate()
        if process.returncode:
            raise RuntimeError("read-only observer command failed")
        return stdout.decode()
    except BaseException:
        if process.returncode is None:
            with suppress(ProcessLookupError):
                process.kill()
            await process.communicate()
        raise


async def observe_database(database: str) -> dict[str, Any]:
    database = iso.database_name(database)
    sql = f"""BEGIN READ ONLY; SELECT json_build_object('connections',count(*),'rows',
      coalesce(json_agg(json_build_object('pid',pid,'role',usename,'state',state,
        'xact_start',xact_start,'wait_event_type',wait_event_type,'wait_event',wait_event,
        'blockers',pg_blocking_pids(pid)) ORDER BY pid),'[]'::json))
      FROM pg_stat_activity WHERE datname='{database}'; COMMIT;"""
    db = await capture(
        [
            "docker",
            "exec",
            iso.CONTAINER,
            "psql",
            "-X",
            "-qAt",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "postgres",
            "-c",
            sql,
        ]
    )
    return cast(dict[str, Any], json.loads(db))


async def observe_docker() -> dict[str, Any]:
    docker = await capture(
        ["docker", "stats", "--no-stream", "--format", "{{json .}}", iso.CONTAINER]
    )
    return cast(dict[str, Any], json.loads(docker))


async def observe_host() -> dict[str, Any]:
    memory = await capture(["vm_stat"])
    return {"load": os.getloadavg(), "host_memory": memory}


def collectors(database: str) -> dict[str, Any]:
    return {
        "database": lambda: observe_database(database),
        "host": observe_host,
        "docker": observe_docker,
    }


async def observe_resources(database: str) -> dict[str, Any]:
    started = time()
    db = await observe_database(database)
    docker = await observe_docker()
    host = await observe_host()
    return {
        "started_at": started,
        "finished_at": time(),
        **host,
        "container": docker,
        "database": db,
    }


async def sampler(database: str, path: Path, stop: asyncio.Event) -> None:
    with path.open("x") as stream:
        while not stop.is_set():
            try:
                row = await observe_resources(database)
            except BaseException as error:
                stream.write(
                    json.dumps({"at": time(), "missing": True, "error": type(error).__name__})
                    + "\n"
                )
                stream.flush()
                raise
            stream.write(json.dumps(row) + "\n")
            stream.flush()
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), 1.0)


async def snapshot_all(
    engine: AsyncEngine, documents: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    result = []
    for document in documents:
        async with user_session(
            engine, UUID(document["owner"]), role=DatabaseRole.ENGINE
        ) as session:
            result.append(
                {
                    "owner": document["owner"],
                    "raw": await checkpoint_snapshot(session, raw=True),
                    "normalized": await checkpoint_snapshot(session),
                }
            )
    return result


def verify_final(
    final: list[dict[str, Any]],
    initial: list[dict[str, Any]],
    reference: list[dict[str, Any]],
    writers: int,
) -> None:
    if len(final) != 4 or len(initial) != 4 or len(reference) != 4:
        raise ValueError("all four owners required in verification")
    for i, (actual, before, expected) in enumerate(zip(final, initial, reference, strict=True)):
        if actual["owner"] != before["owner"] or actual["owner"] != expected["owner"]:
            raise ValueError("snapshot owner identity mismatch")
        key, baseline = ("normalized", expected) if i < writers else ("raw", before)
        if actual[key] != baseline[key]:
            raise ValueError(f"owner {i} final history/state mismatch")


async def read_target(engine: AsyncEngine, target: dict[str, str], family: str) -> str | None:
    with operation_scope(phase="poll", owner=target["owner"], family=family):
        async with user_session(engine, UUID(target["owner"]), role=DatabaseRole.ENGINE) as session:
            if family == "command":
                command = await get_order_command(session, UUID(target["command"]))
                return None if command is None else command.state
            if family != "status":
                raise ValueError("unknown query family")
            return cast(
                str | None,
                (
                    await session.execute(
                        "SELECT status FROM paper_order_projections WHERE order_id=:order",
                        {"order": UUID(target["order"])},
                    )
                ).scalar_one_or_none(),
            )


async def poll(
    engine: AsyncEngine,
    target: dict[str, str],
    family: str,
    offset: float,
    ready: asyncio.Event,
    stop: asyncio.Event,
    metrics: dict[str, Any],
) -> None:
    await asyncio.sleep(offset)
    while not stop.is_set():
        metrics["started"] += 1
        try:
            value = await read_target(engine, target, family)
        except asyncio.CancelledError:
            metrics["cancelled"] += 1
            raise
        except Exception as error:
            metrics["errors"].append(type(error).__name__)
            raise
        metrics["completed"] += 1
        metrics.setdefault("first_completed", monotonic())
        metrics["last_completed"] = monotonic()
        metrics["absent"] += value is None
        ready.set()
        await asyncio.sleep(RESULT_POLL_SECONDS)


async def wait_files(paths: list[Path]) -> None:
    while not all(path.exists() for path in paths):
        await asyncio.sleep(0.01)


async def writer(args: argparse.Namespace) -> None:
    iso.verify_writer(args.source, args.writer_hash)
    actual_db = iso.database_name(
        str(make_url(os.environ[DatabaseRole.ENGINE.url_variable]).database)
    )
    await iso.verify_databases(actual_db)
    document = fixtures(args.fixtures)[args.owner]
    path = args.output / f"writer-{args.owner}"
    path.mkdir()
    engine = create_engine_for(DatabaseRole.ENGINE)
    pools = PoolEvidence(path / "pools.json")
    pools.add(engine, DatabaseRole.ENGINE)
    failure = None
    rows = []
    save(path / "control.json", {"started": monotonic(), "seconds": 900})
    observation = runtime.RuntimeObservation(
        path / "runtime.json", enabled=getattr(args, "profile", None) == runtime.PROFILE
    )
    trace = TransactionTrace(
        path / "transactions.jsonl",
        buffered=True,
        control=path / "control.json",
        monotonic_fields=observation.enabled,
    )
    try:
        async with observation.observe(), trace.observe():
            async with user_session(
                engine, UUID(document["owner"]), role=DatabaseRole.ENGINE
            ) as session:
                await session.execute("SELECT 1")
            observation.mark("ready")
            save(path / "ready.json", {"at": monotonic(), "owner": document["owner"]})
            await wait_files([args.output / "start.json"])
            observation.mark("writer_start")
            for index, item in enumerate(document["operations"], 1):
                with operation_scope(
                    phase="checkpoint", owner=document["owner"], operation=str(index)
                ):
                    async with asyncio.timeout(60):
                        cpu_start = runtime.stamp() if observation.enabled else None
                        measurement = await iso.timed_checkpoint(engine, document, item)
                        if cpu_start is not None:
                            cpu_end = runtime.stamp()
                            measurement.update(
                                cpu_start=cpu_start,
                                cpu_end=cpu_end,
                                process_cpu_seconds=cpu_end["cpu"] - cpu_start["cpu"],
                            )
                if index == len(document["operations"]):
                    observation.mark("final_checkpoint_commit")
                rows.append(
                    {
                        **measurement,
                        "owner": document["owner"],
                        "operation": index,
                        "kind": item["kind"],
                        "writer_sha256": args.writer_hash,
                    }
                )
                save(path / "measurements.json", rows)
                if index < 24:
                    await asyncio.sleep(PACE_SECONDS)
        save(path / "result.json", {"status": "OBSERVATION_COMPLETE", "operations": len(rows)})
    except BaseException as error:
        failure = error
        save(path / "failure.json", {"error": type(error).__name__, "completed": len(rows)})
        raise
    finally:
        pools.finish()
        await close_engine(engine, path / "closed.json", failure)
        if observation.enabled:
            save(path / "resources-closed.json", runtime.stamp())


async def run_group(
    args: argparse.Namespace,
    engine: AsyncEngine,
    targets: list[dict[str, str]],
    owners: list[int],
    polling: int,
    environment: dict[str, str],
) -> dict[str, Any]:
    """Join children/readers/observer before the caller may verify snapshots."""
    stop = asyncio.Event()
    readers: list[asyncio.Task[None]] = []
    poll_metrics = []
    began = monotonic()
    observation = runtime.RuntimeObservation(
        args.output / "runtime.json", enabled=getattr(args, "profile", None) == runtime.PROFILE
    )
    try:
        async with observation.observe(), asyncio.TaskGroup() as group:
            children = []
            for owner in owners:
                command = [
                    sys.executable,
                    "-m",
                    MODULE,
                    "writer",
                    "--fixtures",
                    str(args.fixtures),
                    "--output",
                    str(args.output),
                    "--source",
                    str(args.source),
                    "--writer-hash",
                    args.writer_hash,
                    "--owner",
                    str(owner),
                ]
                if observation.enabled:
                    command[-2:-2] = ["--profile", runtime.PROFILE]
                children.append(
                    group.create_task(
                        iso.child(
                            command, args.backend, environment, args.output / f"writer-{owner}.log"
                        )
                    )
                )
            ready = []
            if polling:
                for index, (owner, family, offset) in enumerate(assignments(len(owners))):
                    signal = asyncio.Event()
                    ready.append(signal)
                    counts: dict[str, Any] = {
                        "index": index,
                        "owner": targets[owner]["owner"],
                        "family": family,
                        "started": 0,
                        "completed": 0,
                        "cancelled": 0,
                        "errors": [],
                        "absent": 0,
                    }
                    poll_metrics.append(counts)
                    readers.append(
                        group.create_task(
                            poll(engine, targets[owner], family, offset, signal, stop, counts)
                        )
                    )
            async with asyncio.timeout(10):
                await wait_files([args.output / f"writer-{i}" / "ready.json" for i in owners])
                await asyncio.gather(*(signal.wait() for signal in ready))
            declared = pool_configuration(
                json.loads(
                    (
                        args.output.parent / "parent-pools.json"
                        if args.output.name.startswith("sequential-")
                        else args.output / "parent-pools.json"
                    ).read_text()
                )
            )
            for owner in owners:
                actual = pool_configuration(
                    json.loads((args.output / f"writer-{owner}" / "pools.json").read_text())
                )
                if actual != declared:
                    raise ValueError("writer pool differs from declared capacity")
            observation.mark("ready")
            sampler_task = group.create_task(
                runtime.resources(collectors(args.database), args.output, stop)
                if observation.enabled
                else sampler(args.database, args.output / "resources.jsonl", stop)
            )
            started = monotonic()
            save(args.output / "polls-at-start.json", poll_metrics)
            observation.mark("common_start")
            start_record = {"started": started}
            if observation.enabled:
                start_record.update(observation.phases[-1])
            save(args.output / "start.json", start_record)
            try:
                async with asyncio.timeout(60):
                    await asyncio.gather(*children)
            finally:
                writers_ended = monotonic()
                observation.mark("writers_joined")
                stop.set()
                for task in readers:
                    task.cancel()
                await asyncio.gather(*readers, return_exceptions=True)
                observation.mark("readers_stopped")
                if observation.enabled:
                    await runtime.finish_resources(sampler_task)
                else:
                    await sampler_task
                observation.mark("resources_closed")
        ended = monotonic()
        return {
            "readiness_seconds": started - began,
            "started": started,
            "ended": ended,
            "seconds": ended - started,
            "writers_ended": writers_ended,
            "writer_seconds": writers_ended - started,
            "polls": poll_metrics,
        }
    finally:
        save(args.output / "polls.json", poll_metrics)


def validate_measurements(rows: list[dict[str, Any]], documents: list[dict[str, Any]]) -> None:
    if len(rows) != len(documents) * 24:
        raise ValueError("incomplete checkpoint denominator")
    for document in documents:
        owned = [r for r in rows if r["owner"] == document["owner"]]
        if [r["operation"] for r in owned] != list(range(1, 25)):
            raise ValueError("missing or duplicate owner operation")
        if any(r["outcome"] != "COMMIT" or r["client_statements"] != 6 for r in owned):
            raise ValueError("unexpected writer outcome or statement count")


async def arm(args: argparse.Namespace) -> None:
    args.output.mkdir()
    iso.verify_writer(args.source, args.writer_hash)
    save(args.output / "preflight.json", await iso.verify_databases(args.database))
    documents = fixtures(args.fixtures)
    engine = create_engine_for(DatabaseRole.ENGINE)
    pools = PoolEvidence(args.output / "parent-pools.json")
    pools.add(engine, DatabaseRole.ENGINE)
    failure = None
    save(args.output / "control.json", {"started": monotonic(), "seconds": 900})
    trace = TransactionTrace(
        args.output / "transactions.jsonl",
        buffered=True,
        control=args.output / "control.json",
        monotonic_fields=getattr(args, "profile", None) == runtime.PROFILE,
    )
    try:
        initial = await snapshot_all(engine, documents)
        if initial != json.loads((args.fixtures / "initial.json").read_text()):
            raise ValueError("fresh clone mismatch")
        targets = json.loads((args.fixtures / "targets.json").read_text())
        if getattr(args, "profile", None) == runtime.PROFILE:
            preflight: dict[str, Any] = {}
            try:
                for family, collect in collectors(args.database).items():
                    row: dict[str, Any] = {}
                    preflight[family] = row
                    await runtime.collect_one(family, collect, row)
            finally:
                save(args.output / "observer-preflight.json", preflight)
        else:
            save(args.output / "observer-preflight.json", await observe_resources(args.database))
        inventory = [args.output / "parent-pools.json"]
        for i in range(args.writers):
            path = args.output / f"declared-writer-{i}.json"
            save(path, json.loads(inventory[0].read_text()))
            inventory.append(path)
        budget = await connection_budget(engine, inventory, expected_counts=[1] * len(inventory))
        save(args.output / "connection-budget.json", budget)
        if budget["limit"] < budget["declared_capacity"]:
            raise ValueError("insufficient declared connection headroom")
        environment = dict(os.environ)
        async with trace.observe():
            if args.reference is None:
                groups = []
                for i in range(4):
                    sub = argparse.Namespace(**vars(args))
                    sub.output = args.output / f"sequential-{i}"
                    sub.output.mkdir()
                    groups.append(await run_group(sub, engine, targets, [i], 0, environment))
            else:
                groups = [
                    await run_group(
                        args, engine, targets, list(range(args.writers)), args.pollers, environment
                    )
                ]
        final = await snapshot_all(engine, documents)
        save(args.output / "final.json", final)
        reference = (
            final
            if args.reference is None
            else json.loads((args.reference / "final.json").read_text())
        )
        verify_final(final, initial, reference, args.writers)
        rows = [
            row
            for path in sorted(args.output.rglob("measurements.json"))
            for row in json.loads(path.read_text())
        ]
        validate_measurements(rows, documents[: args.writers])
        save(
            args.output / "result.json",
            {
                "status": "OBSERVATION_COMPLETE",
                "acceptance_result": False,
                "writers": args.writers,
                "pollers": args.pollers,
                "operations": len(rows),
                "groups": groups,
                "measurements": rows,
                "checkpoint_p50": percentile([r["checkpoint_seconds"] for r in rows], 0.5),
                "checkpoint_p95": percentile([r["checkpoint_seconds"] for r in rows], 0.95),
                "transaction_p50": percentile([r["transaction_seconds"] for r in rows], 0.5),
                "transaction_p95": percentile([r["transaction_seconds"] for r in rows], 0.95),
            },
        )
    except BaseException as error:
        failure = error
        save(args.output / "failure.json", {"status": "INCOMPLETE", "error": type(error).__name__})
        raise
    finally:
        pools.finish()
        await close_engine(engine, args.output / "closed.json", failure)
        if getattr(args, "profile", None) == runtime.PROFILE:
            save(args.output / "resources-closed.json", runtime.stamp())


async def setup(args: argparse.Namespace) -> None:
    from tests.infra.execution_market.profile_checkpoint_fixture import prepare

    for i in range(4):
        await prepare(args.fixtures / f"fixture-{i}.json", btc_orders=20)
    documents = fixtures(args.fixtures)
    engine = create_engine_for(DatabaseRole.ENGINE)
    try:
        save(args.fixtures / "initial.json", await snapshot_all(engine, documents))
        targets = []
        for document in documents:
            order = document["operations"][0]["order"]
            async with user_session(
                engine, UUID(document["owner"]), role=DatabaseRole.ENGINE
            ) as session:
                command = (
                    await session.execute(
                        "SELECT command_id FROM paper_orders WHERE id=:order",
                        {"order": UUID(order)},
                    )
                ).scalar_one()
            targets.append({"owner": document["owner"], "order": order, "command": str(command)})
        save(args.fixtures / "targets.json", targets)
    finally:
        await engine.dispose()


async def campaign(args: argparse.Namespace) -> None:
    backend = Path(__file__).resolve().parents[3]
    args.output.mkdir(parents=True, exist_ok=False)
    logs = args.output / "logs"
    logs.mkdir()
    fixture_dir = args.output / "fixtures"
    fixture_dir.mkdir()
    source = backend / "src"
    source_hashes = {str(p.relative_to(source)): iso.digest(p) for p in source.rglob("*.py")}
    test_hashes = {
        str(p.relative_to(backend)): iso.digest(p) for p in (backend / "tests").rglob("*.py")
    }
    save(
        args.output / "source-hashes.json",
        {
            "production": source_hashes,
            "harness": test_hashes,
            "lock": iso.digest(backend / "uv.lock"),
        },
    )
    prefix = "tiewtrade_set4_iso_poll_" + uuid4().hex[:8]
    base = json.loads(args.environment.read_text())
    created = []
    results = []
    started = monotonic()
    status = "INCOMPLETE"
    try:
        async with asyncio.timeout(900):
            with tempfile.TemporaryDirectory(prefix="tiewtrade-nc07-") as temporary:
                frozen = Path(temporary) / "src"
                shutil.copytree(source, frozen, ignore=shutil.ignore_patterns("__pycache__"))
                template = prefix + "_template"
                await iso.clone_database(template, None, backend, logs / "create-template.log")
                created.append(template)
                env = iso.database_environment(base, template)
                env["PYTHONPATH"] = f"{frozen}:{backend}"
                await iso.child(
                    [sys.executable, "-m", "alembic", "upgrade", "head"],
                    backend,
                    env,
                    logs / "migrate.log",
                )
                await iso.child(
                    [sys.executable, "-m", MODULE, "setup", "--fixtures", str(fixture_dir)],
                    backend,
                    env,
                    logs / "prepare.log",
                )
                fixture_hashes = {p.name: iso.digest(p) for p in fixture_dir.glob("*.json")}
                save(args.output / "fixture-hashes.json", fixture_hashes)
                reference = args.output / "reference"
                for index, (writers, pollers) in enumerate([(4, 0), *conditions(args.profile)]):
                    database = prefix + f"_a{index}"
                    await iso.clone_database(
                        database, template, backend, logs / f"clone-{index}.log"
                    )
                    created.append(database)
                    arm_env = iso.database_environment(base, database)
                    arm_env["PYTHONPATH"] = env["PYTHONPATH"]
                    output = reference if index == 0 else args.output / f"arm-{index}"
                    command = [
                        sys.executable,
                        "-m",
                        MODULE,
                        "arm",
                        "--fixtures",
                        str(fixture_dir),
                        "--output",
                        str(output),
                        "--source",
                        str(frozen),
                        "--writer-hash",
                        source_hashes[str(iso.STORAGE)],
                        "--database",
                        database,
                        "--writers",
                        str(writers),
                        "--pollers",
                        str(pollers),
                    ]
                    command += ["--profile", args.profile]
                    if index:
                        command += ["--reference", str(reference)]
                    progress(f"{args.profile} arm {index}/8: writers={writers}, pollers={pollers}")
                    await iso.child(command, backend, arm_env, logs / f"arm-{index}.log")
                    results.append(json.loads((output / "result.json").read_text()))
                expected = 96 + sum(writers * 24 for writers, _ in conditions(args.profile))
                if sum(r["operations"] for r in results) != expected:
                    raise ValueError("campaign denominator mismatch")
                if source_hashes != {
                    str(p.relative_to(source)): iso.digest(p) for p in source.rglob("*.py")
                }:
                    raise ValueError("production source changed")
                if test_hashes != {
                    str(p.relative_to(backend)): iso.digest(p)
                    for p in (backend / "tests").rglob("*.py")
                }:
                    raise ValueError("harness source changed")
                if fixture_hashes != {p.name: iso.digest(p) for p in fixture_dir.glob("*.json")}:
                    raise ValueError("fixture changed during campaign")
                status = "OBSERVATION_COMPLETE"
    finally:
        save(
            args.output / "campaign.json",
            {
                "status": status,
                "profile": args.profile,
                "acceptance_result": False,
                "seconds": monotonic() - started,
                "databases": created,
                "results": results,
                "operations": sum(r["operations"] for r in results),
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("campaign", "setup", "arm", "writer"))
    for name in ("output", "fixtures", "source", "reference", "environment"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument(
        "--profile", choices=("concurrency-v1", runtime.PROFILE), default="concurrency-v1"
    )
    parser.add_argument("--database")
    parser.add_argument("--writer-hash")
    parser.add_argument("--writers", type=int, choices=(1, 4))
    parser.add_argument("--pollers", type=int, choices=(0, 100))
    parser.add_argument("--owner", type=int, choices=range(4))
    args = parser.parse_args()
    args.backend = Path(__file__).resolve().parents[3]
    asyncio.run(
        {"campaign": campaign, "setup": setup, "arm": arm, "writer": writer}[args.mode](args)
    )


if __name__ == "__main__":
    main()
