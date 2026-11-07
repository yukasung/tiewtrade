"""NC12 F16/F17 extension of the existing F15 backup/restore harness."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import traceback
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urlparse
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market import profile_restore as restore
from tests.infra.execution_market import profile_restore_fixture as legacy
from tests.infra.execution_market import profile_workload as f15
from tests.infra.execution_market.profile_internal import readonly_admin as readonly_admin
from tests.infra.execution_market.profile_protections import verify_exit
from tests.infra.execution_market.test_dispatch import intent
from tests.infra.manual_orders.test_bridge import select_use
from tests.infra.protections.test_lifecycle import buy, execute
from tests.infra.protections.test_validation import publish_price
from tiewtrade.core.protections import ProtectionState
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import UserSession, market_data_session
from tiewtrade.infra.market_data.realtime_storage import read_snapshot, set_connected
from tiewtrade.infra.paper_orders import worker as order_worker
from tiewtrade.infra.paper_orders.codec import intent_from_payload, intent_payload
from tiewtrade.infra.paper_orders.dispatch import ClaimedOrder
from tiewtrade.infra.paper_orders.requests import admit_new_request, get_request_by_key
from tiewtrade.infra.protections import worker
from tiewtrade.infra.protections.storage import admit_request, groups, load
from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy

TABLES = (
    "paper_order_requests",
    "paper_order_request_results",
    "paper_order_request_dispatch",
    "paper_protection_protocol",
    "paper_protection_requests",
    "paper_protection_results",
    "paper_protections",
    "paper_protection_events",
    "paper_protection_exits",
    "paper_protection_exit_progress",
    "paper_protection_request_progress",
    "user_trading_preferences",
    "risk_protocol_control",
    "risk_owner_state",
)


async def extension_security(engine: AsyncEngine) -> list[dict[str, Any]]:
    # Include table/column ACLs and policy definitions for all extension tables.
    async with engine.connect() as connection:
        tables = (
            (
                await connection.execute(
                    text("""SELECT c.relname,c.relrowsecurity,
            c.relforcerowsecurity,c.relacl::text FROM pg_class c
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relname=ANY(:tables) ORDER BY c.relname"""),
                    {"tables": list(TABLES)},
                )
            )
            .mappings()
            .all()
        )
        columns = (
            (
                await connection.execute(
                    text("""SELECT c.relname,a.attname,a.attacl::text
          FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
          JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
          WHERE n.nspname='public' AND c.relname=ANY(:tables) ORDER BY c.relname,a.attname"""),
                    {"tables": list(TABLES)},
                )
            )
            .mappings()
            .all()
        )
        policies = (
            (
                await connection.execute(
                    text("""SELECT tablename,policyname,permissive,roles,
          cmd,qual,with_check FROM pg_policies WHERE schemaname='public'
          AND tablename=ANY(:tables) ORDER BY tablename,policyname"""),
                    {"tables": list(TABLES)},
                )
            )
            .mappings()
            .all()
        )
        functions = (
            (
                await connection.execute(
                    text("""SELECT p.oid::regprocedure::text name,
          p.prosecdef,p.proacl::text,p.proconfig::text FROM pg_proc p
          JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public'
          AND (p.proname LIKE '%protection%' OR p.proname LIKE '%order_request%')
          ORDER BY p.oid::regprocedure::text""")
                )
            )
            .mappings()
            .all()
        )
    return [
        dict(row) for collection in (tables, columns, policies, functions) for row in collection
    ]


async def extension_coverage(admin: AsyncEngine) -> dict[str, int]:
    async with admin.connect() as connection:
        result = (
            (
                await connection.execute(
                    text("""SELECT
          (SELECT count(*) FROM paper_order_requests q WHERE NOT EXISTS(
            SELECT 1 FROM paper_order_request_results r WHERE r.request_id=q.id)) pending_intake,
          (SELECT count(*) FROM paper_order_request_results WHERE state='TRANSFERRED') transferred,
          (SELECT count(*) FROM paper_protections WHERE state='ARMED') armed,
          (SELECT count(*) FROM paper_protections WHERE state='EXITING') exiting,
          (SELECT count(*) FROM paper_protections WHERE state='CLOSED') closed,
          (SELECT count(*) FROM paper_protection_request_progress p
            WHERE attempt>0 AND NOT EXISTS(SELECT 1 FROM paper_protection_results r
              WHERE r.request_id=p.request_id)) retry""")
                )
            )
            .mappings()
            .one()
        )
    return {key: int(value) for key, value in result.items()}


async def build_extension(engines: dict[DatabaseRole, AsyncEngine], output: Path) -> dict[str, Any]:
    api, engine, scan, market = (
        engines[role]
        for role in (
            DatabaseRole.API,
            DatabaseRole.ENGINE,
            DatabaseRole.ENGINE_SCAN,
            DatabaseRole.MARKET_DATA,
        )
    )
    # Keep the legacy 3-owner fixture and add 17 owners, for 20 total owners.
    owners = await f15.seed_owners(api, engine, scan, 17)
    staged = []
    for owner in owners[1:]:
        source, _, _, _, group = await buy(api, engine, scan, owner.user_id, owner.wallet)
        staged.append(
            {
                "owner": str(owner.user_id),
                "wallet": str(owner.wallet.wallet_id),
                "episode": str(owner.wallet.episode_id),
                "group": str(group),
            }
        )
        await source.dispose()
    # Produce a real completed exit through the same writer as lifecycle validation.
    closed = staged[2]
    await publish_price(market, "111")
    async with user_session(engine, UUID(closed["owner"]), role=DatabaseRole.ENGINE) as session:
        await worker.process_group(session, UUID(closed["group"]))
        command = (
            await session.execute(
                "SELECT command_id FROM paper_protection_exits WHERE protection_id=:id",
                {"id": UUID(closed["group"])},
            )
        ).scalar_one()
    stop = asyncio.Event()
    stats: dict[str, Any] = {"target_hz": 10}
    publisher = asyncio.create_task(
        f15.market_publisher(market, stop, stats, heartbeat_per_book=True)
    )
    try:
        await f15.wait_publisher_ready(publisher, stats)
        async with asyncio.timeout(60):
            while True:
                await execute(
                    engine, UUID(closed["owner"]), command, policy=TransactionalRiskPolicy()
                )
                async with user_session(
                    engine, UUID(closed["owner"]), role=DatabaseRole.ENGINE
                ) as session:
                    await worker.process_group(session, UUID(closed["group"]))
                    current = await load(session, UUID(closed["group"]))
                if current is not None and current.value.state is ProtectionState.CLOSED:
                    break
                await asyncio.sleep(0.25)
        await verify_exit(engine, owners[3], UUID(closed["group"]))
    finally:
        stop.set()
        await publisher
    # Pending exit is committed before backup, but its execution is not driven yet.
    exiting = staged[1]
    await publish_price(market, "111")
    async with user_session(engine, UUID(exiting["owner"]), role=DatabaseRole.ENGINE) as session:
        await worker.process_group(session, UUID(exiting["group"]))
    await publish_price(market, "100")
    # F16 pending receipt: preserve the exact NEW identity across restore and retry.
    owner = owners[0]
    await select_use(api, owner.user_id)
    value = intent(owner.user_id, owner.wallet.episode_id)
    async with user_session(api, owner.user_id) as session:
        receipt = await admit_new_request(
            session,
            wallet_id=owner.wallet.wallet_id,
            intent=value,
            protection={"tp": "110", "sl": "90"},
        )
    pending = {
        "owner": str(owner.user_id),
        "wallet": str(owner.wallet.wallet_id),
        "episode": str(owner.wallet.episode_id),
        "receipt": str(receipt.request_id),
        "intent": intent_payload(value),
    }
    # A real unavailable source creates durable replacement retry state.
    retry = staged[3]
    async with market_data_session(market) as session:
        snapshot = await read_snapshot(session)
        assert snapshot.feed is not None
        await set_connected(session, snapshot.feed, False)
    async with user_session(engine, UUID(retry["owner"]), role=DatabaseRole.ENGINE) as session:
        current = await load(session, UUID(retry["group"]))
        assert current is not None
    payload = {
        "quantity": "0.5",
        "tp": "120",
        "sl": "80",
        "expected_revision": current.value.revision,
    }
    key = uuid4()
    async with user_session(api, UUID(retry["owner"])) as session:
        request = await admit_request(
            session,
            wallet_id=UUID(retry["wallet"]),
            episode_id=UUID(retry["episode"]),
            action="REPLACE",
            key=key,
            protection_id=UUID(retry["group"]),
            payload=payload,
        )
    async with user_session(engine, UUID(retry["owner"]), role=DatabaseRole.ENGINE) as session:
        await worker.process_request(session, request)
    result = {
        "owners": staged,
        "pending": pending,
        "exiting": exiting,
        "closed": closed,
        "retry": {**retry, "request": str(request), "key": str(key), "payload": payload},
    }
    f15.save(output / "internal-fixture.json", result)
    return result


def guard_restore(args: argparse.Namespace, environment: dict[str, str]) -> None:
    source = internal.guard_database(environment)
    expected = urlparse(environment[DatabaseRole.MIGRATOR.url_variable])
    for variable in (args.source_url_env, args.admin_url_env):
        supplied = urlparse(environment.get(variable, ""))
        if (supplied.hostname, supplied.port, supplied.path) != (
            expected.hostname,
            expected.port,
            expected.path,
        ):
            raise ValueError("internal restore admin/source must match the isolated role database")
    if args.action == "verify" and (
        not re.fullmatch(r"tiewtrade_internal20_[a-z0-9_]+", args.target_database or "")
        or args.target_database == source
    ):
        raise ValueError("internal restore requires a separate isolated target")
    if args.postgres_container not in (None, "tiewtrade-postgres-1"):
        raise ValueError("internal restore container differs from the approved local PostgreSQL")


async def build(args: argparse.Namespace) -> int:
    guard_restore(args, dict(os.environ))
    await internal.require_empty_database()
    await legacy.run(args)
    engines = {
        role: create_engine_for(role)
        for role in (
            DatabaseRole.API,
            DatabaseRole.ENGINE,
            DatabaseRole.ENGINE_SCAN,
            DatabaseRole.MIGRATOR,
            DatabaseRole.MARKET_DATA,
        )
    }
    observer = readonly_admin(source_variable=args.source_url_env)
    try:
        async with internal.activated_protocols(engines[DatabaseRole.MIGRATOR], protections=True):
            await build_extension(engines, args.output)
            coverage = await extension_coverage(observer)
            if not all(coverage.values()):
                raise RuntimeError("INTERNAL_RESTORE_FIXTURE_INCOMPLETE")
            f15.save(args.output / "internal-coverage.json", coverage)
    finally:
        await observer.dispose()
        for engine in engines.values():
            await engine.dispose()
    return 0


@contextmanager
def observe_rejections(path: Path) -> Iterator[None]:
    """Observe the caught domain exception without changing rejection or exposing inputs."""
    original = order_worker._reject

    async def observed(
        session: UserSession, claim: ClaimedOrder, command: Any, failure_code: str
    ) -> None:
        error = sys.exception()
        frames = [] if error is None else traceback.extract_tb(error.__traceback__)
        backend = Path(__file__).resolve().parents[3]
        locations = []
        for frame in frames:
            source = Path(frame.filename).resolve()
            locations.append(
                {
                    "file": str(source.relative_to(backend))
                    if source.is_relative_to(backend)
                    else source.name,
                    "function": frame.name,
                    "line": frame.lineno,
                }
            )
        record = {
            "command_id": str(command["id"]),
            "failure_code": failure_code,
            "error_type": None if error is None else type(error).__name__,
            "locations": locations,
            "stage": "rejection_requested",
        }
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
        await original(session, claim, command, failure_code)

    order_worker._reject = observed
    try:
        yield
    finally:
        order_worker._reject = original


async def check_terminal_rejection(session: UserSession, request: UUID, output: Path) -> None:
    row = (
        (
            await session.execute(
                """SELECT r.state AS intake_state,r.command_id,
        c.state AS command_state,coalesce(r.failure_code,c.failure_code) AS failure_code
        FROM paper_order_request_results r LEFT JOIN paper_order_command_results c
        ON c.command_id=r.command_id WHERE r.request_id=:id""",
                {"id": request},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is not None and (
        row["intake_state"] == "REJECTED" or row["command_state"] == "REJECTED"
    ):
        f15.save(output / "terminal-rejection.json", dict(row))
        raise RuntimeError("INTERNAL_RESTORE_TERMINAL_REJECTION")


def restored_worker_factory(
    engines: Mapping[DatabaseRole, AsyncEngine],
) -> Callable[[DatabaseRole], AsyncEngine]:
    urls = {
        role: engines[role].url.render_as_string(hide_password=False)
        for role in (DatabaseRole.ENGINE, DatabaseRole.ENGINE_SCAN)
    }

    def create(role: DatabaseRole) -> AsyncEngine:
        # Construction is synchronous: no other asyncio task can see the scoped URL.
        # The normal factory retains role credentials, pool defaults and ownership.
        with patch.dict(os.environ, {role.url_variable: urls[role]}):
            return create_engine_for(role)

    return create


async def integrated_digest(engine: AsyncEngine) -> dict[str, Any]:
    # Called before starting / after joining recovery, matching the W4 table scope.
    with patch.object(restore, "PAPER_TABLES", (*restore.PAPER_TABLES, *TABLES)):
        return await restore.database_digest(engine)


async def recover(
    engines: dict[DatabaseRole, AsyncEngine],
    fixture: dict[str, Any],
    output: Path,
    *,
    observer: AsyncEngine,
) -> None:
    api, engine = engines[DatabaseRole.API], engines[DatabaseRole.ENGINE]
    pending = fixture["pending"]
    value = intent_from_payload(pending["intent"])
    async with user_session(api, UUID(pending["owner"])) as session:
        for _ in range(2):
            receipt = await admit_new_request(
                session,
                wallet_id=UUID(pending["wallet"]),
                intent=value,
                protection={"tp": "110", "sl": "90"},
            )
            assert str(receipt.request_id) == pending["receipt"]
    retry = fixture["retry"]
    async with user_session(api, UUID(retry["owner"])) as session:
        request = await admit_request(
            session,
            wallet_id=UUID(retry["wallet"]),
            episode_id=UUID(retry["episode"]),
            action="REPLACE",
            key=UUID(retry["key"]),
            protection_id=UUID(retry["group"]),
            payload=retry["payload"],
        )
        assert str(request) == retry["request"]
    # Owner checks on the restored roles, before starting real workers.
    for record in fixture["owners"]:
        async with user_session(api, UUID(record["owner"])) as session:
            assert await load(session, UUID(record["group"])) is not None
        async with user_session(api, UUID(pending["owner"])) as session:
            assert await load(session, UUID(record["group"])) is None
    before = await restore.economic_digest(observer)
    stop, worker_stop = asyncio.Event(), output / "recovery.stop"
    publisher = asyncio.create_task(
        f15.market_publisher(
            engines[DatabaseRole.MARKET_DATA], stop, {"target_hz": 10}, heartbeat_per_book=True
        )
    )
    rejection_observer = observe_rejections(output / "rejections.jsonl")
    rejection_observer.__enter__()
    serving = asyncio.create_task(
        f15.run_worker_process(
            "internal-restore",
            worker_stop,
            output / "recovery-worker.json",
            policy=TransactionalRiskPolicy(),
            manual_intake=True,
            protection_rounds=True,
            claim_limit=1,
            coordinate_claims=True,
            engine_factory=restored_worker_factory(engines),
        )
    )
    try:
        async with asyncio.timeout(60):
            while True:
                async with user_session(
                    engine, UUID(pending["owner"]), role=DatabaseRole.ENGINE
                ) as session:
                    restored_receipt = await get_request_by_key(
                        session, action="NEW", key=value.idempotency_key
                    )
                    assert (
                        restored_receipt is not None
                        and str(restored_receipt.request_id) == pending["receipt"]
                    )
                    await check_terminal_rejection(session, UUID(pending["receipt"]), output)
                    pending_groups = await groups(session, UUID(pending["episode"]), f15.PAIR)
                async with user_session(
                    engine, UUID(fixture["exiting"]["owner"]), role=DatabaseRole.ENGINE
                ) as session:
                    exiting = await load(session, UUID(fixture["exiting"]["group"]))
                async with user_session(
                    engine, UUID(retry["owner"]), role=DatabaseRole.ENGINE
                ) as session:
                    done = (
                        await session.execute(
                            "SELECT state FROM paper_protection_results WHERE request_id=:id",
                            {"id": request},
                        )
                    ).scalar_one_or_none()
                if (
                    len(pending_groups) == 1
                    and pending_groups[0].value.state is ProtectionState.ARMED
                    and exiting is not None
                    and exiting.value.state is ProtectionState.CLOSED
                    and done == "APPLIED"
                ):
                    break
                if serving.done():
                    await serving
                    raise RuntimeError("INTERNAL_RESTORE_WORKER_STOPPED")
                if publisher.done():
                    await publisher
                    raise RuntimeError("INTERNAL_RESTORE_PUBLISHER_STOPPED")
                await asyncio.sleep(0.05)
    finally:
        worker_stop.touch()
        try:
            await asyncio.wait_for(serving, 10)
        finally:
            rejection_observer.__exit__(None, None, None)
            stop.set()
            await publisher
    # Each closed group must still have one exit/two linked fills after retry.
    for name in ("closed", "exiting"):
        record = fixture[name]
        async with user_session(api, UUID(record["owner"])) as session:
            from tiewtrade.infra.paper_wallet import get_wallet

            wallet = await get_wallet(session)
            assert wallet is not None
        await verify_exit(
            engine, f15.OwnerState(UUID(record["owner"]), wallet), UUID(record["group"])
        )
    # The pending entry must have exactly one fill, and replay must not add financial effects.
    async with user_session(engine, UUID(pending["owner"]), role=DatabaseRole.ENGINE) as session:
        assert (
            await session.execute(
                "SELECT count(*) FROM paper_execution_links WHERE episode_id=:id",
                {"id": UUID(pending["episode"])},
            )
        ).scalar_one() == 1
    after = await restore.economic_digest(observer)
    assert before != after  # The staged pending entry/exit really completed.
    async with user_session(api, UUID(pending["owner"])) as session:
        replay = await admit_new_request(
            session,
            wallet_id=UUID(pending["wallet"]),
            intent=value,
            protection={"tp": "110", "sl": "90"},
        )
        assert str(replay.request_id) == pending["receipt"]
    async with user_session(engine, UUID(retry["owner"]), role=DatabaseRole.ENGINE) as session:
        await worker.process_request(session, request)
    assert await restore.economic_digest(observer) == after
    f15.save(
        output / "internal-recovery.json",
        {
            "status": "PASSED",
            "restored_owner_rls": True,
            "pending_receipt_identity": True,
            "exact_retry": True,
            "duplicate_exit_fill": 0,
        },
    )


async def recover_legacy_claims(
    admin: AsyncEngine, engine: AsyncEngine, scan: AsyncEngine
) -> dict[str, int]:
    """Recover exactly the expired legacy claims, leaving staged F16/F17 work intact."""
    from tiewtrade.infra.paper_orders.dispatch import DueOrder, claim_order
    from tiewtrade.infra.paper_orders.worker import process_claimed_order

    async with admin.connect() as connection:
        due = (
            (
                await connection.execute(
                    text("""SELECT command_id,user_id,next_attempt_at
            FROM paper_order_dispatch WHERE state='CLAIMED' AND lease_until<=clock_timestamp()
            ORDER BY command_id""")
                )
            )
            .mappings()
            .all()
        )
    async with internal.activated_protocols(admin, protections=True):
        for row in due:
            async with user_session(engine, row["user_id"], role=DatabaseRole.ENGINE) as session:
                claim = await claim_order(
                    session,
                    DueOrder(row["command_id"], row["user_id"], row["next_attempt_at"]),
                    worker="internal-restore-expired",
                )
            if claim is None:
                raise RuntimeError("INTERNAL_RESTORE_EXPIRED_CLAIM_NOT_RECOVERED")
            async with user_session(engine, row["user_id"], role=DatabaseRole.ENGINE) as session:
                await process_claimed_order(session, claim, policy=TransactionalRiskPolicy())
    async with admin.connect() as connection:
        after: int = (
            await connection.execute(
                text("""SELECT count(*) FROM paper_order_dispatch
            WHERE state='CLAIMED' AND lease_until<=clock_timestamp()""")
            )
        ).scalar_one()
    return {"expired_before": len(due), "expired_after": int(after), "rounds": len(due)}


async def verify(args: argparse.Namespace) -> int:
    guard_restore(args, dict(os.environ))
    fixture = json.loads((args.fixture / "internal-fixture.json").read_text())
    original_tables, original_security = restore.PAPER_TABLES, restore.security_shape

    async def security(engine: AsyncEngine) -> list[dict[str, object]]:
        return await original_security(engine) + await extension_security(engine)

    restore.PAPER_TABLES = (*original_tables, *TABLES)
    restore.security_shape = security
    try:
        result = await restore.run(args, recovery_hook=recover_legacy_claims)
    finally:
        restore.PAPER_TABLES, restore.security_shape = original_tables, original_security
    if result:
        return result
    base = json.loads((args.output / "result.json").read_text())
    f15.save(args.output / "result.json", {**base, "status": "PENDING_INTERNAL_RECOVERY"})
    engines = {
        role: create_async_engine(
            restore.database_url(os.environ[role.url_variable], args.target_database),
            hide_parameters=True,
        )
        for role in (
            DatabaseRole.API,
            DatabaseRole.ENGINE,
            DatabaseRole.ENGINE_SCAN,
            DatabaseRole.MIGRATOR,
            DatabaseRole.MARKET_DATA,
        )
    }
    observer = readonly_admin(source_variable=args.source_url_env, database=args.target_database)
    source_observer = readonly_admin(source_variable=args.source_url_env)
    try:
        source_before = await integrated_digest(source_observer)
        if source_before != base["source"]:
            raise RuntimeError("INTERNAL_RESTORE_SOURCE_CHANGED_BEFORE_RECOVERY")
        async with internal.activated_protocols(engines[DatabaseRole.MIGRATOR], protections=True):
            await recover(engines, fixture, args.output, observer=observer)
        source_unchanged = await integrated_digest(source_observer) == source_before
        f15.save(args.output / "source-unchanged.json", {"passed": source_unchanged})
        if not source_unchanged:
            raise RuntimeError("INTERNAL_RESTORE_SOURCE_CHANGED_DURING_RECOVERY")
        f15.save(
            args.output / "result.json",
            {**base, "status": "PASSED", "internal_recovery": "PASSED", "source_unchanged": True},
        )
    except BaseException as error:
        f15.save(
            args.output / "result.json",
            {**base, "status": "FAILED", "internal_recovery": type(error).__name__},
        )
        raise
    finally:
        await observer.dispose()
        await source_observer.dispose()
        for engine in engines.values():
            await engine.dispose()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "verify"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--source-url-env", default="TIEWTRADE_TEST_ADMIN_URL")
    parser.add_argument("--admin-url-env", default="TIEWTRADE_TEST_ADMIN_URL")
    parser.add_argument("--target-database")
    parser.add_argument("--postgres-container")
    args = parser.parse_args()
    if args.action == "verify" and (args.fixture is None or args.target_database is None):
        parser.error("verify requires fixture and target-database")
    from tests.infra.execution_market.profile_publisher_readiness import observe_publisher_readiness

    with observe_publisher_readiness(args.output / "publisher-readiness.json"):
        result = asyncio.run(build(args) if args.action == "build" else verify(args))
    raise SystemExit(result)
