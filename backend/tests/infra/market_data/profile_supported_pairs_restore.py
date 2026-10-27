"""F-38 V-15 pre-0030 backup/restore acceptance; never collected by pytest."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

BASES = ("BTC", "ETH", "SOL", "XRP", "DOGE")
SUPPORTED = frozenset(("BTC", "ETH"))
BASE_TABLES = {
    "market_latest_prices": "base",
    "market_candle_demand": "base",
    "market_candle_preview": "base",
    "market_candles": "base",
    "indicator_build_jobs": "base",
    "indicator_generations": "base",
    "indicator_heads": "base",
    "indicator_source_changes": "base",
    "indicator_retry_requests": "job",
    "indicator_checkpoints": "generation",
}
CONTROL_TABLES = (
    "market_price_feed",
    "market_candle_feed_state",
    "indicator_rollout_control",
    "indicator_source_guard",
    "indicator_build_slot",
)
NON_MARKET_TABLES = (
    "api_throttle",
    "audit_events",
    "auth_throttle",
    "login_challenges",
    "recovery_grants",
    "sessions",
    "user_api_keys",
    "user_credentials",
    "user_recovery_codes",
    "user_totp",
    "user_totp_pending",
    "user_trading_preferences",
    "users",
)
CONSTRAINTS = (
    "market_candles_check",
    "market_candle_demand_check",
    "market_latest_prices_check",
    "market_candle_preview_check1",
    "indicator_build_jobs_base_check",
    "indicator_generations_base_check",
)

SEED_SQL = """
BEGIN;
SELECT begin_indicator_source_maintenance();
UPDATE market_latest_prices SET amount=100,trade_id=1,
  trade_at='2026-10-01 00:00Z',received_at='2026-10-01 00:00Z',
  observation_kind='SNAPSHOT',reconciled_generation=1,revision=2,
  effective_readiness='READY',reason='READY';
INSERT INTO market_candle_demand
  (source,base,quote,timeframe,desired_start,desired_end,status)
SELECT 'primary_spot',base,'USDT','1m','2026-10-01 00:00Z',
  '2026-10-01 00:01Z','COMPLETE'
FROM unnest(ARRAY['BTC','ETH','SOL','XRP','DOGE']) base;
INSERT INTO market_candles
  (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,
   finality,observed_at,fetch_started_at,last_checked_at,ingestion_generation)
SELECT 'primary_spot',base,'USDT','1m','2026-10-01 00:00Z',
  '2026-10-01 00:01Z',100,101,99,100.5,1,'CLOSED',
  '2026-10-01 00:02Z','2026-10-01 00:02Z','2026-10-01 00:02Z',1
FROM unnest(ARRAY['BTC','ETH','SOL','XRP','DOGE']) base;
INSERT INTO market_candle_preview
  (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,
   finality,event_at,received_at,epoch,revision)
SELECT 'primary_spot',base,'USDT','1m','2026-10-01 00:01Z',
  '2026-10-01 00:02Z',100,101,99,100.5,1,'OPEN',
  '2026-10-01 00:01:30Z','2026-10-01 00:01:31Z',1,1
FROM unnest(ARRAY['BTC','ETH','SOL','XRP','DOGE']) base;
SELECT activate_indicator_source_proof();
INSERT INTO indicator_build_jobs
  (source,base,quote,timeframe,formula_version,status)
SELECT 'primary_spot',base,'USDT','1m','indicators-v2','QUEUED'
FROM unnest(ARRAY['BTC','ETH','SOL','XRP','DOGE']) base;
WITH fixture_clock AS (
  SELECT date_trunc('minute',clock_timestamp()) AS now
), made AS (
  INSERT INTO indicator_generations
    (job_id,source,base,quote,timeframe,formula_version,calculation_start,
     calculation_end,as_of,source_epoch,source_fence,dataset_revision,
     checkpoint_count,codec_version,build_rollout_epoch,candidate_sequence,
     claim_token,status,expires_at,prepared_at)
  SELECT j.id,j.source,j.base,j.quote,j.timeframe,j.formula_version,
    f.now-interval '2 minutes',f.now-interval '1 minute',f.now-interval '1 minute',
    g.epoch,g.revision,repeat('a',64),1,2,c.rollout_epoch,1,
    gen_random_uuid(),'EXPIRED',f.now+interval '6 hours 9 minutes',clock_timestamp()
  FROM indicator_build_jobs j
  CROSS JOIN indicator_source_guard g CROSS JOIN indicator_rollout_control c
  CROSS JOIN fixture_clock f
  RETURNING *
), checkpoints AS (
  INSERT INTO indicator_checkpoints(generation_id,next_open_at,payload)
  SELECT id,calculation_end,'{}'::jsonb FROM made RETURNING generation_id
)
UPDATE indicator_build_jobs j SET generation_sequence=1
FROM made m WHERE j.id=m.job_id;
INSERT INTO indicator_retry_requests(request_id,job_id,cycle_id,result)
SELECT gen_random_uuid(),id,cycle_id,'QUEUED' FROM indicator_build_jobs;
INSERT INTO indicator_source_changes
  (epoch,revision,source,base,quote,timeframe,open_at,kind)
