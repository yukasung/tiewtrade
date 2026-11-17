"""NC-F17-TAIL-01: isolated evidence-history reads, never workload acceptance."""

from __future__ import annotations

import argparse
import ast
import asyncio
import hashlib
import json
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market import remaining_paper_campaign as campaign
from tests.infra.execution_market.profile_parent_poll import ParentPollGate
from tests.infra.execution_market.test_evidence import source_record
from tests.infra.execution_market.test_publisher_clock_recovery import financial_state
from tiewtrade.core.order_book import BookState
from tiewtrade.core.orders import SimulationProfile
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.paper_orders import storage

OWNERS = 20
HEAD = 144513
BATCH = 500
ROOT = Path(__file__).resolve().parents[4]
BASELINE_FIXTURE = Path(__file__).with_name("fixtures") / "tail_cursor_baseline.json"
READ_SCOPE: ContextVar[dict[str, Any] | None] = ContextVar("tail_read_timing", default=None)


def diagnostic_sql(source: str | None = None) -> str:
    """Bind the shared runtime query and both callers, not a private query copy."""
    tree = ast.parse(Path(workload.__file__).read_text() if source is None else source)
    queries = [
        node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "TAIL_CURSOR_SQL"
            for target in node.targets
        )
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ]
    if len(queries) != 1 or queries[0] != workload.TAIL_CURSOR_SQL:
        raise ValueError("shared cursor query differs from runtime")
    caller_assignment = "row = await read_input_cursor(session, owner.wallet.episode_id)"
    for name, reference, expression in (
        (
            "read_input_cursor",
            "TAIL_CURSOR_SQL",
            'return (await session.execute(TAIL_CURSOR_SQL, {"episode": episode})).one()',
        ),
        (
            "wait_for_input_recovery",
            "read_input_cursor",
            caller_assignment,
        ),
        (
            "drain_final_tail",
            "read_input_cursor",
            caller_assignment,
        ),
    ):
        functions = [
            node
            for node in tree.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == name
        ]
        if len(functions) != 1:
            raise ValueError("shared cursor query binding missing or ambiguous")
        function = functions[0]
        nodes = tuple(ast.walk(function))
        expected = ast.parse(expression).body[0]
        signature = ast.dump(expected)
        statement_matches = sum(
            ast.dump(node) == signature for node in nodes if isinstance(node, type(expected))
        )
        references = sum(isinstance(node, ast.Name) and node.id == reference for node in nodes)
        if (
            statement_matches != 1
            or references != 1
            or (name == "read_input_cursor" and len(function.body) != 1)
        ):
            raise ValueError("shared cursor query binding missing or ambiguous")
    return " ".join(queries[0].split())


def baseline_sql() -> str:
    """Load the verified immutable control even in a shallow/non-Git checkout."""
    try:
        fixture = json.loads(BASELINE_FIXTURE.read_text())
        receipt = json.loads(
            (
                ROOT / "specs/features/2026-11-02-tp-sl/evidence/"
                "endurance20-20261115/tail01-diagnostic-summary.json"
            ).read_text()
        )
        sql = " ".join(fixture["sql"].split())
        expected_digest = receipt["sql_sha256"]
        if (
            fixture["source_revision"] != "b0d5580364268be7619f5369dc8488d440f12160"
            or fixture["source_path"] != "backend/tests/infra/execution_market/profile_workload.py"
            or fixture["normalization"] != "single-space-whitespace"
            or fixture["sql_sha256"] != expected_digest
            or hashlib.sha256(sql.encode()).hexdigest() != expected_digest
        ):
            raise ValueError("control provenance or digest mismatch")
        return sql
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise ValueError("historical cursor query control is missing or invalid") from None


def require_space(root: Path) -> None:
    if shutil.disk_usage(root).free < 2 * 1024**3:
        raise RuntimeError("tail diagnostic disk headroom low")


