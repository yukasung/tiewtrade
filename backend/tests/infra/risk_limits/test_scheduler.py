"""Owner fairness and bounded asynchronous monitoring against real PostgreSQL roles."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.risk_limits.test_monitor import publish, start
from tests.infra.risk_limits.test_prices import publication as publication
from tests.infra.risk_limits.test_requests import seed_setting, submission
from tiewtrade.core.risk_limits import RiskEvaluation, RiskReason, RiskSetting
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_wallet import PaperWalletAction, admit_command, get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits.dispatch import lock_risk_owner
from tiewtrade.infra.risk_limits.monitor import initialize_monitor, replay_monitor
from tiewtrade.infra.risk_limits.monitor_snapshot import MonitorSnapshot, read_monitor_snapshot
from tiewtrade.infra.risk_limits.storage import read_setting
from tiewtrade.infra.users import create_user
from tiewtrade.services.engine import risk_limit as worker
from tiewtrade.services.engine.paper_wallet import run_paper_wallet_round


async def another_wallet(
    api: AsyncEngine,
    engine: AsyncEngine,
    scan: AsyncEngine,
    owner: UUID,
) -> PaperWalletSnapshot:
    await create_user(api, owner)
    async with user_session(api, owner) as session:
        await admit_command(
            session,
            action=PaperWalletAction.CREATE,
            idempotency_key=uuid4(),
            capital_text="10000",
            expected_episode_id=None,
        )
    await run_paper_wallet_round(engine=engine, scan_engine=scan, worker="risk-scheduler-fixture")
    async with user_session(api, owner) as session:
        wallet = await get_wallet(session)
    assert wallet is not None
    return wallet


async def ready(
    engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    await seed_setting(engine, owner)
    scope = submission(owner, wallet).scope
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_monitor(session, await read_setting(session, scope))
        await session.execute("UPDATE risk_owner_state SET due_at=clock_timestamp()")


async def test_locked_owner_cannot_starve_the_next_due_owner(
    caplog: pytest.LogCaptureFixture,
    publication: AsyncEngine,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    next_owner = UUID(int=owner.int + 1)
    other = await another_wallet(api_engine, engine_engine, scan_engine, next_owner)
    await publish(publication, await start(publication), "1000")
    await ready(engine_engine, owner, wallet)
    await ready(engine_engine, next_owner, other)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as blocker:
        await lock_risk_owner(blocker, submission(owner, wallet).scope.mode)
        before = (
            await blocker.execute("SELECT cursor,book,replay_pending FROM risk_owner_state")
        ).one()
        first = await worker.run_risk_monitor_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            limit=1,
            after_owner=UUID(int=owner.int - 1),
        )
        assert first.deferred == 1 and first.next_owner == owner
        assert (
            await blocker.execute("SELECT cursor,book,replay_pending FROM risk_owner_state")
        ).one() == before
        assert not [r for r in caplog.records if r.exc_info is not None]
        second = await worker.run_risk_monitor_round(
            engine=engine_engine, scan_engine=scan_engine, limit=1, after_owner=first.next_owner
        )
        assert second.processed == 1 and second.next_owner == next_owner
    recovered = await worker.run_risk_monitor_round(
        engine=engine_engine,
        scan_engine=scan_engine,
        limit=1,
        after_owner=UUID(int=owner.int - 1),
    )
    assert recovered.processed == 1 and recovered.next_owner == owner


@pytest.mark.parametrize("slots", [4, 8])
async def test_monitor_bounds_owner_transactions_and_keeps_other_pools_available(
    slots: int,
    publication: AsyncEngine,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owners = [UUID(int=owner.int + index) for index in range(slots + 1)]
    wallets = [wallet]
    for other in owners[1:]:
        wallets.append(await another_wallet(api_engine, engine_engine, scan_engine, other))
    await publish(publication, await start(publication), "1000")
    for identity, financial in zip(owners, wallets, strict=True):
        await ready(engine_engine, identity, financial)
    active = maximum = entered = 0
    slots_entered, release = asyncio.Event(), asyncio.Event()
    original = replay_monitor

    async def selected_owner(session: UserSession) -> MonitorSnapshot:
        snapshot = await read_monitor_snapshot(session)
        return snapshot if session.user_id in owners else replace(snapshot, owner=None)

    # Other tests leave settings for the global scanner; only these selected owners
    # participate in this bounded-slot barrier, even with a full-size page.
    monkeypatch.setattr(worker, "read_monitor_snapshot", selected_owner)

    async def observed(
        session: UserSession,
        setting: RiskSetting,
        *,
        publication_fence: bool = True,
        final_publication_fence: bool = False,
        snapshot: MonitorSnapshot | None = None,
    ) -> RiskEvaluation:
        nonlocal active, maximum, entered
        active += 1
        maximum = max(maximum, active)
        entered += 1
        if entered == slots:
            slots_entered.set()
        try:
            await release.wait()
            return await original(
                session,
                setting,
                publication_fence=publication_fence,
                final_publication_fence=final_publication_fence,
                snapshot=snapshot,
            )
        finally:
            active -= 1

    monkeypatch.setattr(worker, "replay_monitor", observed)
    monitor_engine = create_engine_for(DatabaseRole.ENGINE, pool_size=slots, max_overflow=0)
    request_engine = create_engine_for(DatabaseRole.ENGINE, pool_size=1, max_overflow=0)
    stop_engine = create_engine_for(DatabaseRole.ENGINE, pool_size=2, max_overflow=0)
    task = asyncio.create_task(
        worker.run_risk_monitor_round(
            engine=monitor_engine,
            scan_engine=scan_engine,
            limit=100,
            concurrency=slots,
            after_owner=UUID(int=owner.int - 1),
        )
    )
    try:
        await asyncio.wait_for(slots_entered.wait(), timeout=3)
        assert active == maximum == entered == slots
        if slots == 8:
            from tests.infra.execution_market.test_dispatch import intent
            from tests.infra.risk_limits.test_stops import breach
            from tiewtrade.core.orders import TradingMode
            from tiewtrade.infra.db.session import ScanSession
            from tiewtrade.infra.paper_orders.requests import admit_new_request
            from tiewtrade.infra.risk_limits.dispatch import DueRiskRequest
            from tiewtrade.infra.risk_limits.requests import submit_request

            request_owner = UUID(int=owner.int + slots + 1)
            stop_owner = UUID(int=owner.int + slots + 2)
            request_wallet = await another_wallet(
                api_engine, engine_engine, scan_engine, request_owner
            )
            stop_wallet = await another_wallet(api_engine, engine_engine, scan_engine, stop_owner)
            async with user_session(api_engine, request_owner) as session:
                request = await submit_request(session, submission(request_owner, request_wallet))
            async with user_session(api_engine, stop_owner) as session:
                opening = await admit_new_request(
                    session,
                    wallet_id=stop_wallet.wallet_id,
                    intent=intent(stop_owner, stop_wallet.episode_id),
                )
            stop_id = await breach(engine_engine, stop_owner, stop_wallet)

            async def selected_request(
                scan: ScanSession, *, limit: int = 20
            ) -> tuple[DueRiskRequest, ...]:
                return (DueRiskRequest(request.receipt_id, request_owner, TradingMode.PAPER),)

            monkeypatch.setattr(worker, "due_requests", selected_request)
            requests = await asyncio.wait_for(
                worker.run_risk_request_round(
                    engine=request_engine, scan_engine=scan_engine, worker="monitor-pool-test"
                ),
                timeout=3,
            )
            stops = await asyncio.wait_for(
                worker.run_risk_stop_round(
                    engine=stop_engine,
                    scan_engine=scan_engine,
                    limit=1,
                    after_owner=UUID(int=stop_owner.int - 1),
                ),
                timeout=3,
            )
            assert requests.processed == stops.processed == 1
            async with user_session(
                request_engine, request_owner, role=DatabaseRole.ENGINE
            ) as session:
                assert (
                    await session.execute(
                        "SELECT state FROM risk_limit_results WHERE request_id=:id",
                        {"id": request.receipt_id},
                    )
                ).scalar_one() == "APPLIED"
            async with user_session(stop_engine, stop_owner, role=DatabaseRole.ENGINE) as session:
                assert (
                    await session.execute(
                        "SELECT state FROM paper_order_request_results WHERE request_id=:id",
                        {"id": opening.request_id},
                    )
                ).scalar_one() == "REJECTED"
                assert (
                    await session.execute(
                        "SELECT target_set_complete AND pending_count=0 "
                        "FROM risk_stop_progress WHERE stop_id=:id",
                        {"id": stop_id},
                    )
                ).scalar_one()
            assert active == maximum == entered == slots
        release.set()
        result = await asyncio.wait_for(task, timeout=5)
        assert result.processed == slots + 1 and entered == slots + 1 and maximum == slots
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        for pool in (monitor_engine, request_engine, stop_engine):
            await pool.dispose()


async def test_scheduler_commits_captured_cursor_while_publication_advances(
    publication: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from collections.abc import Mapping
    from typing import Any

    lease = await publish(publication, await start(publication), "1000")
    await ready(engine_engine, owner, wallet)
    captured, release = asyncio.Event(), asyncio.Event()
    original = UserSession.execute

    async def paused(
        session: UserSession, statement: str, parameters: Mapping[str, object] | None = None
    ) -> Any:
        result = await original(session, statement, parameters)
        if "captured_watermark" in statement:
            settings = (
                await original(
                    session,
                    "SELECT current_setting('lock_timeout'),current_setting('statement_timeout')",
                )
            ).one()
            assert tuple(settings) == ("100ms", "700ms")
            captured.set()
            await release.wait()
        return result

    monkeypatch.setattr(UserSession, "execute", paused)
    task = asyncio.create_task(
        worker.run_risk_monitor_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            limit=1,
            after_owner=UUID(int=owner.int - 1),
        )
    )
    try:
        await asyncio.wait_for(captured.wait(), 3)
        await asyncio.wait_for(publish(publication, lease, "1200"), 3)
        release.set()
        assert (await asyncio.wait_for(task, 3)).processed == 1
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            row = (
                await session.execute("""SELECT o.cursor,p.watermark
              FROM risk_owner_state o CROSS JOIN risk_price_publication p""")
            ).one()
            assert row.cursor < row.watermark
            await session.execute("UPDATE risk_owner_state SET due_at=clock_timestamp()")
        assert (
            await worker.run_risk_monitor_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                limit=1,
                after_owner=UUID(int=owner.int - 1),
            )
        ).processed == 1
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("""SELECT o.cursor=p.watermark
              FROM risk_owner_state o CROSS JOIN risk_price_publication p""")
            ).scalar_one()
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("concurrency", [0, 9, True])
async def test_monitor_rejects_invalid_concurrency(
    engine_engine: AsyncEngine, scan_engine: AsyncEngine, concurrency: int
) -> None:
    with pytest.raises(ValueError, match="bounded monitor concurrency"):
        await worker.run_risk_monitor_round(
            engine=engine_engine, scan_engine=scan_engine, concurrency=concurrency
        )


@pytest.mark.parametrize("case", ["oldest", "equal", "uninitialized", "future", "hint"])
async def test_monitor_prioritizes_due_work_without_changing_the_selected_page(
    case: str,
    publication: AsyncEngine,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.infra.execution_market.test_dispatch import intent
    from tiewtrade.infra.risk_limits.evaluation_requests import request_evaluation

    owners = [UUID(int=owner.int + offset) for offset in range(3)]
    wallets = [wallet]
    for identity in owners[1:]:
        wallets.append(await another_wallet(api_engine, engine_engine, scan_engine, identity))
    await publish(publication, await start(publication), "1000")
    for index, (identity, financial) in enumerate(zip(owners, wallets, strict=True)):
        if case == "uninitialized" and index == 1:
            await seed_setting(engine_engine, identity)
            continue
        await ready(engine_engine, identity, financial)
        async with user_session(engine_engine, identity, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                "UPDATE risk_owner_state SET due_at=CAST(:due AS timestamptz)",
                {"due": datetime(2000 - index, 1, 1, tzinfo=UTC)},
            )
    if case == "equal":
        async with user_session(engine_engine, owners[1], role=DatabaseRole.ENGINE) as session:
            await session.execute("UPDATE risk_owner_state SET due_at='2000-01-01 00:00:00+00'")
    if case in {"future", "hint"}:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                "UPDATE risk_owner_state SET due_at=clock_timestamp()+interval '1 day'"
            )
        if case == "hint":
            async with user_session(api_engine, owner) as session:
                await request_evaluation(
                    session, intent(owner, wallet.episode_id), wallet.wallet_id
                )

    entered: list[UUID] = []

    async def observed(session: UserSession) -> MonitorSnapshot:
        entered.append(session.user_id)
        return await read_monitor_snapshot(session)

    monkeypatch.setattr(worker, "read_monitor_snapshot", observed)
    result = await worker.run_risk_monitor_round(
        engine=engine_engine,
        scan_engine=scan_engine,
        limit=2,
        concurrency=1,
        after_owner=UUID(int=owner.int - 1),
    )
    expected = [owners[0], owners[1]] if case == "equal" else [owners[1], owners[0]]
    if case == "future":
        expected = [owners[2], owners[1]]
    assert entered == expected
    assert result.processed == 2
    # The last EXECUTED owner must not replace the original page's final UUID.
    assert result.next_owner == owners[2 if case == "future" else 1]
    if case == "oldest":
        entered.clear()
        following = await worker.run_risk_monitor_round(
            engine=engine_engine, scan_engine=scan_engine, limit=1, after_owner=result.next_owner
        )
        assert entered == [owners[2]]
        assert following.processed == 1 and following.next_owner == owners[2]


async def test_active_exclusion_is_applied_before_limit_and_wraps_original_uuid_order(
    publication: AsyncEngine,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    owners = [UUID(int=owner.int + offset) for offset in range(3)]
    wallets = [wallet]
    for identity in owners[1:]:
        wallets.append(await another_wallet(api_engine, engine_engine, scan_engine, identity))
    await publish(publication, await start(publication), "1000")
    for identity, financial in zip(owners, wallets, strict=True):
        await ready(engine_engine, identity, financial)
    rows = await worker._scan_monitor_candidates(
        scan_engine, limit=1, after_owner=UUID(int=owner.int - 1), excluded=(owners[0], owners[1])
    )
    assert [UUID(str(r.user_id)) for r in rows] == [owners[2]]
    # Empty exclusion preserves the legacy page; cursor is the SQL UUID, not due priority.
    normal = await worker._scan_monitor_candidates(
        scan_engine, limit=2, after_owner=UUID(int=owner.int - 1)
    )
    assert [UUID(str(r.user_id)) for r in normal] == owners[:2]
    wrapped = await worker._scan_monitor_candidates(
        scan_engine, limit=1, after_owner=UUID(int=(1 << 128) - 1), excluded=tuple(owners[1:])
    )
    assert wrapped and UUID(str(wrapped[0].user_id)) <= owners[0]


@pytest.mark.parametrize("exit_kind", ["commit", "cancel", "rollback"])
async def test_two_monitor_instances_serialize_and_leave_one_breach_after_recovery(
    publication: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
    exit_kind: str,
) -> None:
    from tests.infra.positions.test_storage import _fact
    from tiewtrade.infra.paper_orders.initialization import enable_financial_writer
    from tiewtrade.infra.positions import PositionEventKind, apply_position_event

    lease = await publish(publication, await start(publication), "1000")
    await ready(engine_engine, owner, wallet)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await enable_financial_writer(session)
        await apply_position_event(
            session,
            wallet.episode_id,
            uuid4(),
            PositionEventKind.RECORD,
            _fact(uuid4(), 1, quote="1000"),
        )
    lease = await publish(publication, lease, "900")
    await publish(publication, lease, "1200")
    entered, release = asyncio.Event(), asyncio.Event()
    original = vars(worker)["acknowledge_evaluations"]

    async def hold_after_persist(session: UserSession, reason: RiskReason) -> None:
        await original(session, reason)
        if not entered.is_set():
            entered.set()
            await release.wait()
            if exit_kind == "rollback":
                raise RuntimeError("injected transaction rollback")

    monkeypatch.setattr(worker, "acknowledge_evaluations", hold_after_persist)
    peer = create_engine_for(DatabaseRole.ENGINE, pool_size=1, max_overflow=0)
    first = asyncio.create_task(worker._evaluate_monitor_owner(engine_engine, owner))
    try:
        await asyncio.wait_for(entered.wait(), 3)
        # A different pool/instance sees the same authoritative owner lock.
        assert await worker._evaluate_monitor_owner(peer, owner) == "deferred"
        if exit_kind == "cancel":
            first.cancel()
        release.set()
        result = await asyncio.gather(first, return_exceptions=True)
        if exit_kind == "cancel":
            assert isinstance(result[0], asyncio.CancelledError)
        else:
            assert result[0] == ("processed" if exit_kind == "commit" else "deferred")
        async with user_session(peer, owner, role=DatabaseRole.ENGINE) as session:
            count = (await session.execute("SELECT count(*) FROM risk_limit_events")).scalar_one()
            assert count == (1 if exit_kind == "commit" else 0)
        assert await worker._evaluate_monitor_owner(peer, owner) == "processed"
        assert await worker._evaluate_monitor_owner(engine_engine, owner) == "processed"
        async with user_session(peer, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("SELECT count(*) FROM risk_limit_events")
            ).scalar_one() == 1
            assert (
                await session.execute("SELECT count(*) FROM risk_stop_requests")
            ).scalar_one() == 1
            assert (
                await session.execute("SELECT count(*) FROM risk_stop_progress")
            ).scalar_one() == 1
            assert (
                await session.execute("SELECT count(*) FROM risk_owner_state")
            ).scalar_one() == 1
    finally:
        release.set()
        first.cancel()
        await asyncio.gather(first, return_exceptions=True)
        await peer.dispose()


async def test_setting_disappearing_after_selection_keeps_authoritative_evaluation(
    publication: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from sqlalchemy import text

    await publish(publication, await start(publication), "1000")
    await ready(engine_engine, owner, wallet)
    selected = await worker._scan_monitor_candidates(
        scan_engine, limit=1, after_owner=UUID(int=owner.int - 1)
    )
    assert selected[0].user_id == owner
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text("DELETE FROM risk_limit_settings WHERE user_id=:owner AND mode='PAPER'"),
            {"owner": owner},
        )
    assert await worker._evaluate_monitor_owner(engine_engine, owner) == "processed"
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert (await session.execute("SELECT count(*) FROM risk_limit_events")).scalar_one() == 0
        assert (await session.execute("SELECT count(*) FROM risk_stop_requests")).scalar_one() == 0
    following = await worker._scan_monitor_candidates(
        scan_engine, limit=1, after_owner=UUID(int=owner.int - 1)
    )
    assert owner not in [r.user_id for r in following]
