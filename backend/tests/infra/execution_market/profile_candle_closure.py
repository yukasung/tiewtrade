"""One authorized public-source Paper campaign. Never imported by production.

Run only in a new tiewtrade_e2e_closure_campaign_* database. The exclusive report
file is the attempt marker; a failed/partial run cannot silently restart it.
The profile selects BTC/ETH1m, uses real public adapters, and never seeds prices,
CLOSED candles, strategy state, execution facts or recovery/entry cutoffs.
"""

import argparse
import asyncio
import json
import os
import secrets
import traceback
from contextlib import AsyncExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from tests.infra.positions.conftest import create_production_wallet
from tests.infra.risk_limits.test_requests import submission
from tiewtrade.core.indicators import FORMULA_VERSION
from tiewtrade.core.market_data import Timeframe, initial_window
from tiewtrade.core.order_book import BookState
from tiewtrade.core.orders import OrderError
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.realtime_prices import Readiness, readiness
from tiewtrade.core.strategy_config import PAPER_TEST_STRATEGY, STRATEGY_NAME
from tiewtrade.infra.db import DatabaseRole, InfraError, create_engine_for, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.indicators.pinned import pinned_indicator_writer
from tiewtrade.infra.indicators.prepared import fresh_proof_valid, read_generation_authority
from tiewtrade.infra.indicators.scheduling import POLL_SECONDS, coalesce_jobs
from tiewtrade.infra.market_data.candle_closure import connection_ready
from tiewtrade.infra.market_data.order_book_storage import read_latest_book
from tiewtrade.infra.market_data.realtime_storage import read_snapshot
from tiewtrade.infra.realtime.notifications import RedisNotifications
from tiewtrade.infra.risk_limits.requests import submit_request
from tiewtrade.services.api.app import app, lifespan
from tiewtrade.services.api.bot_models import (
    PaperTestConfigurationInput,
    StrategyConfigurationInput,
)
from tiewtrade.services.api.settings import CSRF_COOKIE, CSRF_HEADER
from tiewtrade.services.engine.bot import StrategyRegistry, run_bot_worker_round
from tiewtrade.services.engine.paper_order_main import serve as orders
from tiewtrade.services.engine.risk_limit import run_risk_request_round
from tiewtrade.services.engine.risk_limit_main import serve as risk
from tiewtrade.services.indicator_builder.attempt import AttemptStatus, run_attempt
from tiewtrade.services.market_data.candle_realtime import CandleSupervisor
from tiewtrade.services.market_data.ingestion import MARKET_TIMEOUT, run_round
from tiewtrade.services.market_data.order_book import ExecutionBookSupervisor
from tiewtrade.services.market_data.realtime import QuoteSupervisor
from tiewtrade.venues import (
    live_candle_feed,
    live_candle_source,
    live_execution_feed,
    live_price_feed,
    public_rate_limit_guard,
)


def now() -> datetime:
    return datetime.now(UTC)


class ProfileCandles(CandleSupervisor):
    async def _reload_catalog(self) -> None:
        await super()._reload_catalog()
        if set(self.catalog) != {("BTC", "USDT"), ("ETH", "USDT")}:
            raise RuntimeError("campaign requires the initial BTC/ETH catalog")
        self.series = tuple(s for s in self.series if s.timeframe is Timeframe.M1)


def guard() -> None:
    names = {
        make_url(value).database
        for key, value in os.environ.items()
        if key.startswith("TIEWTRADE_DATABASE_URL_") or key == "TIEWTRADE_TEST_ADMIN_URL"
    }
    if len(names) != 1 or not all(
        name is not None and name.startswith("tiewtrade_e2e_closure_campaign_") for name in names
    ):
        raise RuntimeError("fresh owned closure campaign database required")
    if os.environ.get("TIEWTRADE_CANDLE_CLOSURE_ENABLED") != "1":
        raise RuntimeError("compatible source writer must be explicitly enabled")
    if make_url(os.environ["TIEWTRADE_TEST_ADMIN_URL"]).host not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise RuntimeError("local owned campaign audit database required")


