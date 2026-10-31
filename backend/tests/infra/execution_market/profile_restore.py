"""F-15 W4 PostgreSQL backup/restore verifier; never collected by pytest."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse
from uuid import UUID

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from tests.infra.execution_market.profile_workload import AllowPaperPolicy
from tiewtrade.core.money import Money
from tiewtrade.core.orders import AdmissionPolicy, OrderScope, TradingMode
from tiewtrade.core.positions import PositionPair, rebuild_position
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_orders.matching_storage import load_matching_state
from tiewtrade.infra.paper_orders.storage import read_execution_inputs
from tiewtrade.infra.positions import read_effective_executions, read_position_snapshot
from tiewtrade.services.engine.paper_order import run_paper_order_round

PAPER_TABLES: tuple[str, ...] = (
    "audit_events",
    "market_execution_state",
    "market_execution_buffer",
    "market_execution_demand",
    "paper_wallet_commands",
    "paper_wallet_admission_results",
    "paper_wallet_command_dispatch",
    "paper_wallet_command_results",
    "paper_wallets",
    "paper_wallet_episodes",
    "paper_wallet_episode_closures",
    "paper_wallet_state",
    "paper_wallet_ledger",
    "paper_execution_profiles",
    "paper_market_dependencies",
    "paper_order_activity",
    "paper_order_initializations",
    "paper_order_commands",
    "paper_order_command_results",
    "paper_order_dispatch",
    "paper_orders",
    "paper_execution_inputs",
    "paper_execution_input_keys",
    "paper_order_events",
    "paper_order_projections",
    "paper_reservations",
    "paper_execution_links",
    "paper_position_activity",
    "paper_position_events",
    "paper_position_projections",
    "paper_position_external_fees",
    "paper_position_conflicts",
)


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, default=str, indent=2) + "\n", encoding="utf-8")


def postgres_url(value: str) -> str:
    return value.replace("postgresql+asyncpg://", "postgresql://", 1)


def database_url(value: str, database: str) -> str:
    return make_url(value).set(database=database).render_as_string(hide_password=False)


def command_connection(value: str, database: str | None = None) -> tuple[list[str], dict[str, str]]:
    parsed = urlparse(postgres_url(value))
    if parsed.scheme != "postgresql" or not parsed.hostname or not parsed.username:
        raise ValueError("PostgreSQL URL is invalid")
    command = ["--host", parsed.hostname, "--username", unquote(parsed.username)]
    if parsed.port is not None:
        command.extend(("--port", str(parsed.port)))
    command.extend(("--dbname", database or parsed.path.removeprefix("/")))
    environment = dict(os.environ)
    if parsed.password is not None:
        environment["PGPASSWORD"] = unquote(parsed.password)
    return command, environment


def postgres_command(
    tool: str,
    value: str,
    *,
    database: str | None = None,
    container: str | None = None,
) -> tuple[list[str], dict[str, str]]:
    options, environment = command_connection(value, database)
    if container is None:
        return [tool, *options], environment
    parsed = urlparse(postgres_url(value))
    options = [
        "--username",
        unquote(parsed.username or ""),
        "--dbname",
        database or parsed.path.removeprefix("/"),
    ]
    password = environment.pop("PGPASSWORD", None)
    command = ["docker", "exec"]
    if password is not None:
        command.extend(("-e", f"PGPASSWORD={password}"))
    command.extend((container, tool, *options))
    return command, environment


async def run_command(*command: str, environment: dict[str, str]) -> None:
    process = await asyncio.create_subprocess_exec(
        *command,
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"{command[0]} failed: {stderr.decode().strip()}")


async def table_digest(engine: AsyncEngine, table: str) -> dict[str, object]:
    digest = hashlib.sha256()
    rows = 0
    async with engine.connect() as connection:
        result = await connection.exec_driver_sql(
            f"SELECT to_jsonb(value)::text FROM {table} AS value ORDER BY to_jsonb(value)::text"
        )
        for value in result.scalars():
            digest.update(value.encode())
            digest.update(b"\n")
            rows += 1
    return {"rows": rows, "sha256": digest.hexdigest()}


async def database_digest(engine: AsyncEngine) -> dict[str, dict[str, object]]:
    return {table: await table_digest(engine, table) for table in PAPER_TABLES}


async def economic_digest(engine: AsyncEngine) -> dict[str, dict[str, object]]:
    return {
        table: await table_digest(engine, table)
        for table in (
            "paper_wallet_ledger",
            "paper_position_events",
            "paper_position_projections",
            "paper_execution_links",
        )
    }


async def security_shape(engine: AsyncEngine) -> list[dict[str, object]]:
    async with engine.connect() as connection:
        rows = (
            await connection.exec_driver_sql(
                """SELECT c.relname AS table_name,c.relrowsecurity,c.relforcerowsecurity,
                coalesce(string_agg(DISTINCT p.rolname||':'||a.privilege_type,','
                  ORDER BY p.rolname||':'||a.privilege_type),'') AS grants
                FROM pg_class c
                JOIN pg_namespace n ON n.oid=c.relnamespace
                LEFT JOIN information_schema.role_table_grants a
                  ON a.table_schema=n.nspname AND a.table_name=c.relname
                LEFT JOIN pg_roles p ON p.rolname=a.grantee
                WHERE n.nspname='public' AND c.relname LIKE 'paper_%'
                GROUP BY c.relname,c.relrowsecurity,c.relforcerowsecurity
                ORDER BY c.relname"""
            )
        ).mappings()
        return [dict(row) for row in rows]


async def fixture_coverage(engine: AsyncEngine) -> dict[str, int]:
    async with engine.connect() as connection:
        row = (
            (
                await connection.exec_driver_sql(
                    """SELECT
                (SELECT count(*) FROM paper_wallet_ledger
                  WHERE kind='EXTERNAL_CAPITAL') AS capital,
                (SELECT count(*) FROM paper_order_events WHERE event_kind='FILL') AS fills,
                (SELECT count(*) FROM paper_order_projections
                  WHERE status='PARTIALLY_FILLED'
                    OR (status='CANCELED' AND filled_quantity>0)) AS partial_orders,
                (SELECT count(*) FROM paper_order_events WHERE event_kind='CANCELED') AS cancels,
                (SELECT count(*) FROM paper_position_events
                  WHERE event_kind IN ('REPLACE','VOID')) AS corrections,
                (SELECT count(*) FROM paper_wallet_episode_closures) AS resets,
                (SELECT count(*) FROM paper_execution_inputs) AS evidence,
                (SELECT count(*) FROM paper_order_dispatch
                  WHERE state='CLAIMED' AND lease_until<=clock_timestamp()) AS expired_claims"""
                )
            )
            .mappings()
            .one()
        )
    return {key: int(value) for key, value in row.items()}


async def replay_restored_domain(admin: AsyncEngine, engine: AsyncEngine) -> dict[str, object]:
    async with admin.connect() as connection:
        owners = (
            (
                await connection.exec_driver_sql(
                    """SELECT e.user_id,e.wallet_id,e.id AS episode_id,
                e.id=s.active_episode_id AS active
                FROM paper_wallet_episodes e
                JOIN paper_wallet_state s USING(wallet_id,user_id)
                ORDER BY e.user_id,e.started_at"""
                )
            )
            .mappings()
            .all()
        )
    evidence = 0
    checkpoints = 0
    replayed_positions = 0
    for owner in owners:
        user_id = UUID(str(owner["user_id"]))
        episode_id = UUID(str(owner["episode_id"]))
        async with user_session(engine, user_id, role=DatabaseRole.ENGINE) as session:
            snapshot = await read_position_snapshot(session, episode_id)
            if snapshot is None:
                raise RuntimeError("F15_W4_MISSING_POSITION_SOURCE")
            replayed_cash = Money.of(0, "USDT")
            for position in snapshot.positions:
                facts = await read_effective_executions(session, episode_id, position.pair)
                by_sequence = {fact.source_sequence: fact for fact in facts}
                rebuilt = rebuild_position(
                    position.pair,
                    tuple(
                        by_sequence.get(sequence)
                        for sequence in range(1, snapshot.activity.source_sequence + 1)
                    ),
                )
                if (
                    rebuilt.state.held_quantity != position.held_quantity
                    or rebuilt.state.total_cost != position.total_cost
                    or rebuilt.state.realized_pnl != position.realized_pnl
                ):
                    raise RuntimeError("F15_W4_POSITION_REPLAY_MISMATCH")
                replayed_cash = replayed_cash + rebuilt.effects.quote_cash_delta
                replayed_positions += 1
            cash = (
                await session.execute(
                    """SELECT coalesce(sum(amount),0) FROM paper_wallet_ledger
                    WHERE episode_id=:episode AND kind IN ('TRADE_CASH','CORRECTION_CASH')""",
                    {"episode": episode_id},
                )
            ).scalar_one()
            if replayed_cash != Money.of(cash, "USDT"):
                raise RuntimeError("F15_W4_CASH_REPLAY_MISMATCH")
            cursor = 0
            while True:
                batch = await read_execution_inputs(
                    session,
                    episode_id=episode_id,
                    pair=PositionPair("BTC", "USDT"),
                    after_input_id=cursor,
                    limit=4096,
                )
                if not batch:
                    break
                evidence += len(batch)
                cursor = batch[-1].record.market.input_id
            if owner["active"]:
                await load_matching_state(
                    session,
                    wallet_id=UUID(str(owner["wallet_id"])),
                    scope=OrderScope(user_id, episode_id, TradingMode.PAPER),
                    pair=PositionPair("BTC", "USDT"),
                )
                checkpoints += 1
    return {
        "owners": len(owners),
        "evidence_records": evidence,
        "checkpoints": checkpoints,
        "replayed_positions": replayed_positions,
    }


async def recover_expired_claims(
    admin: AsyncEngine,
    engine: AsyncEngine,
    scan: AsyncEngine,
    *,
    policy: AdmissionPolicy | None = None,
) -> dict[str, int]:
    async with admin.connect() as connection:
        before = int(
            (
                await connection.exec_driver_sql(
                    """SELECT count(*) FROM paper_order_dispatch
                    WHERE state='CLAIMED' AND lease_until<=clock_timestamp()"""
                )
            ).scalar_one()
        )
    rounds = 0
    while rounds < 100:
        result = await run_paper_order_round(
            engine=engine,
            scan_engine=scan,
            worker="f15-w4-claim-recovery",
            policy=AllowPaperPolicy() if policy is None else policy,
        )
        rounds += 1
        if result.processed + result.deferred + result.skipped == 0:
            break
    async with admin.connect() as connection:
        after = int(
            (
                await connection.exec_driver_sql(
                    """SELECT count(*) FROM paper_order_dispatch
                    WHERE state='CLAIMED' AND lease_until<=clock_timestamp()"""
                )
            ).scalar_one()
        )
    return {"expired_before": before, "expired_after": after, "rounds": rounds}


async def run(args: argparse.Namespace, *, recovery_policy: AdmissionPolicy | None = None) -> int:
    output: Path = args.output
    output.mkdir(parents=True, exist_ok=False)
    source_url = os.environ[args.source_url_env]
    admin_url = os.environ[args.admin_url_env]
    source = create_async_engine(source_url, hide_parameters=True)
    target_url = database_url(admin_url, args.target_database)
    target = create_async_engine(target_url, hide_parameters=True)
    target_engine = create_async_engine(
        database_url(os.environ[DatabaseRole.ENGINE.url_variable], args.target_database),
        hide_parameters=True,
    )
    target_scan = create_async_engine(
        database_url(os.environ[DatabaseRole.ENGINE_SCAN.url_variable], args.target_database),
        hide_parameters=True,
    )
    backup = output / "f15-w4.dump"
    started = datetime.now(UTC)
    try:
        coverage = await fixture_coverage(source)
        missing = [key for key, value in coverage.items() if value == 0]
        if missing:
            raise RuntimeError("F15_W4_FIXTURE_INCOMPLETE:" + ",".join(missing))
        before = await database_digest(source)
        before_security = await security_shape(source)
        dump_command, source_environment = postgres_command(
            "pg_dump",
            source_url,
            container=args.postgres_container,
        )
        dump_path = f"/tmp/{args.target_database}.dump" if args.postgres_container else str(backup)
        await run_command(
            *dump_command,
            "--format=custom",
            "--file",
            dump_path,
            environment=source_environment,
        )
        if args.postgres_container:
            await run_command(
                "docker",
                "cp",
                f"{args.postgres_container}:{dump_path}",
                str(backup),
                environment=dict(os.environ),
            )
        create_command, admin_environment = postgres_command(
            "createdb", admin_url, container=args.postgres_container
        )
        create_command = create_command[:-2]
        await run_command(
            *create_command,
            args.target_database,
            environment=admin_environment,
        )
        restore_command, target_environment = postgres_command(
            "pg_restore",
            admin_url,
            database=args.target_database,
            container=args.postgres_container,
        )
        await run_command(
            *restore_command,
            "--exit-on-error",
            dump_path,
            environment=target_environment,
        )
        after = await database_digest(target)
        after_security = await security_shape(target)
        replay = await replay_restored_domain(target, target_engine)
        economic_before_recovery = await economic_digest(target)
        claim_recovery = await recover_expired_claims(
            target, target_engine, target_scan, policy=recovery_policy
        )
        economic_after_recovery = await economic_digest(target)
        passed = (
            before == after
            and before_security == after_security
            and replay["evidence_records"] == coverage["evidence"]
            and claim_recovery["expired_before"] == coverage["expired_claims"]
            and claim_recovery["expired_after"] == 0
            and economic_before_recovery == economic_after_recovery
        )
        result = {
            "phase": "W4",
            "status": "PASSED" if passed else "FAILED",
            "started_at": started,
            "completed_at": datetime.now(UTC),
            "platform": platform.platform(),
            "target_database": args.target_database,
            "fixture_coverage": coverage,
            "source": before,
            "restored": after,
            "rls_and_grants_match": before_security == after_security,
            "canonical_data_match": before == after,
            "domain_replay": replay,
            "claim_recovery": claim_recovery,
            "claim_recovery_economic_effects_unchanged": (
                economic_before_recovery == economic_after_recovery
            ),
            "backup_bytes": backup.stat().st_size,
        }
        save(output / "result.json", result)
        return 0 if passed else 1
    except Exception as error:
        save(
            output / "failure.json",
            {
                "failed_at": datetime.now(UTC),
                "error_type": type(error).__name__,
                "error": str(error),
            },
        )
        raise
    finally:
        await source.dispose()
        await target.dispose()
        await target_engine.dispose()
        await target_scan.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--target-database", required=True)
    parser.add_argument("--source-url-env", default="TIEWTRADE_TEST_ADMIN_URL")
    parser.add_argument("--admin-url-env", default="TIEWTRADE_TEST_ADMIN_URL")
    parser.add_argument("--postgres-container")
    options = parser.parse_args()
    if not options.target_database.startswith("tiewtrade_f15_w4_"):
        parser.error("target database must start with tiewtrade_f15_w4_")
    raise SystemExit(asyncio.run(run(options)))
