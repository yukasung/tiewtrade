"""Real-worker preflight for the approved Set-5 source and restore changes."""

import asyncio
import json
import os
from dataclasses import replace
from pathlib import Path
from time import monotonic
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from tests.infra.execution_market import profile_workload as f15
from tests.infra.risk_limits import profile_stop_restore
from tests.infra.risk_limits.profile_resets import run_scheduled_work
from tests.infra.risk_limits.profile_risk_timing import collect_commits
from tests.infra.risk_limits.profile_stop_runtime import UserStopScheduleRunner
from tests.infra.risk_limits.profile_stop_schedule import build_stop_schedule
from tests.infra.risk_limits.profile_workload import Fixture
from tests.infra.risk_limits.test_prices import publication as publication
from tests.infra.risk_limits.test_publisher_process import wait_publications
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import BaseSize, OrderOrigin, OrderStatus, OrderType, TimeInForce
from tiewtrade.core.trading_stops import StopAction
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_orders.matching_storage import load_order_state
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.positions import read_position_snapshot
from tiewtrade.infra.risk_limits.records import RiskAction
from tiewtrade.infra.trading_stops import receipt_by_id as stop_receipt
from tiewtrade.infra.trading_stops import submit_request as submit_stop
from tiewtrade.services.engine.kill_switch import run_stop_request_round

pytestmark = pytest.mark.fresh_global_state


@pytest.mark.parametrize("coordinated,risk_observer", [(False, False), (True, False), (True, True)])
async def test_one_shot_real_workers_preserve_overlapping_core_and_stop_financials(
    tmp_path: Path,
    publication: AsyncEngine,
    coordinated: bool,
    risk_observer: bool,
) -> None:
    fixture = Fixture(tmp_path)
    fixture.publisher_mode = "child"
    fixture.partial_barrier_enabled = coordinated
    fixture.risk_diagnostic = risk_observer
    try:
        async with fixture.migrator.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE risk_protocol_control SET publication_enabled=true,"
                    "financial_enabled=true,admission_enabled=true"
                )
            )
        fixture.owners = await f15.seed_owners(fixture.api, fixture.engine, fixture.scan, 3)
        dedicated, core_buy, core_sell = fixture.owners
        for owner in fixture.owners:
            async with user_session(fixture.api, owner.user_id) as session:
                await session.execute(
                    "INSERT INTO user_trading_preferences(user_id,use) VALUES(:id,:use)",
                    {"id": owner.user_id, "use": "BOT" if owner is dedicated else "MANUAL"},
                )
        fixture.publisher = asyncio.create_task(fixture.publish())
        if risk_observer:
            (tmp_path / "risk-trace-control.json").write_text(
                json.dumps({"started": monotonic(), "seconds": 300})
            )
            fixture.commit_collector_task = asyncio.create_task(
                collect_commits(fixture.migrator, tmp_path, fixture.commit_collector_stop)
            )
        await wait_publications(fixture, 2)
        await fixture.spawn("risk")
        await fixture.spawn("paper-0")
        await fixture.spawn("paper-1")
        for owner in fixture.owners:
            await fixture.mutation(owner, RiskAction.SET, "1000")
        run_id = uuid4()
        counters = f15.Counters()
        await fixture.request(
            core_sell, f15.market_buy(core_sell, run_id, 0), expected_status=OrderStatus.FILLED
        )
        intent = replace(
            f15.market_buy(dedicated, run_id, 0),
            origin=OrderOrigin.BOT,
            kind=OrderType.LIMIT,
            size=BaseSize(Quantity.of(1, "BTC")),
            limit_price=Money.of(2, "USDT"),
            time_in_force=TimeInForce.GTC,
        )
        await fixture.submit_setup_order_when_ready(
            dedicated,
            lambda: f15.submit_new(
                fixture.engine,
                dedicated,
                intent,
                OrderStatus.ACCEPTED,
                counters,
                [],
            ),
        )
        await fixture.wait_one_shot_resting(dedicated, intent.order_id)
        if coordinated:
            # Leave a naturally stale cursor using real process termination. No worker
            # decision is replaced, and the publisher/risk worker continue normally.
            for process in fixture.processes[1:]:
                process.terminate()
                await process.wait()
            await asyncio.sleep(1.2)
            await fixture.prepare_partial_delivery(
                dedicated, intent.order_id, run_id, deadline=monotonic() + 20
            )

        async def restart_after_arm() -> None:
            if coordinated:
                async with asyncio.timeout(5):
                    while not fixture.partial_barrier.control.exists():
                        await asyncio.sleep(0)
                await fixture.spawn("paper-0", 1)
                await fixture.spawn("paper-1", 1)

        async with fixture.scheduled_partial_trade() as (inject, clear):
            await run_scheduled_work(
                inject(),
                fixture.request(
                    core_buy,
                    f15.market_buy(core_buy, run_id, 1),
                    expected_status=OrderStatus.FILLED,
                ),
                restart_after_arm(),
                fixture.request(
                    core_sell,
                    f15.market_sell(core_sell, run_id, 1),
                    expected_status=OrderStatus.FILLED,
                ),
            )
            await f15.wait_status(
                fixture.engine, dedicated.user_id, intent.order_id, OrderStatus.PARTIALLY_FILLED
            )
            runner = UserStopScheduleRunner(
                api_engine=fixture.api,
                schedule=build_stop_schedule("W1", [dedicated.user_id, core_buy.user_id]),
                owners=[dedicated, core_buy],
                journal=tmp_path / "stop-schedule.jsonl",
            )
            await runner._stop(dedicated, "partial-preflight")
            await runner._ready(dedicated)
            await clear()
            await runner._resume(dedicated)
        await wait_publications(fixture, int(fixture.publisher_stats["price_published"]) + 2)
        async with user_session(
            fixture.engine, dedicated.user_id, role=DatabaseRole.ENGINE
        ) as session:
            result = await load_order_state(session, intent.order_id)
            assert result.status is OrderStatus.CANCELED
            assert result.filled == Quantity.of("0.5", "BTC") and result.spent == Money.of(
                1, "USDT"
            )
            row = (
                await session.execute(
                    "SELECT quote_reserved,base_reserved FROM paper_reservations "
                    "WHERE order_id=:id",
                    {"id": intent.order_id},
                )
            ).one()
            assert row.quote_reserved == row.base_reserved == 0
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_order_events "
                    "WHERE order_id=:id AND event_kind='FILL'",
                    {"id": intent.order_id},
                )
            ).scalar_one() == 1
            wallet = await get_wallet(session)
            assert wallet is not None and wallet.balance == Money.of(9999, "USDT")
            position = await read_position_snapshot(session, dedicated.wallet.episode_id)
            assert position is not None and len(position.positions) == 1
            assert position.positions[0].held_quantity == Quantity.of("0.4995", "BTC")
            assert position.positions[0].total_cost == Money.of(1, "USDT")
        assert len(fixture.one_shot_receipts) == 1
        if coordinated:
            receipt = next(iter(fixture.one_shot_receipts.values()))
            async with user_session(
                fixture.engine, dedicated.user_id, role=DatabaseRole.ENGINE
            ) as session:
                assert (
                    await session.execute(
                        "SELECT count(*) FROM paper_execution_inputs "
                        "WHERE input_id=:input AND payload#>>'{market,kind}'='TRADE'",
                        {"input": receipt["input_id"]},
                    )
                ).scalar_one() == 1
        assert fixture.publisher_stats["last_ask_quantity"] == "1000000"
    finally:
        await fixture.close()
    if risk_observer:
        rows = [
            json.loads(line) for line in (tmp_path / "commit-times.jsonl").read_text().splitlines()
        ]
        assert rows and any(row["status"] == "VERIFIED" for row in rows)
        assert all(row["status"] in {"VERIFIED", "UNKNOWN"} for row in rows)