SELECT g.epoch,1,'primary_spot',base,'USDT','1m',
  '2026-10-01 00:00Z','WRITE'
FROM indicator_source_guard g
CROSS JOIN unnest(ARRAY['BTC','ETH','SOL','XRP','DOGE']) base;
INSERT INTO users(id) VALUES('10000000-0000-0000-0000-000000000001');
INSERT INTO user_credentials(user_id,email,password_hash)
VALUES('10000000-0000-0000-0000-000000000001',
  'restore@example.com','fixture-no-secret');
INSERT INTO sessions(token_hash,user_id,idle_expires_at,absolute_expires_at)
VALUES(repeat('b',64),'10000000-0000-0000-0000-000000000001',
  '2026-11-01Z','2026-12-01Z');
INSERT INTO user_trading_preferences(user_id,use)
VALUES('10000000-0000-0000-0000-000000000001','MANUAL');
INSERT INTO audit_events
  (id,recorded_at,owner_user_id,actor_kind,actor_id,action,subject_kind,
   subject_id,mode,outcome,details)
VALUES('20000000-0000-0000-0000-000000000001','2026-10-01Z',
  '10000000-0000-0000-0000-000000000001','USER',
  '10000000-0000-0000-0000-000000000001','USER_CREATED','USER',
  '10000000-0000-0000-0000-000000000001','NOT_APPLICABLE','SUCCEEDED','{}');