@contextmanager
def observe_connection(engine: AsyncEngine) -> Iterator[None]:
    def checkout(*args: Any) -> None:
        if (row := READ_SCOPE.get()) is not None:
            row["checkout_at"] = monotonic()

    def begin(*args: Any) -> None:
        if (row := READ_SCOPE.get()) is not None:
            row["begin_at"] = monotonic()

    event.listen(engine.sync_engine, "checkout", checkout)
    event.listen(engine.sync_engine, "begin", begin)
    try:
        yield
    finally:
        event.remove(engine.sync_engine, "begin", begin)
        event.remove(engine.sync_engine, "checkout", checkout)


async def observe_read(
    engine: AsyncEngine,
    owner: workload.OwnerState,
    episode: UUID,
    sql: str,
    gate: ParentPollGate,
    rows: list[dict[str, Any]],
    *,
    explain: bool = False,
) -> Any:
    row: dict[str, Any] = {
        "owner": str(owner.user_id),
        "phase": gate.phase,
        "explain": explain,
        "started": monotonic(),
    }
    rows.append(row)
    token = READ_SCOPE.set(row)
    try:
        async with gate.permit(owner.user_id, "tail_explain" if explain else "tail_read"):
            row["session_enter_at"] = monotonic()
            async with user_session(
                engine, owner.user_id, role=DatabaseRole.ENGINE, cleanup_seconds=2
            ) as session:
                row["role_ready_at"] = monotonic()
                await session.execute("SET TRANSACTION READ ONLY")
                await session.execute("SELECT set_config('statement_timeout','10000',true)")
                row["query_started_at"] = monotonic()
                result = await session.execute(
                    ("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " if explain else "") + sql,
                    {"episode": episode},
                )
                value = result.scalar_one() if explain else dict(result.mappings().one())
                row["query_returned_at"] = monotonic()
            row["session_exited_at"] = monotonic()
        if not all(key in row for key in ("checkout_at", "begin_at")):
            raise RuntimeError("tail connection timing missing")
        row.update(outcome="RETURNED", value=value)
        return value
    except BaseException as error:
        row["outcome"] = type(error).__name__
        raise
    finally:
        row["finished"] = monotonic()
        READ_SCOPE.reset(token)


# Fixture-only bulk insertion follows storage.append_execution_inputs' CTE/keys
# relationship. Rows come from its production preparer; no constraints are disabled.
SEED_SQL = """WITH inserted AS (
 INSERT INTO paper_execution_inputs
 (id,user_id,wallet_id,episode_id,base,quote,input_id,generation,decision_kind,payload,digest,source_digest)
 SELECT id,user_id,wallet_id,episode_id,base,quote,input_id,generation,
 decision_kind,payload,digest,source_digest
 FROM jsonb_to_recordset(CAST(:rows AS jsonb)) AS r(
 id uuid,user_id uuid,wallet_id uuid,episode_id uuid,base text,quote text,input_id bigint,
 generation bigint,decision_kind text,payload jsonb,digest text,source_digest text)
 RETURNING recorded_at,id,user_id,wallet_id,episode_id,base,quote,generation,input_id,decision_kind)
 INSERT INTO paper_execution_input_keys
 (recorded_at,evidence_id,user_id,wallet_id,episode_id,base,quote,generation,input_id,decision_kind)
 SELECT recorded_at,id,user_id,wallet_id,episode_id,base,quote,generation,input_id,decision_kind
 FROM inserted"""