async def test_shared_stop_restore_fixture_recovers_pending_cursor_and_rejects_stale_resume(
    tmp_path: Path,
) -> None:
    fixture = Fixture(tmp_path)
    admin = create_async_engine(os.environ["TIEWTRADE_TEST_ADMIN_URL"], hide_parameters=True)
    staged = None
    try:
        fixture.owners = await f15.seed_owners(fixture.api, fixture.engine, fixture.scan, 2)
        for owner in fixture.owners:
            async with user_session(fixture.api, owner.user_id) as session:
                await session.execute(
                    "INSERT INTO user_trading_preferences(user_id,use) VALUES(:id,'BOT')",
                    {"id": owner.user_id},
                )
        staged = await profile_stop_restore.stage(fixture, tmp_path)
        await profile_stop_restore.verify(
            staged,
            {
                DatabaseRole.API: fixture.api,
                DatabaseRole.ENGINE: fixture.engine,
                DatabaseRole.ENGINE_SCAN: fixture.scan,
            },
            admin,
            tmp_path,
        )
    finally:
        try:
            # A global fence must not leak into the next fresh-global-state test.
            if staged is not None:
                platform = staged["requests"][1]
                cleanup = None
                async with user_session(fixture.api, UUID(platform["owner"])) as session:
                    progress = (
                        await session.execute(
                            "SELECT * FROM platform_stop_progress WHERE stop_id=:id",
                            {"id": UUID(platform["stop_id"])},
                        )
                    ).one()
                    if (
                        progress.discovery_complete
                        and progress.pending_count == progress.failed_count == 0
                    ):
                        cleanup = await submit_stop(
                            session,
                            mode=None,
                            action=StopAction.RESUME,
                            key=uuid4(),
                            expected_stop_id=UUID(platform["stop_id"]),
                            expected_revision=platform["revision"],
                            expected_summary_revision=progress.revision,
                            expected_reconciliation_revision=progress.reconciliation_revision,
                            reason_code="W4_TEST_CLEANUP",
                            platform=True,
                        )
                await run_stop_request_round(engine=fixture.engine, scan_engine=fixture.scan)
                if cleanup is not None:
                    async with user_session(fixture.api, UUID(platform["owner"])) as session:
                        terminal = await stop_receipt(session, cleanup.request_id)
                        assert terminal is not None and terminal.state == "APPLIED"
        finally:
            await fixture.close()
            await admin.dispose()