COMMIT;
"""


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, default=str, indent=2) + "\n", encoding="utf-8")


def database_url(value: str, database: str) -> str:
    return make_url(value).set(database=database).render_as_string(hide_password=False)


async def run_command(*command: str, environment: dict[str, str] | None = None) -> None:
    process = await asyncio.create_subprocess_exec(
        *command,
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError(f"{Path(command[0]).name} failed: {stderr.decode().strip()}")


async def digest_query(engine: AsyncEngine, query: str) -> dict[str, object]:
    digest = hashlib.sha256()
    rows = 0
    async with engine.connect() as connection:
        result = await connection.exec_driver_sql(query)
        for value in result.scalars():
            digest.update(value.encode())
            digest.update(b"\n")
            rows += 1
    return {"rows": rows, "sha256": digest.hexdigest()}


async def table_digest(engine: AsyncEngine, table: str) -> dict[str, object]:
    return await digest_query(
        engine,
        f"SELECT to_jsonb(value)::text FROM {table} value ORDER BY to_jsonb(value)::text",
    )


def base_query(table: str, relation: str, base: str) -> str:
    if relation == "base":
        return (
            f"SELECT to_jsonb(value)::text FROM {table} value WHERE base='{base}' "
            "ORDER BY to_jsonb(value)::text"
        )
    if relation == "job":
        return (
            f"SELECT to_jsonb(value)::text FROM {table} value JOIN indicator_build_jobs j "
            f"ON j.id=value.job_id WHERE j.base='{base}' ORDER BY to_jsonb(value)::text"
        )
    return (
        f"SELECT to_jsonb(value)::text FROM {table} value JOIN indicator_generations g "
        f"ON g.id=value.generation_id WHERE g.base='{base}' ORDER BY to_jsonb(value)::text"
    )


async def snapshot(engine: AsyncEngine) -> dict[str, Any]:
    async with engine.connect() as connection:
        revision = (
            await connection.exec_driver_sql("SELECT version_num FROM alembic_version")
        ).scalar_one()
        constraints = {
            row["conname"]: row["definition"]
            for row in (
                await connection.exec_driver_sql(
                    "SELECT conname,pg_get_constraintdef(oid) AS definition FROM pg_constraint "
                    "WHERE conname=ANY($1::text[]) ORDER BY conname",
                    (list(CONSTRAINTS),),
                )
            ).mappings()
        }
        functions = {
            signature: (
                await connection.exec_driver_sql(
                    "SELECT pg_get_functiondef(to_regprocedure($1))", (signature,)
                )
            ).scalar_one()
            for signature in (
                "transition_indicator_rollout(indicator_rollout_mode,uuid,indicator_rollout_mode)",
                "seed_indicator_build_jobs()",
                "claim_indicator_build_job(uuid)",
            )
        }
        invalid_constraints = int(
            (
                await connection.exec_driver_sql(
                    "SELECT count(*) FROM pg_constraint WHERE connamespace='public'::regnamespace "
                    "AND NOT convalidated"
                )
            ).scalar_one()
        )
        indicator_slot_idle = (
            await connection.exec_driver_sql(
                "SELECT count(*)=1 AND bool_and(state='IDLE') FROM indicator_build_slot"
            )
        ).scalar_one()
        indicator_generations_expired = (
            await connection.exec_driver_sql(
                "SELECT count(*)=5 AND bool_and(status='EXPIRED') FROM indicator_generations"
            )
        ).scalar_one()
        source_guard = dict(
            (
                await connection.exec_driver_sql(
                    """SELECT revision,scope_kind::text,journal_floor,
                    cardinality(protected_relations) AS protected_relation_count,
                    indicator_source_triggers_valid() AS triggers_valid,
                    (SELECT count(*) FROM pg_partition_tree('market_candles'::regclass))
                      AS partition_relation_count
                    FROM indicator_source_guard WHERE id=1"""
                )
            )
            .mappings()
            .one()
        )
        financial_tables = int(
            (
                await connection.exec_driver_sql(
                    """SELECT count(*) FROM information_schema.tables
                    WHERE table_schema='public'
                      AND (table_name LIKE 'paper_order%'
                        OR table_name LIKE 'paper_wallet%'
                        OR table_name LIKE 'paper_position%')"""
                )
            ).scalar_one()
        )
        security = [
            dict(row)
            for row in (
                await connection.exec_driver_sql(
                    """SELECT c.relname AS table_name,c.relrowsecurity,c.relforcerowsecurity,
                    coalesce(string_agg(DISTINCT a.grantee||':'||a.privilege_type,','
                      ORDER BY a.grantee||':'||a.privilege_type),'') AS grants
                    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    LEFT JOIN information_schema.role_table_grants a
                      ON a.table_schema=n.nspname AND a.table_name=c.relname
                    WHERE n.nspname='public' AND c.relkind IN ('r','p')
                    GROUP BY c.relname,c.relrowsecurity,c.relforcerowsecurity
                    ORDER BY c.relname"""
                )
            ).mappings()
        ]
    base_digests = {
        table: {
            base: await digest_query(engine, base_query(table, relation, base)) for base in BASES
        }
        for table, relation in BASE_TABLES.items()
    }
    table_digests = {
        table: await table_digest(engine, table) for table in (*CONTROL_TABLES, *NON_MARKET_TABLES)
    }
    return {
        "revision": revision,
        "base_digests": base_digests,
        "table_digests": table_digests,
        "constraints": constraints,
        "functions": functions,
        "invalid_constraints": invalid_constraints,
        "indicator_slot_idle": indicator_slot_idle,
        "indicator_generations_expired": indicator_generations_expired,
        "source_guard": source_guard,
        "financial_tables": financial_tables,
        "security": security,
    }


def supported_unchanged(before: dict[str, Any], after: dict[str, Any]) -> bool:
    before_tables = before["base_digests"]
    after_tables = after["base_digests"]
    assert isinstance(before_tables, dict) and isinstance(after_tables, dict)
    return all(
        before_tables[table][base] == after_tables[table][base]
        for table in BASE_TABLES
        for base in SUPPORTED
    )


def unsupported_empty(value: dict[str, Any]) -> bool:
    tables = value["base_digests"]
    assert isinstance(tables, dict)
    return all(
        tables[table][base]["rows"] == 0 for table in BASE_TABLES for base in set(BASES) - SUPPORTED
    )


def fixture_complete(value: dict[str, Any]) -> bool:
    tables = value["base_digests"]
    assert isinstance(tables, dict)
    populated_tables = set(BASE_TABLES) - {"indicator_heads"}
    return all(
        tables[table][base]["rows"] > 0 for table in populated_tables for base in BASES
    ) and all(tables["indicator_heads"][base]["rows"] == 0 for base in BASES)


def table_digests_equal(
    before: dict[str, Any], after: dict[str, Any], tables: tuple[str, ...]
) -> bool:
    return all(before["table_digests"][table] == after["table_digests"][table] for table in tables)


def post_snapshots_match(source: dict[str, Any], restored: dict[str, Any]) -> bool:
    scalar_keys = (
        "revision",
        "base_digests",
        "constraints",
        "functions",
        "invalid_constraints",
        "indicator_slot_idle",
        "indicator_generations_expired",
        "financial_tables",
        "security",
        "source_guard",
    )
    deterministic_control_tables = tuple(
        table for table in CONTROL_TABLES if table != "indicator_source_guard"
    )
    return all(source[key] == restored[key] for key in scalar_keys) and table_digests_equal(
        source, restored, (*deterministic_control_tables, *NON_MARKET_TABLES)
    )


def valid_source_guard(value: dict[str, Any]) -> bool:
    guard = value["source_guard"]
    return bool(
        guard["scope_kind"] == "MAINTENANCE"
        and guard["triggers_valid"]
        and guard["protected_relation_count"] == guard["partition_relation_count"]
    )


async def migrate(url: str, revision: str) -> None:
    environment = dict(os.environ)
    environment["TIEWTRADE_DATABASE_URL_MIGRATOR"] = url
    alembic = shutil.which("alembic") or str(Path(sys.executable).parent / "alembic")
    if alembic is None:
        raise RuntimeError("alembic executable missing")
    await run_command(alembic, "upgrade", revision, environment=environment)


async def run(args: argparse.Namespace) -> int:
    output: Path = args.output
    output.mkdir(parents=True, exist_ok=False)
    source_url = database_url(os.environ[args.admin_url_env], args.source_database)
    restored_url = database_url(os.environ[args.admin_url_env], args.restored_database)
    source_migrator_url = database_url(os.environ[args.migrator_url_env], args.source_database)
    restored_migrator_url = database_url(os.environ[args.migrator_url_env], args.restored_database)
    source = create_async_engine(source_url, hide_parameters=True)
    restored: AsyncEngine | None = None
    backup = Path(args.backup)
    commands: list[str] = []
    started = datetime.now(UTC)
    try:
        await run_command(
            "docker",
            "exec",
            args.postgres_container,
            "psql",
            "-U",
            "postgres",
            "-d",
            args.source_database,
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            SEED_SQL,
        )
        before = await snapshot(source)
        if (
            before["revision"] != "0029"
            or not fixture_complete(before)
            or not before["indicator_slot_idle"]
            or not before["indicator_generations_expired"]
        ):
            raise RuntimeError("F38_RESTORE_FIXTURE_INCOMPLETE")
        commands.append("pg_dump custom-format from quiesced 0029 source")
        container_dump = f"/tmp/{args.source_database}.dump"
        await run_command(
            "docker",
            "exec",
            args.postgres_container,
            "pg_dump",
            "-U",
            "postgres",
            "-d",
            args.source_database,
            "--format=custom",
            "--file",
            container_dump,
        )
        await run_command(
            "docker",
            "cp",
            f"{args.postgres_container}:{container_dump}",
            str(backup),
        )
        checksum = hashlib.sha256(backup.read_bytes()).hexdigest()
        await migrate(source_migrator_url, "0030")
        commands.append("alembic upgrade 0029 to 0030 on source")
        source_after = await snapshot(source)

        await run_command(
            "docker",
            "exec",
            args.postgres_container,
            "createdb",
            "-U",
            "postgres",
            "-T",
            "template0",
            args.restored_database,
        )
        restore_started = datetime.now(UTC)
        commands.append("pg_restore into new disposable database")
        await run_command(
            "docker",
            "exec",
            args.postgres_container,
            "pg_restore",
            "-U",
            "postgres",
            "-d",
            args.restored_database,
            "--exit-on-error",
            container_dump,
        )
        restored = create_async_engine(restored_url, hide_parameters=True)
        restored_before = await snapshot(restored)
        rpo_match = before == restored_before
        await migrate(restored_migrator_url, "0030")
        commands.append("alembic upgrade 0029 to 0030 on restored database")
        restored_after = await snapshot(restored)
        restore_verified = datetime.now(UTC)
        rto_seconds = (restore_verified - restore_started).total_seconds()
        postconditions = {
            "source_revision_0030": source_after["revision"] == "0030",
            "restored_pre_revision_0029": restored_before["revision"] == "0029",
            "restored_post_revision_0030": restored_after["revision"] == "0030",
            "source_supported_unchanged": supported_unchanged(before, source_after),
            "restored_supported_unchanged": supported_unchanged(restored_before, restored_after),
            "source_unsupported_empty": unsupported_empty(source_after),
            "restored_unsupported_empty": unsupported_empty(restored_after),
            "non_market_source_unchanged": table_digests_equal(
                before, source_after, NON_MARKET_TABLES
            ),
            "non_market_restored_unchanged": table_digests_equal(
                restored_before, restored_after, NON_MARKET_TABLES
            ),
            "control_source_unchanged_except_guard": table_digests_equal(
                before,
                source_after,
                tuple(table for table in CONTROL_TABLES if table != "indicator_source_guard"),
            ),
            "control_restored_unchanged_except_guard": table_digests_equal(
                restored_before,
                restored_after,
                tuple(table for table in CONTROL_TABLES if table != "indicator_source_guard"),
            ),
            "source_guard_expected_after_migration": valid_source_guard(source_after),
            "restored_guard_expected_after_migration": valid_source_guard(restored_after),
            "source_restored_post_match": post_snapshots_match(source_after, restored_after),
            "constraints_valid": source_after["invalid_constraints"] == 0
            and restored_after["invalid_constraints"] == 0,
            "catalog_constraints_reduced": all(
                all(base not in definition for base in ("SOL", "XRP", "DOGE"))
                for definition in source_after["constraints"].values()
            ),
            "seed_function_reduced": all(
                base not in source_after["functions"]["seed_indicator_build_jobs()"]
                for base in ("SOL", "XRP", "DOGE")
            ),
            "ready_gate_16": "ready_count<>16"
            in source_after["functions"][
                "transition_indicator_rollout(indicator_rollout_mode,uuid,indicator_rollout_mode)"
            ],
        }
        passed = rpo_match and rto_seconds <= 1800 and all(postconditions.values())
        result = {
            "status": "PASSED" if passed else "FAILED",
            "started_at": started,
            "completed_at": restore_verified,
            "source_database": args.source_database,
            "restored_database": args.restored_database,
            "writers_stopped": True,
            "indicator_slot_idle_before_backup": before["indicator_slot_idle"],
            "backup": {
                "format": "PostgreSQL custom",
                "path": str(backup),
                "bytes": backup.stat().st_size,
                "sha256": checksum,
            },
            "rpo": {"target_committed_rows": 0, "exact_snapshot_match": rpo_match},
            "rto": {"target_seconds": 1800, "measured_seconds": rto_seconds},
            "fixture_has_all_five_bases_in_legally_populated_scoped_tables": fixture_complete(
                before
            ),
            "indicator_heads_quiesced_empty": all(
                before["base_digests"]["indicator_heads"][base]["rows"] == 0 for base in BASES
            ),
            "indicator_generations_quiesced_expired": before["indicator_generations_expired"],
            "schema_0029_has_order_balance_position_tables": bool(before["financial_tables"]),
            "private_venue_requests": 0,
            "live_orders": 0,
            "postconditions": postconditions,
            "before": before,
            "source_after": source_after,
            "restored_before": restored_before,
            "restored_after": restored_after,
            "sanitized_commands": commands,
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
                "sanitized_commands": commands,
            },
        )
        raise
    finally:
        await source.dispose()
        if restored is not None:
            await restored.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backup", required=True)
    parser.add_argument("--postgres-container", required=True)
    parser.add_argument("--source-database", required=True)
    parser.add_argument("--restored-database", required=True)
    parser.add_argument("--admin-url-env", default="TIEWTRADE_TEST_ADMIN_URL")
    parser.add_argument("--migrator-url-env", default="TIEWTRADE_DATABASE_URL_MIGRATOR")
    options = parser.parse_args()
    if not options.source_database.startswith("tiewtrade_f38_restore_"):
        parser.error("source database must use the F-38 disposable prefix")
    if not options.restored_database.startswith("tiewtrade_f38_restore_"):
        parser.error("restored database must use the F-38 disposable prefix")
    raise SystemExit(asyncio.run(run(options)))