def configuration_payload(base: str, strategy: str) -> dict[str, Any]:
    fields: dict[str, Any] = {"base": base, "timeframe": "1m", "capital_per_entry": "100"}
    if strategy == PAPER_TEST_STRATEGY:
        return PaperTestConfigurationInput.model_validate(
            fields | {"strategy_name": strategy}
        ).model_dump(mode="json")
    if strategy == STRATEGY_NAME:
        return StrategyConfigurationInput.model_validate(fields | {"max_entries": 1}).model_dump(
            mode="json"
        )
    raise ValueError("unsupported campaign strategy")


class ApiRejectedError(RuntimeError):
    def __init__(self, path: str, status: int) -> None:
        super().__init__("campaign API rejected")
        self.path = path
        self.status = status


async def request(client: httpx.AsyncClient, path: str, body: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(
        path,
        json=body,
        headers={
            CSRF_HEADER: str(client.cookies.get(CSRF_COOKIE, "")),
            "Idempotency-Key": str(uuid4()),
        },
    )
    if response.status_code not in (200, 201, 202):
        raise ApiRejectedError(path, response.status_code)
    return dict(response.json())


async def fresh_heads(api: AsyncEngine) -> bool:
    async with user_session(api, UUID(int=1)) as session:
        for base in ("BTC", "ETH"):
            head, failure = await read_generation_authority(
                session, base, "USDT", Timeframe.M1, FORMULA_VERSION
            )
            if (
                head is None
                or failure is not None
                or not await fresh_proof_valid(session, head, now())
            ):
                return False
    return True


async def prepare_heads(builder: AsyncEngine, api: AsyncEngine, report: dict[str, Any]) -> None:
    """Eligibility, cooldown and retry authority stay in the existing DB scheduler."""
    owner = uuid4()
    report.setdefault("builds", [])
    while not await fresh_heads(api):
        await coalesce_jobs(builder)
        built = await run_attempt(builder, owner)
        report["builds"].append(built.status.value)
        if built.status in (AttemptStatus.ORPHANED, AttemptStatus.FAILED_NUMERIC):
            raise RuntimeError("actual-source F11 preparation requires recovery")
        if built.status in (AttemptStatus.NO_JOB, AttemptStatus.LOCK_BUSY):
            await asyncio.sleep(POLL_SECONDS)


async def trading_sources_ready(market: AsyncEngine) -> bool:
    async with market_data_session(market) as session:
        snapshot = await read_snapshot(session)
        feed = snapshot.feed
        if feed is None or not feed.connected or feed.lease_until <= snapshot.server_time:
            return False
        for base in ("BTC", "ETH"):
            row = next((row for row in snapshot.rows if row.base == base), None)
            if (
                row is None
                or readiness(
                    quote=row.observation,
                    connected=feed.connected,
                    reconciled=(
                        row.reconciled_generation == feed.generation
                        and row.effective_readiness == "READY"
                    ),
                    producer_alive=feed.lease_until > snapshot.server_time,
                    now=snapshot.server_time,
                )
                is not Readiness.READY
            ):
                return False
            try:
                book = await read_latest_book(session, PositionPair(base, "USDT"))
                if not isinstance(book.market, BookState):
                    return False
                book.market.require_ready(now())
            except (InfraError, OrderError):
                return False
        return await connection_ready(session)


async def campaign(report: dict[str, Any]) -> None:
    guard()
    roles = (
        DatabaseRole.MIGRATOR,
        DatabaseRole.MARKET_DATA,
        DatabaseRole.ENGINE,
        DatabaseRole.ENGINE_SCAN,
        DatabaseRole.API,
        DatabaseRole.INDICATOR_BUILDER,
    )
    engines = {role: create_engine_for(role) for role in roles}
    admin, market, engine, scan, api, builder = (engines[role] for role in roles)
    audit = create_async_engine(
        os.environ["TIEWTRADE_TEST_ADMIN_URL"],
        hide_parameters=True,
        execution_options={"postgresql_readonly": True},
    )
    tasks: list[asyncio.Task[None]] = []
    try:
        async with audit.connect() as conn:
            if (await conn.execute(text("SELECT count(*) FROM users"))).scalar_one() != 0:
                raise RuntimeError("campaign database must have no existing users")
        async with admin.begin() as conn:
            await conn.execute(text("SELECT activate_indicator_source_proof()"))
            await conn.execute(
                text("""UPDATE indicator_rollout_control SET mode='PREPARING',
                codec_version=2,protocol_version=1,retention_policy='GRACE'""")
            )
            await conn.execute(
                text("""UPDATE risk_protocol_control SET publication_enabled=true,
                financial_enabled=true,admission_enabled=true""")
            )
            await conn.execute(text("UPDATE paper_protection_protocol SET enabled=true"))
            # Keep non-profile series explicitly unavailable, never pretend history exists.
            for base in ("BTC", "ETH"):
                for tf in Timeframe:
                    window = initial_window(tf, now())
                    await conn.execute(
                        text("""INSERT INTO market_candle_demand
                        (source,base,quote,timeframe,desired_start,desired_end,requested_at,
                         status,checked_at,next_attempt_at)
                        VALUES('primary_spot',:base,'USDT',:tf,:lo,:hi,clock_timestamp(),
                         :status,clock_timestamp(),:due)"""),
                        {
                            "base": base,
                            "tf": tf.value,
                            "lo": window.start,
                            "hi": window.end,
                            "status": "PENDING" if tf is Timeframe.M1 else "UNAVAILABLE",
                            "due": now() if tf is Timeframe.M1 else now() + timedelta(days=1),
                        },
                    )
        async with AsyncExitStack() as stack:
            public = await stack.enter_async_context(httpx.AsyncClient())
            redis = Redis.from_url(os.environ["TIEWTRADE_REDIS_URL_MARKET_DATA"])
            stack.push_async_callback(redis.aclose)
            limiter = public_rate_limit_guard(clock=now)
            candles = live_candle_source(
                client=public, clock=now, timeout=MARKET_TIMEOUT, guard=limiter
            )
            notifications = RedisNotifications(redis)
            supervisors = (
                ProfileCandles(market, live_candle_feed(clock=now), notifications),
                QuoteSupervisor(
                    market,
                    live_price_feed(
                        client=public, clock=now, timeout=MARKET_TIMEOUT, guard=limiter
                    ),
                    notifications,
                ),
                ExecutionBookSupervisor(
                    market,
                    live_execution_feed(
                        client=public, clock=now, timeout=MARKET_TIMEOUT, guard=limiter
                    ),
                ),
            )

            async def ingest() -> None:
                while True:
                    await run_round(market, candles, "owned-closure-campaign", now())
                    await asyncio.sleep(30)

            tasks.extend(asyncio.create_task(s.run()) for s in supervisors)
            tasks.append(asyncio.create_task(ingest()))
            report["boot_started_at"] = now().isoformat()
            report["phase"] = "PUBLIC_BOOT"
            # Boot is bounded separately; no warm-up fixture or synthetic source fallback.
            preparation_deadline = asyncio.get_running_loop().time() + 300
            async with asyncio.timeout_at(preparation_deadline):
                while True:
                    for task in tasks:
                        if task.done():
                            task.result()
                            raise RuntimeError("public source ended during boot")
                    async with market_data_session(market) as session:
                        counts = (
                            (
                                await session.execute("""SELECT base,count(*) AS total
                            FROM market_candles
                            WHERE timeframe='1m' AND fetch_started_at>=end_at GROUP BY base""")
                            )
                            .mappings()
                            .all()
                        )
                        ready = await connection_ready(session)
                    if len(counts) == 2 and all(row["total"] >= 250 for row in counts) and ready:
                        break
                    await asyncio.sleep(1)
            async with asyncio.timeout_at(preparation_deadline):
                async with pinned_indicator_writer(builder, connection_mode="direct") as writer:
                    if writer is None:
                        raise RuntimeError("owned builder lock unavailable")
                    await writer.seed()
                async with admin.begin() as conn:
                    await conn.execute(
                        text("""UPDATE indicator_build_jobs SET retry_not_before=
                        clock_timestamp()+interval '1 day' WHERE timeframe<>'1m'""")
                    )
                report["phase"] = "ACTUAL_F11_BUILD"
                while True:
                    report["phase"] = "ACTUAL_F11_BUILD"
                    await prepare_heads(builder, api, report)
                    report["phase"] = "TRADING_SOURCE_PREFLIGHT"
                    if await trading_sources_ready(market):
                        break
                    for task in tasks:
                        if task.done():
                            task.result()
                            raise RuntimeError("public source ended during preflight")
                    await asyncio.sleep(1)
            async with admin.begin() as conn:
                await conn.execute(text("UPDATE indicator_rollout_control SET mode='PREPARED'"))
                inventory = {
                    "legacy_writers_drained": True,
                    "legacy_restart_disabled": True,
                    "readers_compatible": True,
                    "paper_only": True,
                    "candidate_sha": report["candidate_fingerprint"],
                }
                await conn.execute(
                    text("SELECT activate_candle_closure(true,CAST(:i AS jsonb))"),
                    {"i": json.dumps(inventory)},
                )
            report["phase"] = "OWNED_API_SETUP"
            os.environ["TIEWTRADE_SIGNUP_OPEN"] = "1"
            os.environ["TIEWTRADE_COOKIE_SECURE"] = "0"
            os.environ["TIEWTRADE_PRICE_ORIGINS"] = "http://localhost:5173"
            await stack.enter_async_context(lifespan(app))
            app.state.bot_f21_enabled = True
            app.state.paper_test_strategy_enabled = True
            clients = []
            for base, strategy in (("BTC", PAPER_TEST_STRATEGY), ("ETH", STRATEGY_NAME)):
                client = await stack.enter_async_context(
                    httpx.AsyncClient(
                        transport=httpx.ASGITransport(app=app), base_url="http://localhost:5173"
                    )
                )
                await client.get("/auth/csrf")
                await request(
                    client,
                    "/auth/register",
                    {
                        "email": f"closure-{uuid4().hex}@example.com",
                        "password": secrets.token_urlsafe(32),
                    },
                )
                identity = UUID((await client.get("/auth/me")).json()["user_id"])
                await request(client, "/trading-account/use", {"use": "BOT"})
                wallet = await create_production_wallet(api, engine, scan, identity)
                async with user_session(api, identity) as owned_session:
                    await submit_request(owned_session, submission(identity, wallet))
                await run_risk_request_round(
                    engine=engine, scan_engine=scan, worker="closure-profile"
                )
                configuration = await request(
                    client, "/paper/bots/configurations", configuration_payload(base, strategy)
                )
                clients.append((client, configuration["reference"]))
            registry = StrategyRegistry(enable_f21=True, enable_paper_test=True)

            async def bots() -> None:
                cursor = None
                worker = uuid4()
                while True:
                    result = await run_bot_worker_round(
                        engine=engine,
                        scan_engine=scan,
                        registry=registry,
                        cursor=cursor,
                        worker_id=worker,
                    )
                    cursor = result.next_cursor
                    await asyncio.sleep(0.5)

            tasks.extend(asyncio.create_task(fn()) for fn in (orders, risk, bots))
            report["phase"] = "CAMPAIGN"
            report["campaign_started_at"] = now().isoformat()
            deadline = asyncio.get_running_loop().time() + 360
            for client, reference in clients:
                await request(client, "/paper/bots/requests", {"strategy_config_ref": reference})
            while asyncio.get_running_loop().time() < deadline:
                for task in tasks:
                    if task.done():
                        task.result()
                        raise RuntimeError("campaign service ended")
                await asyncio.sleep(min(1, max(0, deadline - asyncio.get_running_loop().time())))
            report["api_status"] = [(await c.get("/paper/bots/status")).json() for c, _ in clients]
            # Cancel producers/workers before closing API pools and capture facts in finally.
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        report["stopped_at"] = now().isoformat()
        try:
            await capture_evidence(audit, report)
        finally:
            for pool in (*engines.values(), audit):
                await pool.dispose()


async def capture_evidence(audit: AsyncEngine, report: dict[str, Any]) -> None:
    """Read owned test facts without mistaking FORCE RLS filtering for no activity."""
    async with audit.connect() as conn:
        for name, sql in {
            "users": "SELECT id FROM users",
            "wallets": "SELECT id,user_id FROM paper_wallets",
            "runs": "SELECT id,strategy_name,status FROM bot_runs",
            "build_jobs": "SELECT base,timeframe,status,attempts_used,failure_reason, "
            "failure_category,availability_deadline,retry_not_before "
            "FROM indicator_build_jobs WHERE timeframe='1m'",
            "execution_sources": "SELECT base,ready,failure_code,generation,last_input_id, "
            "received_at,verified_at FROM market_execution_state",
            "closure_states": "SELECT * FROM market_candle_closure_state",
            "closure_results": "SELECT * FROM market_candle_closure_results",
            "closure_observations": "SELECT * FROM market_candle_closure_observations",
            "decisions": "SELECT d.id,r.strategy_name,d.input_provenance, "
            "d.state_before,d.state_after "
            "FROM bot_decisions d JOIN bot_runs r ON r.id=d.run_id",
            "links": "SELECT * FROM bot_order_links",
            "canonical": "SELECT c.* FROM market_candles c JOIN market_candle_closure_state s "
            "USING(source,base,quote,timeframe,open_at)",
            "ledger": "SELECT * FROM paper_wallet_ledger",
            "executions": "SELECT * FROM paper_execution_links",
            "orders": "SELECT * FROM paper_order_projections",
            "positions": "SELECT * FROM paper_position_projections",
            "reservations": "SELECT * FROM paper_reservations",
            "anchors": "SELECT * FROM bot_test_entry_anchors",
        }.items():
            report[name] = [dict(row) for row in (await conn.execute(text(sql))).mappings()]


def _failure_frames(error: BaseException) -> list[dict[str, str | int | None]]:
    return [
        {"file": Path(frame.filename).name, "function": frame.name, "line": frame.lineno}
        for frame in traceback.extract_tb(error.__traceback__, limit=-16)
    ]


def _failure_tree(error: BaseException) -> dict[str, Any]:
    """Bound diagnostic metadata; never render exception text or chained context."""
    nodes: list[dict[str, Any]] = []
    truncated = False

    def visit(current: BaseException, path: tuple[int, ...]) -> None:
        nonlocal truncated
        frames_truncated = len(traceback.extract_tb(current.__traceback__, limit=17)) > 16
        truncated |= frames_truncated
        nodes.append(
            {
                "path": path,
                "type": type(current).__name__,
                "frames": _failure_frames(current),
                "frames_truncated": frames_truncated,
            }
        )
        if isinstance(current, BaseExceptionGroup):
            if len(path) >= 8:
                truncated = True
                return
            for index, child in enumerate(current.exceptions):
                if len(nodes) >= 32:
                    truncated = True
                    break
                visit(child, (*path, index))

    visit(error, ())
    return {"nodes": nodes, "truncated": truncated}


async def main(output: Path, fingerprint: str) -> None:
    guard()
    if len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
        raise ValueError("reviewed candidate SHA256 required")
    with output.open("x") as destination:
        report: dict[str, Any] = {"candidate_fingerprint": fingerprint, "result": "INCOMPLETE"}
        destination.write(json.dumps(report))
        destination.flush()
        try:
            await campaign(report)
            filled = {
                row["order_id"] for row in report.get("orders", []) if row["status"] == "FILLED"
            }
            anchors = {row["order_id"] for row in report.get("anchors", []) if row["execution_id"]}
            proofs = {
                str(row["id"])
                for row in report.get("closure_results", [])
                if row["outcome"] == "MATCHED"
            }
            decisions = {
                row["id"]
                for row in report.get("decisions", [])
                if row["strategy_name"] == PAPER_TEST_STRATEGY
                and row["input_provenance"].get("closure_proof_id") in proofs
            }
            linked = {
                row["order_id"]
                for row in report.get("links", [])
                if row["decision_id"] in decisions
            }
            report["result"] = "PASSED" if filled & anchors & linked else "PARTIAL"
        except Exception as error:
            report["result"], report["failure_type"] = "PARTIAL", type(error).__name__
            report["failure_frames"] = _failure_frames(error)
            report["failure_tree"] = _failure_tree(error)
            if isinstance(error, ApiRejectedError):
                report["api_rejection"] = {"path": error.path, "status": error.status}
        finally:
            destination.seek(0)
            destination.truncate()
            destination.write(json.dumps(report, default=str, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-fingerprint", required=True)
    args = parser.parse_args()
    asyncio.run(main(args.output, args.candidate_fingerprint))