async def seed_history(
    engine: AsyncEngine,
    owner: workload.OwnerState,
    head: int,
    root: Path,
    *,
    generation: int = 1,
    rebase: bool = False,
) -> None:
    if type(head) is not int or not 0 <= head <= HEAD:
        raise ValueError("unsupported tail fixture head")
    template = source_record()
    assert isinstance(template.market, BookState)
    profile = SimulationProfile()
    for first in range(1, head + 1, BATCH):
        require_space(root)
        async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
            await storage.pin_execution_profile(
                session,
                wallet_id=owner.wallet.wallet_id,
                episode_id=owner.wallet.episode_id,
                profile=profile,
            )
            records = []
            for number in range(first, min(head + 1, first + BATCH)):
                record = replace(
                    template,
                    market=replace(
                        template.market, input_id=number, generation=generation, rebase=rebase
                    ),
                )
                record = replace(record, digest=storage._source_digest(record))
                records.append(
                    storage._prepare_execution_input(
                        session,
                        wallet_id=owner.wallet.wallet_id,
                        episode_id=owner.wallet.episode_id,
                        evidence_id=uuid4(),
                        record=record,
                        decision_market=None,
                        fee_version=profile.fee_version,
                        model_version=profile.liquidity_version,
                    )
                )
            await session.execute(SEED_SQL, {"rows": json.dumps(records, default=str)})


