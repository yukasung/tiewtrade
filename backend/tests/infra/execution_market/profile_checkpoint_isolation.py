"""NC-SET4-06: one bounded, paired checkpoint experiment; never acceptance."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import event, make_url, text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.pool import QueuePool

from tests.infra.execution_market.profile_checkpoint_fixture import checkpoint_snapshot
from tests.infra.execution_market.profile_workload import percentile, progress, save
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.paper_orders import matching_storage
from tiewtrade.infra.paper_orders.codec import state_from_payload

LEGACY_HEAD = "98ff2f840fe08dc46ab5eb9976f17bdf32b062b1"
LEGACY_HASH = "396c2f4e7dac1b3518a8cfe7c2a675a98d408d237d9af4fe6d34e4ca31b30ad6"
STORAGE = Path("tiewtrade/infra/paper_orders/matching_storage.py")
CONTAINER = "tiewtrade-postgres-1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def database_name(value: str) -> str:
    if not re.fullmatch(r"tiewtrade_set4_iso_[a-z0-9_]{1,40}", value):
        raise ValueError("isolated scratch database name required")
    return value


@dataclass(frozen=True)
class Arm:
    btc_orders: int
    block: int
    index: int
    writer: str
    database: str


def schedule(prefix: str) -> list[Arm]:
    database_name(prefix)
    arms = [
        Arm(size, block, index, writer, database_name(f"{prefix}_f{size}_b{block}_a{index}"))
        for size in (2, 20)
        for block in range(1, 4)
        for index, writer in enumerate(("direct", "batch", "batch", "direct"), 1)
    ]
    if len({arm.database for arm in arms}) != 24:
        raise ValueError("independent arm databases required")
    return arms


def database_environment(base: dict[str, str], database: str) -> dict[str, str]:
    database_name(database)
    urls = {role: make_url(base[role.url_variable]) for role in DatabaseRole}
    if len({(url.host, url.port, url.database) for url in urls.values()}) != 1 or any(
        url.username != role.value or (url.host, url.port) != ("127.0.0.1", 55432)
        for role, url in urls.items()
    ):
        raise ValueError("role URL or local database identity mismatch")
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("TIEWTRADE_")
    }
    environment.update(
        {
            role.url_variable: url.set(database=database).render_as_string(hide_password=False)
            for role, url in urls.items()
        }
    )
    return environment


async def verify_databases(database: str) -> dict[str, Any]:
    database_name(database)
    result: dict[str, Any] = {}
    for role in DatabaseRole:
        engine = create_engine_for(role)
        failed = False
        try:
            async with engine.connect() as connection:
                identity = (
                    await connection.execute(text("SELECT current_database(),current_user"))
                ).one()
                if tuple(identity) != (database, role.value):
                    raise ValueError("actual role/database identity mismatch")
                result[role.name] = {"database": identity[0], "role": identity[1]}
                if role is DatabaseRole.MIGRATOR:
                    if (
                        await connection.execute(text("SELECT version_num FROM alembic_version"))
                    ).scalar_one() != "0066":
                        raise ValueError("schema0066 required")
                    row = (
                        await connection.execute(
                            text("""SELECT p.prosrc,p.prosecdef,
                        p.provolatile::text,p.proconfig FROM pg_proc p JOIN pg_namespace n
                        ON n.oid=p.pronamespace WHERE n.nspname='public'
                        AND p.proname='paper_persist_checkpoint_v1'""")
                        )
                    ).one()
                    migration = importlib.import_module("migrations.versions.0065_checkpoint_batch")
                    if tuple(row) != (
                        migration._FUNCTION.split("$$")[1],
                        False,
                        "v",
                        ["search_path=pg_catalog"],
                    ):
                        raise ValueError("checkpoint function source/authority mismatch")
                    result["function_body_sha256"] = hashlib.sha256(row.prosrc.encode()).hexdigest()
        except BaseException:
            failed = True
            raise
        finally:
            try:
                await engine.dispose()
            except BaseException:
                if not failed:
                    raise
    return result


def verify_writer(source: Path, expected_hash: str) -> None:
    actual = Path(matching_storage.__file__).resolve()
    if actual != (source / STORAGE).resolve() or digest(actual) != expected_hash:
        raise ValueError("isolated writer source mismatch")


async def timed_checkpoint(
    engine: AsyncEngine, document: dict[str, Any], item: dict[str, Any]
) -> dict[str, Any]:
    """One checkpoint; context exit is included, snapshots/pacing are excluded."""
    state = state_from_payload(item["state"])
    count = 0
    counting = False

    def statement(*values: Any) -> None:
        nonlocal count
        if counting:
            count += 1

    event.listen(engine.sync_engine, "before_cursor_execute", statement)
    try:
        started = monotonic()
        async with user_session(
            engine, UUID(document["owner"]), role=DatabaseRole.ENGINE
        ) as session:
            counting = True
            checkpoint_start = monotonic()
            try:
                await matching_storage.persist_checkpoint(
                    session,
                    wallet_id=UUID(document["wallet"]),
                    state=state,
                    anchor_order_id=UUID(item["order"]),
                    event_kind=item["kind"],
                    decision_kind=item["decision"],
                    occurred_at=datetime.fromisoformat(item["at"]),
                    decision_id=UUID(item["id"]),
                )
            finally:
                checkpoint_seconds = monotonic() - checkpoint_start
                counting = False
        ended = monotonic()
        return {
            "rows": len(state.orders),
            "client_statements": count,
            "checkpoint_seconds": checkpoint_seconds,
            "transaction_seconds": ended - started,
            "started": started,
            "ended": ended,
            "outcome": "COMMIT",
        }
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", statement)


async def measure_arm(args: argparse.Namespace) -> None:
    args.output.mkdir(parents=True, exist_ok=False)
    verify_writer(args.source, args.writer_hash)
    preflight = await verify_databases(args.database)
    document = json.loads(args.fixture.read_text())
    operations = document["operations"]
    size = len(operations) - 4
    if size not in (2, 20):
        raise ValueError("unexpected fixture denominator")
    metadata = {
        "acceptance_result": False,
        "fixture_sha256": digest(args.fixture),
        "fixture_identity": f"CHECKPOINT_ISOLATION_BTC{size}_ETH2_V1",
        "operations": len(operations),
        "writer": args.writer,
        "writer_sha256": args.writer_hash,
        "database": args.database,
        "preflight": preflight,
    }
    save(args.output / "manifest.json", metadata)
    if args.reference is not None:
        reference = json.loads((args.reference / "result.json").read_text())
        if not (
            reference["writer"] == "direct"
            and reference["fixture_sha256"] == metadata["fixture_sha256"]
            and reference["operations"] == len(operations)
            and reference["status"] == "OBSERVATION_COMPLETE"
        ):
            raise ValueError("complete direct reference for identical fixture required")
    engine = create_engine_for(DatabaseRole.ENGINE)
    failure: BaseException | None = None
    try:
        async with user_session(
            engine, UUID(document["owner"]), role=DatabaseRole.ENGINE
        ) as session:
            initial = await checkpoint_snapshot(session, raw=True)
            headers = (await session.execute("SELECT count(*) FROM paper_orders")).scalar_one()
        if headers != size + 2 or initial["paper_order_events"]:
            raise ValueError("fresh prepared template required")
        save(args.output / "initial-raw.json", initial)
        if args.initial is None:
            return  # Template inspection only; never runs an operation.
        if initial != json.loads(args.initial.read_text()):
            raise ValueError("clone differs from prepared template")
        # Identical owner-session warm-up for both variants; no financial write.
        async with user_session(
            engine, UUID(document["owner"]), role=DatabaseRole.ENGINE
        ) as session:
            await session.execute("SELECT 1")
        measurements = []
        for index, item in enumerate(operations, 1):
            async with asyncio.timeout(60):
                timing = await timed_checkpoint(engine, document, item)
                # Verification is a separate transaction, outside both timing boundaries.
                async with user_session(
                    engine, UUID(document["owner"]), role=DatabaseRole.ENGINE
                ) as session:
                    raw = await checkpoint_snapshot(session, raw=True)
                    normalized = await checkpoint_snapshot(session)
                save(args.output / f"operation-{index:02d}-raw.json", raw)
                normalized_path = args.output / f"operation-{index:02d}-normalized.json"
                save(normalized_path, normalized)
                measurement = {
                    "operation": index,
                    "kind": item["kind"],
                    **timing,
                    "normalized_sha256": digest(normalized_path),
                }
                measurements.append(measurement)
                save(args.output / "measurements.json", measurements)
                if args.reference is not None and normalized != json.loads(
                    (args.reference / normalized_path.name).read_text()
                ):
                    raise ValueError(f"checkpoint snapshot mismatch at operation{index}")
        save(
            args.output / "result.json",
            {**metadata, "status": "OBSERVATION_COMPLETE", "measurements": measurements},
        )
    except BaseException as error:
        failure = error
        with suppress(OSError):
            save(
                args.output / "failure.json",
                {"error_type": type(error).__name__, "acceptance_result": False},
            )
        raise
    finally:
        try:
            pool = cast(QueuePool, engine.pool)
            before = pool.checkedout()
            await engine.dispose()
            save(
                args.output / "closed.json",
                {
                    "disposed": True,
                    "checked_out_before_dispose": before,
                    "checked_out": pool.checkedout(),
                },
            )
            if before != 0 or pool.checkedout() != 0:
                raise RuntimeError("checkpoint arm leaked a connection")
        except BaseException:
            if failure is None:
                raise


async def child(command: list[str], cwd: Path, environment: dict[str, str], log: Path) -> None:
    with log.open("x") as stream:
        process = await asyncio.create_subprocess_exec(
            *command, cwd=cwd, env=environment, stdout=stream, stderr=stream
        )
        try:
            code = await process.wait()
            if code != 0:
                raise RuntimeError(f"isolated subprocess failed; see {log.name}")
        except BaseException:
            if process.returncode is None:
                with suppress(ProcessLookupError):
                    process.send_signal(signal.SIGINT)
                try:
                    await asyncio.wait_for(process.wait(), 5)
                except TimeoutError:
                    process.kill()
                    await process.wait()
            raise


async def clone_database(name: str, template: str | None, backend: Path, log: Path) -> None:
    sql = f"CREATE DATABASE {database_name(name)} OWNER tiewtrade_migrator"
    if template is not None:
        sql += f" TEMPLATE {database_name(template)}"
    await child(
        [
            "docker",
            "exec",
            CONTAINER,
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "postgres",
            "-c",
            sql,
        ],
        backend,
        dict(os.environ),
        log,
    )


def summarize(arms: list[dict[str, Any]]) -> dict[str, Any]:
    if len(arms) != 24 or sum(len(arm["measurements"]) for arm in arms) != 360:
        raise ValueError("complete predeclared campaign required")
    blocks = []
    for size in (2, 20):
        for block in range(1, 4):
            group = [arm for arm in arms if arm["btc_orders"] == size and arm["block"] == block]
            if [arm["writer"] for arm in group] != ["direct", "batch", "batch", "direct"]:
                raise ValueError("ABBA order required")
            row: dict[str, Any] = {"btc_orders": size, "block": block}
            for writer in ("direct", "batch"):
                samples = [
                    m for arm in group if arm["writer"] == writer for m in arm["measurements"]
                ]
                row[writer] = {
                    field: {
                        "total": sum(m[field] for m in samples),
                        "p50": percentile([m[field] for m in samples], 0.5),
                        "p95": percentile([m[field] for m in samples], 0.95),
                    }
                    for field in ("checkpoint_seconds", "transaction_seconds")
                }
            row["batch_over_direct_checkpoint_ratio"] = (
                row["batch"]["checkpoint_seconds"]["total"]
                / row["direct"]["checkpoint_seconds"]["total"]
            )
            row["batch_over_direct_transaction_ratio"] = (
                row["batch"]["transaction_seconds"]["total"]
                / row["direct"]["transaction_seconds"]["total"]
            )
            blocks.append(row)
    return {
        "acceptance_result": False,
        "status": "OBSERVATION_COMPLETE",
        "arms": arms,
        "blocks": blocks,
    }


async def campaign(args: argparse.Namespace) -> None:
    backend = Path(__file__).resolve().parents[3]
    args.output.mkdir(parents=True, exist_ok=False)
    logs = args.output / "logs"
    logs.mkdir()
    started = monotonic()
    prefix = "tiewtrade_set4_iso_" + uuid4().hex[:8]
    arms = schedule(prefix)
    base = json.loads(args.environment.read_text())
    created: list[str] = []
    results: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {
        "acceptance_result": False,
        "prefix": prefix,
        "schedule": [asdict(a) for a in arms],
        "total_cap_seconds": 900,
        "operation_cap_seconds": 60,
        "created_databases": created,
        "platform": platform.platform(),
        "python": sys.version,
        "uv_lock_sha256": digest(backend / "uv.lock"),
        "host_cpu_count": os.cpu_count(),
        "host_load_average_before": os.getloadavg(),
        "host_free_bytes_before": shutil.disk_usage(backend).free,
        "unrelated_workload_attribution": (
            "Unknown; host load averages do not identify individual workloads"
        ),
    }
    harness = {
        str(p.relative_to(backend)): digest(p) for p in sorted((backend / "tests").rglob("*.py"))
    }
    manifest["harness_hashes"] = harness
    save(args.output / "campaign.json", manifest)
    campaign_error: BaseException | None = None
    source_workspace = tempfile.TemporaryDirectory(prefix="tiewtrade-set4-isolation-")
    try:
        async with asyncio.timeout(900):
            await child(
                ["docker", "port", CONTAINER, "5432/tcp"],
                backend,
                dict(os.environ),
                logs / "docker-port.log",
            )
            ports = (logs / "docker-port.log").read_text().splitlines()
            if not ports or any(not port.endswith(":55432") for port in ports):
                raise ValueError("local Docker port mismatch")
            # Isolated source trees have identical Python files except the pinned writer.
            sources = Path(source_workspace.name)
            for variant in ("direct", "batch"):
                shutil.copytree(
                    backend / "src" / "tiewtrade",
                    sources / variant / "tiewtrade",
                    ignore=shutil.ignore_patterns("__pycache__"),
                )
            old = subprocess.check_output(
                ["git", "show", f"{LEGACY_HEAD}:backend/src/{STORAGE}"], cwd=backend
            )
            if hashlib.sha256(old).hexdigest() != LEGACY_HASH:
                raise ValueError("legacy source proof mismatch")
            (sources / "direct" / STORAGE).write_bytes(old)
            hashes = {
                variant: {
                    str(p.relative_to(sources / variant)): digest(p)
                    for p in sorted((sources / variant).rglob("*.py"))
                }
                for variant in ("direct", "batch")
            }
            differences = [p for p in hashes["direct"] if hashes["direct"][p] != hashes["batch"][p]]
            if differences != [str(STORAGE)] or hashes["direct"].keys() != hashes["batch"].keys():
                raise ValueError("writer must be the only source difference")
            save(args.output / "source-hashes.json", hashes)
            schema = prefix + "_schema"
            await clone_database(schema, None, backend, logs / "schema-create.log")
            created.append(schema)
            await child(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                backend,
                database_environment(base, schema),
                logs / "migration.log",
            )
            template_paths: dict[int, tuple[str, Path, Path]] = {}
            for size in (2, 20):
                template = prefix + f"_f{size}"
                await clone_database(template, schema, backend, logs / f"template-{size}.log")
                created.append(template)
                fixture = args.output / f"fixture-{size}.json"
                environment = database_environment(base, template)
                await child(
                    [
                        sys.executable,
                        "-m",
                        "tests.infra.execution_market.profile_checkpoint_fixture",
                        "prepare",
                        "--btc-orders",
                        str(size),
                        "--fixture",
                        str(fixture),
                    ],
                    backend,
                    environment,
                    logs / f"prepare-{size}.log",
                )
                initial = args.output / f"template-{size}"
                await launch_arm(
                    backend,
                    sources,
                    base,
                    template,
                    fixture,
                    initial,
                    "batch",
                    None,
                    None,
                    logs / f"inspect-{size}.log",
                )
                template_paths[size] = template, fixture, initial / "initial-raw.json"
            references: dict[int, Path] = {}
            for arm in arms:
                template, fixture, initial = template_paths[arm.btc_orders]
                await clone_database(
                    arm.database, template, backend, logs / f"{arm.database}-clone.log"
                )
                created.append(arm.database)
                save(args.output / "campaign.json", manifest)
                output = args.output / arm.database
                await launch_arm(
                    backend,
                    sources,
                    base,
                    arm.database,
                    fixture,
                    output,
                    arm.writer,
                    initial,
                    references.get(arm.btc_orders),
                    logs / f"{arm.database}-run.log",
                )
                result = json.loads((output / "result.json").read_text())
                results.append({**asdict(arm), **result})
                if arm.btc_orders not in references:
                    references[arm.btc_orders] = output
                progress(
                    f"arm {len(results)}/24: BTC{arm.btc_orders} block{arm.block} {arm.writer}"
                )
            current = {
                str(p.relative_to(backend / "src")): digest(p)
                for p in sorted((backend / "src" / "tiewtrade").rglob("*.py"))
            }
            if current != hashes["batch"] or any(
                digest(backend / p) != value for p, value in harness.items()
            ):
                raise ValueError("candidate source or harness changed during campaign")
            save(
                args.output / "result.json",
                {**summarize(results), "elapsed_seconds": monotonic() - started},
            )
    except BaseException as error:
        campaign_error = error
        with suppress(OSError):
            save(
                args.output / "failure.json",
                {
                    "acceptance_result": False,
                    "status": "INCOMPLETE",
                    "error_type": type(error).__name__,
                    "completed_arms": len(results),
                    "elapsed_seconds": monotonic() - started,
                },
            )
        raise
    finally:
        try:
            source_workspace.cleanup()
            manifest["host_load_average_after"] = os.getloadavg()
            manifest["host_free_bytes_after"] = shutil.disk_usage(backend).free
            save(
                args.output / "campaign.json",
                {**manifest, "elapsed_seconds": monotonic() - started},
            )
        except OSError:
            if campaign_error is None:
                raise


async def launch_arm(
    backend: Path,
    sources: Path,
    base: dict[str, str],
    database: str,
    fixture: Path,
    output: Path,
    writer: str,
    initial: Path | None,
    reference: Path | None,
    log: Path,
) -> None:
    source = sources / writer
    environment = database_environment(base, database)
    environment["PYTHONPATH"] = os.pathsep.join((str(source), str(backend)))
    command = [
        sys.executable,
        "-m",
        "tests.infra.execution_market.profile_checkpoint_isolation",
        "arm",
        "--fixture",
        str(fixture),
        "--output",
        str(output),
        "--database",
        database,
        "--source",
        str(source),
        "--writer-hash",
        digest(source / STORAGE),
        "--writer",
        writer,
    ]
    if initial is not None:
        command.extend(("--initial", str(initial)))
    if reference is not None:
        command.extend(("--reference", str(reference)))
    await child(command, backend, environment, log)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("campaign", "arm"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--environment", type=Path)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--database")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--writer-hash")
    parser.add_argument("--writer", choices=("direct", "batch"))
    parser.add_argument("--initial", type=Path)
    parser.add_argument("--reference", type=Path)
    parsed = parser.parse_args()
    parsed.output = parsed.output.resolve()
    if parsed.action == "campaign" and parsed.environment is None:
        parser.error("campaign requires environment file")
    if parsed.action == "arm" and any(
        getattr(parsed, key) is None
        for key in ("fixture", "database", "source", "writer_hash", "writer")
    ):
        parser.error("arm requires fixture/database/source/hash/writer")
    asyncio.run(campaign(parsed) if parsed.action == "campaign" else measure_arm(parsed))
