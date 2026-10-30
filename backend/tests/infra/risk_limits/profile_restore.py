"""F18 W4: preserve F15 history, risk baselines, pending stops and risk requests.

Only isolated local tiewtrade_f18_release* databases are accepted. No Live capability.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from tests.infra.execution_market import profile_restore as restore
from tests.infra.execution_market import profile_restore_fixture as legacy
from tests.infra.execution_market import profile_workload as f15
from tests.infra.risk_limits.profile_observations import SOURCE_HZ
from tests.infra.risk_limits.profile_workload import (
    Fixture,
    guard_release_database,
    source_manifest,
)
from tiewtrade.core.money import Money
from tiewtrade.core.orders import OrderStatus, TradingMode
from tiewtrade.core.risk_limits import RiskScope
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.errors import NotPermittedError
from tiewtrade.infra.db.session import scan_session_bypassing_rls
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy
from tiewtrade.infra.risk_limits.records import RiskAction, RiskSubmission
from tiewtrade.infra.risk_limits.requests import receipt_by_key, submit_request
from tiewtrade.services.engine.paper_order import run_paper_order_round
from tiewtrade.services.engine.risk_limit import run_risk_request_round, run_risk_stop_round

RISK_TABLES = (
    "risk_protocol_control",
    "risk_price_publication",
    "market_price_feed",
    "market_latest_prices",
    "market_risk_price_frames",
    "risk_boundary_claims",
    "risk_financial_boundaries",
    "risk_owner_state",
    "risk_limit_authorizations",
    "risk_limit_requests",
    "risk_limit_results",
    "risk_limit_dispatch",
    "risk_limit_settings",
    "risk_limit_events",
    "risk_limit_baselines",
    "risk_limit_pairs",
    "risk_limit_evaluations",
    "risk_stop_requests",
    "risk_stop_progress",
    "risk_stop_targets",
    "risk_stop_effects",
    "risk_order_lifecycle",
    "risk_evaluation_requests",
    "risk_evaluation_results",
    "paper_order_requests",
    "paper_order_request_results",
    "paper_order_request_dispatch",
    "user_totp",
    "user_totp_pending",
)


def guard_admin(args: argparse.Namespace) -> None:
    expected = urlparse(os.environ[DatabaseRole.ENGINE.url_variable])
    for name in {args.admin_url_env, args.source_url_env}:
        value = urlparse(os.environ[name])
        if (value.hostname, value.port, value.path) != (
            expected.hostname,
            expected.port,
            expected.path,
        ):
            raise RuntimeError("F18_RESTORE_ADMIN_TARGET_MISMATCH")
    if args.postgres_container and not args.postgres_container.startswith("tiewtrade-f18-release"):
        raise RuntimeError("F18_RESTORE_CONTAINER_REJECTED")


async def build(args: argparse.Namespace) -> int:
    guard_release_database()
    guard_admin(args)
    output: Path = args.output
    output.mkdir(parents=True, exist_ok=False)
    check = create_engine_for(DatabaseRole.MIGRATOR)
    try:
        async with check.connect() as connection:
            enabled = bool(
                (
                    await connection.execute(
                        text("SELECT publication_enabled FROM risk_protocol_control")
                    )
                ).scalar_one()
            )
            if enabled:
                raise RuntimeError("F18_W4_REQUIRES_FRESH_PREACTIVATION_FIXTURE")
    finally:
        await check.dispose()
    # Preserve the real pre-rollout F15 restore fixture, including corrections,
    # episode closure and an expired claim. Only this pre-activation stage uses its policy.
    await legacy.run(argparse.Namespace(output=output / "legacy", admin_url_env=args.admin_url_env))
    legacy_fixture = json.loads((output / "legacy" / "fixture.json").read_text())
    ids = [UUID(item["user_id"]) for item in legacy_fixture["owners"]]
    assert ids
    risk_output = output / "risk"
    risk_output.mkdir()
    fixture = Fixture(risk_output)
    fixture.publisher_mode = getattr(args, "publisher_mode", "inline")
    try:
        async with fixture.migrator.begin() as connection:
            await connection.execute(
                text("""UPDATE risk_protocol_control SET
                publication_enabled=true,financial_enabled=true,admission_enabled=true""")
            )
        for owner_id in ids:
            async with user_session(fixture.api, owner_id) as session:
                wallet = await get_wallet(session)
                assert wallet is not None
                fixture.owners.append(f15.OwnerState(UUID(str(owner_id)), wallet))
        fixture.publisher = asyncio.create_task(fixture.publish())
        await fixture.spawn("risk")
        async with asyncio.timeout(20):
            while fixture.publisher_stats.get("published", 0) < 2:
                if fixture.publisher.done():
                    await fixture.publisher
                await asyncio.sleep(0.02)
        for owner in fixture.owners:
            await fixture.mutation(owner, RiskAction.SET, "1000")
            await fixture.mutation(owner, RiskAction.RESET)
        owner = (await f15.seed_owners(fixture.api, fixture.engine, fixture.scan, 1))[0]
        fixture.owners.append(owner)
        fixture.selected = owner.user_id
        fixture.partial_ready.set()
        async with user_session(fixture.api, owner.user_id) as session:
            await session.execute(
                "INSERT INTO user_trading_preferences(user_id,use) VALUES(:owner,'MANUAL')",
                {"owner": owner.user_id},
            )
        await fixture.mutation(owner, RiskAction.SET, "5")
        await fixture.mutation(owner, RiskAction.RESET)
        await fixture.spawn("paper-0")
        counters = f15.Counters()
        times: list[float] = []
        run_id = uuid4()
        for index in range(2):
            await fixture.new(
                fixture.engine,
                owner,
                f15.baseline(owner, run_id, index),
                OrderStatus.ACCEPTED,
                counters,
                times,
            )
        await fixture.new(
            fixture.engine,
            owner,
            f15.market_buy(owner, run_id, 0),
            OrderStatus.FILLED,
            counters,
            times,
        )
        await f15.stop_worker_processes(fixture.processes, fixture.stop)
        assert all(process.returncode == 0 for process in fixture.processes)
        fixture.processes.clear()
        fixture.stop.unlink()
        await fixture.spawn("risk", 1)
        await fixture.source_control(price="80")
        async with asyncio.timeout(30):
            while True:
                async with user_session(fixture.api, owner.user_id) as session:
                    state = (
                        await session.execute("""SELECT s.revision,s.latched,
                        p.stop_id,p.pending_count
                      FROM risk_limit_settings s JOIN risk_stop_requests r USING(user_id,mode)
                      JOIN risk_stop_progress p ON p.stop_id=r.id WHERE s.mode='PAPER'""")
                    ).one_or_none()
                if state is not None and state.latched and state.pending_count > 0:
                    break
                await asyncio.sleep(0.02)
        key = uuid4()
        scope = RiskScope(
            owner.user_id,
            TradingMode.PAPER,
            UUID(str(owner.wallet.wallet_id)),
            UUID(str(owner.wallet.episode_id)),
        )
        submission = RiskSubmission(
            scope, RiskAction.INCREASE, key, state.revision, Money.of(1000, "USDT")
        )
        async with user_session(fixture.api, owner.user_id) as session:
            receipt = await submit_request(session, submission)
            observed = await receipt_by_key(session, TradingMode.PAPER, key)
            assert observed == receipt and not observed.authorization_only
        # Adoption's real Paper worker may already have recovered the legacy
        # expired claim. Stage it again only after every consumer is stopped,
        # using the original fixture's real claim protocol rather than omitting
        # this required restore/recovery case.
        await f15.stop_worker_processes(fixture.processes, fixture.stop)
        assert all(process.returncode == 0 for process in fixture.processes)
        fixture.processes.clear()
        legacy_owner = UUID(legacy_fixture["owners"][2]["user_id"])
        await legacy.stage_expired_claim(
            fixture.engine,
            fixture.scan,
            next(item for item in fixture.owners if item.user_id == legacy_owner),
            os.environ[args.admin_url_env],
        )
        f15.save(
            output / "fixture.json",
            {
                "profile": "F18_W4_V1",
                "publisher_mode": fixture.publisher_mode,
                "source_target_hz": SOURCE_HZ,
                "source_tree_sha256": source_manifest()["source_tree_sha256"],
                "owner": str(owner.user_id),
                "stop_id": str(state.stop_id),
                "receipt_id": str(receipt.receipt_id),
                "key": str(key),
                "pending_count": state.pending_count,
                "scope": submission.payload(),
            },
        )
        return 0
    finally:
        await fixture.close()


async def extra_security(engine: AsyncEngine) -> list[dict[str, object]]:
    async with engine.connect() as connection:
        rows = (
            (
                await connection.exec_driver_sql("""SELECT c.relname table_name,c.relrowsecurity,
          c.relforcerowsecurity,c.relacl::text grants
          FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname='public' AND (c.relname LIKE 'risk_%' OR c.relname LIKE 'market_risk_%')
          AND c.relkind='r' ORDER BY c.relname""")
            )
            .mappings()
            .all()
        )
        functions = (
            (
                await connection.exec_driver_sql("""SELECT p.oid::regprocedure::text function_name,
          p.prosecdef,p.proacl::text grants,p.proconfig::text configuration FROM pg_proc p
          JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public'
          AND p.proname LIKE 'risk_%' ORDER BY p.oid::regprocedure::text""")
            )
            .mappings()
            .all()
        )
        columns = (
            (
                await connection.execute(
                    text("""
          SELECT c.relname AS table_name,a.attname AS column_name,
            pg_get_userbyid(x.grantor) AS grantor,
            CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END AS grantee,
            x.privilege_type,x.is_grantable
          FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
          JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
          CROSS JOIN LATERAL aclexplode(a.attacl) x
          WHERE n.nspname='public' AND c.relname=ANY(:tables)
          ORDER BY c.relname,a.attname,grantor,grantee,x.privilege_type,x.is_grantable
        """),
                    {"tables": sorted({*restore.PAPER_TABLES, *RISK_TABLES})},
                )
            )
            .mappings()
            .all()
        )
        policies = (
            (
                await connection.execute(
                    text("""
          SELECT tablename,policyname,permissive,roles,cmd,qual,with_check
          FROM pg_policies WHERE schemaname='public'
            AND tablename=ANY(:tables)
          ORDER BY tablename,policyname
        """),
                    {"tables": sorted({*restore.PAPER_TABLES, *RISK_TABLES})},
                )
            )
            .mappings()
            .all()
        )
        grants = (
            await connection.exec_driver_sql("""
          SELECT has_column_privilege('tiewtrade_engine_scan','risk_owner_state','cursor','SELECT')
            AND has_column_privilege(
              'tiewtrade_engine_scan','risk_price_publication','watermark','SELECT')
            AND NOT has_table_privilege('tiewtrade_engine_scan','risk_owner_state','SELECT')
            AND NOT has_column_privilege('tiewtrade_engine_scan','risk_owner_state','book','SELECT')
            AND NOT has_table_privilege('tiewtrade_engine_scan','risk_owner_state','UPDATE')
        """)
        ).scalar_one()
        if not grants:
            raise RuntimeError("F18_RESTORE_SCANNER_PRIVILEGES_INVALID")
    return [dict(row) for group in (rows, functions, columns, policies) for row in group]


async def verify_role_access(engines: dict[DatabaseRole, AsyncEngine], owner: UUID) -> None:
    for role in (DatabaseRole.API, DatabaseRole.ENGINE):
        async with user_session(engines[role], owner, role=role) as session:
            own = (
                await session.execute(
                    "SELECT count(*) FROM risk_limit_settings WHERE user_id=:owner",
                    {"owner": owner},
                )
            ).scalar_one()
            others = (
                await session.execute(
                    "SELECT count(*) FROM risk_limit_settings WHERE user_id<>:owner",
                    {"owner": owner},
                )
            ).scalar_one()
            if own == 0 or others != 0:
                raise RuntimeError("F18_RESTORE_OWNER_ISOLATION_FAILED")
    scan = engines[DatabaseRole.ENGINE_SCAN]
    async with scan_session_bypassing_rls(scan) as session:
        await session.execute("SELECT cursor FROM risk_owner_state LIMIT 1")
        await session.execute("SELECT watermark FROM risk_price_publication")
    for statement in (
        "SELECT book FROM risk_owner_state LIMIT 1",
        "SELECT payload FROM market_risk_price_frames LIMIT 1",
        "UPDATE risk_owner_state SET cursor=cursor WHERE false",
        "UPDATE risk_price_publication SET watermark=watermark WHERE false",
    ):
        try:
            async with scan_session_bypassing_rls(scan) as session:
                await session.execute(statement)
        except NotPermittedError:
            continue
        raise RuntimeError("F18_RESTORE_SCANNER_ACCESS_TOO_BROAD")


async def verify(args: argparse.Namespace) -> int:
    guard_release_database()
    guard_admin(args)
    if not args.target_database.startswith("tiewtrade_f18_release"):
        raise RuntimeError("F18_RESTORE_TARGET_REJECTED")
    fixture = json.loads(args.fixture.read_text())
    original_tables, original_security = restore.PAPER_TABLES, restore.security_shape

    async def security_shape(engine: AsyncEngine) -> list[dict[str, object]]:
        return await original_security(engine) + await extra_security(engine)

    restore.PAPER_TABLES = (*original_tables, *RISK_TABLES)
    restore.security_shape = security_shape
    try:
        result = await restore.run(args, recovery_policy=TransactionalRiskPolicy())
    finally:
        restore.PAPER_TABLES, restore.security_shape = original_tables, original_security
    if result:
        return result
    base_result = json.loads((args.output / "result.json").read_text())
    base_result["fixture_publisher_mode"] = fixture.get("publisher_mode", "inline")
    base_result["fixture_source_target_hz"] = fixture.get("source_target_hz")
    if base_result["status"] != "PASSED":
        raise RuntimeError("F18_RESTORE_BASE_VERDICT_REQUIRED")
    f15.save(
        args.output / "result.json",
        {**base_result, "status": "PENDING_RISK_RECOVERY", "base_restore_passed": True},
    )
    role_engines = {
        role: create_async_engine(
            restore.database_url(os.environ[role.url_variable], args.target_database),
            hide_parameters=True,
        )
        for role in (
            DatabaseRole.API,
            DatabaseRole.ENGINE,
            DatabaseRole.ENGINE_SCAN,
            DatabaseRole.MARKET_DATA,
        )
    }
    admin = create_async_engine(
        restore.database_url(os.environ[args.admin_url_env], args.target_database),
        hide_parameters=True,
    )
    try:
        owner, key, stop_id = UUID(fixture["owner"]), UUID(fixture["key"]), UUID(fixture["stop_id"])
        await verify_role_access(role_engines, owner)
        before = await restore.economic_digest(admin)
        baseline_before = await restore.table_digest(admin, "risk_limit_baselines")
        async with user_session(role_engines[DatabaseRole.API], owner) as session:
            receipt = await receipt_by_key(session, TradingMode.PAPER, key)
            assert (
                receipt is not None
                and not receipt.authorization_only
                and str(receipt.receipt_id) == fixture["receipt_id"]
            )
            first = await submit_request(session, receipt.submission)
            assert await submit_request(session, receipt.submission) == first
        market = role_engines[DatabaseRole.MARKET_DATA]
        book, price = await f15.acquire_sources(market)
        await f15.publish_market(market, book, price, rebase=True, trade_id=1)
        await run_risk_request_round(
            engine=role_engines[DatabaseRole.ENGINE],
            scan_engine=role_engines[DatabaseRole.ENGINE_SCAN],
            worker="w4-authorized-recovery",
        )
        async with asyncio.timeout(15):
            while True:
                await run_risk_stop_round(
                    engine=role_engines[DatabaseRole.ENGINE],
                    scan_engine=role_engines[DatabaseRole.ENGINE_SCAN],
                )
                await run_paper_order_round(
                    engine=role_engines[DatabaseRole.ENGINE],
                    scan_engine=role_engines[DatabaseRole.ENGINE_SCAN],
                    worker="w4-real-risk-cancel",
                    policy=TransactionalRiskPolicy(),
                )
                async with user_session(role_engines[DatabaseRole.API], owner) as session:
                    pending = (
                        await session.execute(
                            "SELECT pending_count FROM risk_stop_progress WHERE stop_id=:id",
                            {"id": stop_id},
                        )
                    ).scalar_one()
                if pending == 0:
                    break
                await asyncio.sleep(0.02)
        # Replay the actual consumers after completion, then prove each target
        # still has exactly one durable terminal state/effect.
        await run_risk_stop_round(
            engine=role_engines[DatabaseRole.ENGINE],
            scan_engine=role_engines[DatabaseRole.ENGINE_SCAN],
        )
        await run_paper_order_round(
            engine=role_engines[DatabaseRole.ENGINE],
            scan_engine=role_engines[DatabaseRole.ENGINE_SCAN],
            worker="w4-cancel-retry",
            policy=TransactionalRiskPolicy(),
        )
        async with user_session(role_engines[DatabaseRole.API], owner) as session:
            progress = (
                await session.execute(
                    "SELECT * FROM risk_stop_progress WHERE stop_id=:id", {"id": stop_id}
                )
            ).one()
            assert progress.target_set_complete and progress.pending_count == 0
            setting = (
                await session.execute(
                    "SELECT amount,latched FROM risk_limit_settings WHERE mode='PAPER'"
                )
            ).one()
            assert setting.latched and Money.of(setting.amount, "USDT") == Money.of(1000, "USDT")
            assert (
                await session.execute(
                    "SELECT state FROM risk_limit_results WHERE request_id=:id",
                    {"id": first.receipt_id},
                )
            ).scalar_one() == "APPLIED"
            assert (
                await session.execute(
                    "SELECT count(*) FROM risk_limit_requests WHERE idempotency_key=:key",
                    {"key": key},
                )
            ).scalar_one() == 1
        # Immutable order events are ENGINE reads, not part of the API role's
        # contract. Verify internal financial effects without broadening grants.
        async with user_session(
            role_engines[DatabaseRole.ENGINE], owner, role=DatabaseRole.ENGINE
        ) as session:
            cancel_counts = (
                await session.execute(
                    """SELECT count(*) events,count(DISTINCT t.order_id) orders
              FROM risk_stop_targets t JOIN paper_orders o ON o.id=t.order_id
              JOIN paper_order_events e ON e.episode_id=o.episode_id
                AND e.base=o.base AND e.quote=o.quote
              CROSS JOIN LATERAL jsonb_array_elements(e.payload->'terminal_orders') terminal(value)
              WHERE t.stop_id=:stop AND terminal.value->>'status'='CANCELED'
                AND terminal.value->'intent'->>'order_id'=t.order_id::text""",
                    {"stop": stop_id},
                )
            ).one()
            assert cancel_counts.events == cancel_counts.orders == progress.target_count
            assert (
                await session.execute(
                    """SELECT count(*) FROM risk_stop_effects
                    WHERE stop_id=:stop AND state='CANCELED'""",
                    {"stop": stop_id},
                )
            ).scalar_one() == progress.target_count
            assert (
                await session.execute(
                    """SELECT coalesce(sum(quote_reserved),0) FROM paper_reservations
              WHERE order_id IN (SELECT order_id FROM risk_stop_targets WHERE stop_id=:stop)""",
                    {"stop": stop_id},
                )
            ).scalar_one() == 0
        assert await restore.economic_digest(admin) == before
        assert await restore.table_digest(admin, "risk_limit_baselines") == baseline_before
        f15.save(
            args.output / "risk-recovery.json",
            {
                "status": "PASSED",
                "real_risk_policy": True,
                "paper_request_exact_retry": True,
                "pending_stop_completed": True,
                "terminal_cancel_states": cancel_counts.events,
                "duplicate_cancel_effects": 0,
                "financial_facts_unchanged": True,
                "reset_baselines_unchanged": True,
            },
        )
        f15.save(
            args.output / "result.json",
            {
                **base_result,
                "status": "PASSED",
                "base_restore_passed": True,
                "risk_recovery_passed": True,
                "restored_role_access_passed": True,
            },
        )
        return 0
    except BaseException as error:
        f15.save(
            args.output / "result.json",
            {
                **base_result,
                "status": "FAILED",
                "base_restore_passed": True,
                "risk_recovery_passed": False,
                "error_type": type(error).__name__,
            },
        )
        raise
    finally:
        for engine in role_engines.values():
            await engine.dispose()
        await admin.dispose()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "verify"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--source-url-env", default="TIEWTRADE_TEST_ADMIN_URL")
    parser.add_argument("--admin-url-env", default="TIEWTRADE_TEST_ADMIN_URL")
    parser.add_argument("--target-database")
    parser.add_argument("--postgres-container")
    parser.add_argument(
        "--publisher-mode",
        choices=("inline", "child"),
        default="inline",
        help="Build mode; verify uses the captured fixture mode",
    )
    args = parser.parse_args()
    if args.action == "verify" and (args.fixture is None or not args.target_database):
        parser.error("verify requires fixture and target-database")
    return asyncio.run(build(args) if args.action == "build" else verify(args))


if __name__ == "__main__":
    raise SystemExit(main())