async def verify_owner(
    engine: AsyncEngine, owner: workload.OwnerState, head: int
) -> dict[str, Any]:
    async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
        keys = (
            (
                await session.execute(
                    """SELECT count(*) AS count,min(input_id) AS first,
            max(input_id) AS last FROM paper_execution_input_keys WHERE episode_id=:episode""",
                    {"episode": owner.wallet.episode_id},
                )
            )
            .mappings()
            .one()
        )
        if keys["count"] != head or (head and (keys["first"], keys["last"]) != (1, head)):
            raise RuntimeError("tail fixture history mismatch")
        samples = (
            (
                await session.execute(
                    """SELECT * FROM paper_execution_inputs
            WHERE episode_id=:episode AND input_id IN (1,:middle,:head)""",
                    {"episode": owner.wallet.episode_id, "middle": max(1, head // 2), "head": head},
                )
            )
            .mappings()
            .all()
        )
        for row in samples:
            storage._decode(row)
        return {"owner": str(owner.user_id), "keys": dict(keys), "decoded_samples": len(samples)}


async def run_pass(
    engine: AsyncEngine,
    owners: list[workload.OwnerState],
    sql: str,
    gate: ParentPollGate,
    rows: list[dict[str, Any]],
    *,
    concurrent: bool,
    label: str | None = None,
) -> None:
    async def read(owner: workload.OwnerState) -> None:
        value = await observe_read(engine, owner, owner.wallet.episode_id, sql, gate, rows)
        if value != {"availability": "READY", "input_id": HEAD}:
            raise RuntimeError("tail fixture cursor differs from expected")

    mode = "concurrent" if concurrent else "serial"
    gate.phase = mode if label is None else f"{label}_{mode}"
    if concurrent:
        async with asyncio.TaskGroup() as group:
            for owner in owners:
                group.create_task(read(owner))
    else:
        for owner in owners:
            await read(owner)


async def execute(root: Path, *, compare: bool = False) -> int:
    database = internal.guard_database(dict(os.environ))
    if len(database.encode("ascii")) > 63:
        raise ValueError("fixture database identifier exceeds PostgreSQL limit")
    root.mkdir(parents=True, exist_ok=False)
    sql = diagnostic_sql()
    control = baseline_sql() if compare else None
    candidate = campaign.hashes()
    campaign.pin_candidate(root, candidate)
    workload.save(root / "source-inventory.json", candidate)
    schema = await asyncio.to_thread(
        campaign.capture,
        "docker",
        "exec",
        "tiewtrade-postgres-1",
        "pg_dump",
        "-U",
        "postgres",
        "-d",
        database,
        "--schema-only",
        "--no-owner",
        "--no-privileges",
    )
    (root / "schema.sql").write_text(schema)
    (root / "runner.py").write_bytes(Path(__file__).read_bytes())
    engines = [
        create_engine_for(role)
        for role in (DatabaseRole.API, DatabaseRole.ENGINE, DatabaseRole.ENGINE_SCAN)
    ]
    api, engine, scan = engines
    gate = ParentPollGate()
    rows: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "status": "INCOMPLETE",
        "owners": OWNERS,
        "head": HEAD,
        "expected_keys": OWNERS * HEAD,
        "schema_sha256": hashlib.sha256(schema.encode()).hexdigest(),
        "sql": sql,
        "comparison": compare,
        "sql_baseline": control,
        "baseline_sha256": None
        if control is None
        else hashlib.sha256(control.encode()).hexdigest(),
        "sql_sha256": hashlib.sha256(sql.encode()).hexdigest(),
        "budget_seconds": 1500,
        "select_statement_timeout_ms": 10000,
        "measurement_cap_seconds": 300,
        "pool": workload.parent_pool_state(engine),
    }
    started = monotonic()
    report["started"] = started
    try:
        gate.verify_pool(engine)
        async with asyncio.timeout(1500):
            await internal.environment_preflight(
                root / "preflight.json", ROOT, campaign.check_services
            )
            await internal.require_empty_database()
            report["seed_started"] = monotonic()
            owners = await workload.seed_owners(api, engine, scan, OWNERS)
            for number, owner in enumerate(owners, 1):
                await seed_history(engine, owner, HEAD, root)
                workload.progress(f"tail fixture owner {number}/{OWNERS} seeded")
            report["fixture"] = [await verify_owner(engine, owner, HEAD) for owner in owners]
            report["seed_finished"] = monotonic()
            # Explicit fixture-only statistics, not a claim about historical W3 plans.
            admin_url = make_url(os.environ["TIEWTRADE_TEST_ADMIN_URL"])
            if admin_url.database != database:
                raise ValueError("fixture analysis database differs")
            admin = create_async_engine(admin_url, hide_parameters=True)
            try:
                async with admin.begin() as connection:
                    await connection.exec_driver_sql("ANALYZE paper_execution_input_keys")
                    await connection.exec_driver_sql("ANALYZE paper_order_activity")
            finally:
                await admin.dispose()
            report["analyzed_fixture_tables"] = [
                "paper_execution_input_keys",
                "paper_order_activity",
            ]
            before = [await financial_state(engine, owner.user_id) for owner in owners]
            report["measurement_started"] = monotonic()
            with observe_connection(engine):
                async with asyncio.timeout(300):
                    arms = [("old", control), ("new", sql)] if compare else [(None, sql)]
                    for concurrent in (False, True):
                        for label, query in arms:
                            assert query is not None
                            await run_pass(
                                engine,
                                owners,
                                query,
                                gate,
                                rows,
                                concurrent=concurrent,
                                label=label,
                            )
                    for label, query in arms:
                        assert query is not None
                        gate.phase = "explain" if label is None else f"{label}_explain"
                        for index in (0, 9, 19):
                            owner = owners[index]
                            await observe_read(
                                engine,
                                owner,
                                owner.wallet.episode_id,
                                query,
                                gate,
                                rows,
                                explain=True,
                            )
            report["measurement_finished"] = monotonic()
            after = [await financial_state(engine, owner.user_id) for owner in owners]
            if before != after:
                raise RuntimeError("tail read diagnostic changed financial state")
            report["financial_state_unchanged"] = True
            report["services_after"] = await campaign.check_services()
            if campaign.hashes() != candidate:
                raise RuntimeError("tail candidate changed")
            report.update(status="DIAGNOSTIC_COMPLETE", candidate_unchanged=True)
            return 0
    except BaseException as error:
        report["error_type"] = type(error).__name__
        raise
    finally:
        for owned in engines:
            await owned.dispose()
        report.update(
            elapsed_seconds=monotonic() - started,
            observations=rows,
            pool_after=workload.parent_pool_state(engine),
        )
        gate.save(root / "poll-gate.json")
        workload.save(root / "result.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(execute(args.output, compare=args.compare)))
