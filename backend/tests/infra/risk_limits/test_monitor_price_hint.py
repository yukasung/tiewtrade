"""Committed public progress may wake an owner, but cannot authorize financial work."""

from dataclasses import replace
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.db.test_migrations import _alembic, _snapshot
from tests.infra.execution_market.test_dispatch import intent
from tests.infra.risk_limits.migration_support import (
    prepare_migration_roundtrip,
    restore_migration_roundtrip,
)
from tests.infra.risk_limits.test_monitor import publish, start
from tests.infra.risk_limits.test_prices import publication as publication
from tests.infra.risk_limits.test_requests import seed_setting
from tests.infra.risk_limits.test_scheduler import ready
from tiewtrade.core.risk_limits import RiskReason
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.errors import NotPermittedError
from tiewtrade.infra.db.session import (
    UserSession,
    market_data_session,
    scan_session_bypassing_rls,
)
from tiewtrade.infra.market_data.realtime_storage import set_connected
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits.evaluation_requests import request_evaluation
from tiewtrade.infra.risk_limits.monitor_snapshot import MonitorSnapshot, read_monitor_snapshot
from tiewtrade.services.engine import risk_limit as worker


@pytest.fixture
async def attempted(owner: UUID, monkeypatch: pytest.MonkeyPatch) -> list[UUID]:
    entered: list[UUID] = []

    async def observed(session: UserSession) -> MonitorSnapshot:
        snapshot = await read_monitor_snapshot(session)
        if session.user_id == owner:
            entered.append(owner)
            return snapshot
        # Other tests leave globally visible settings; do not mutate their owners.
        return replace(snapshot, owner=None)

    monkeypatch.setattr(worker, "read_monitor_snapshot", observed)
    return entered


async def defer(engine: AsyncEngine, owner: UUID) -> None:
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute(
            "UPDATE risk_owner_state SET due_at=clock_timestamp()+interval '1 day'"
        )


async def run(engine: AsyncEngine, scan: AsyncEngine, owner: UUID) -> worker.RiskRequestRound:
    return await worker.run_risk_monitor_round(
        engine=engine, scan_engine=scan, after_owner=UUID(int=owner.int - 1), limit=1
    )


async def test_new_committed_price_wakes_future_due_owner(
    publication: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    attempted: list[UUID],
) -> None:
    lease = await publish(publication, await start(publication), "1000")
    await ready(engine_engine, owner, wallet)
    await defer(engine_engine, owner)
    await run(engine_engine, scan_engine, owner)
    assert attempted == []
    await publish(publication, lease, "1100")
    result = await run(engine_engine, scan_engine, owner)
    assert attempted == [owner] and result.processed == 1 and result.next_owner == owner
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert (
            await session.execute(
                "SELECT cursor=(SELECT watermark FROM risk_price_publication) "
                "AND NOT replay_pending FROM risk_owner_state"
            )
        ).scalar_one()


async def test_uncommitted_publication_does_not_wake_owner(
    publication: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    attempted: list[UUID],
) -> None:
    lease = await publish(publication, await start(publication), "1000")
    await ready(engine_engine, owner, wallet)
    await defer(engine_engine, owner)
    async with market_data_session(publication) as publisher:
        await set_connected(publisher, lease, False)
        await run(engine_engine, scan_engine, owner)
        assert attempted == []
    result = await run(engine_engine, scan_engine, owner)
    assert attempted == [owner] and result.processed == 1


@pytest.mark.parametrize("trigger", ["due", "hint", "uninitialized"])
async def test_original_monitor_wakeups_remain_available(
    trigger: str,
    publication: AsyncEngine,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    attempted: list[UUID],
) -> None:
    await publish(publication, await start(publication), "1000")
    if trigger == "uninitialized":
        await seed_setting(engine_engine, owner)
    else:
        await ready(engine_engine, owner, wallet)
        if trigger == "hint":
            await defer(engine_engine, owner)
            async with user_session(api_engine, owner) as session:
                await request_evaluation(
                    session, intent(owner, wallet.episode_id), wallet.wallet_id
                )
    result = await run(engine_engine, scan_engine, owner)
    assert attempted == [owner] and result.processed == 1


async def test_pending_price_hint_cannot_hide_missing_frame(
    publication: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lease = await publish(publication, await start(publication), "1000")
    await ready(engine_engine, owner, wallet)
    await defer(engine_engine, owner)
    await publish(publication, lease, "1100")

    async def missing(session: UserSession) -> MonitorSnapshot:
        return replace(await read_monitor_snapshot(session), frames=[])

    monkeypatch.setattr(worker, "read_monitor_snapshot", missing)
    await run(engine_engine, scan_engine, owner)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert (
            await session.execute("SELECT reason FROM risk_limit_evaluations")
        ).scalar_one() != RiskReason.READY.value
        assert (await session.execute("SELECT count(*) FROM risk_stop_requests")).scalar_one() == 0
        assert (await session.execute("SELECT count(*) FROM paper_orders")).scalar_one() == 0


async def test_scanner_grants_are_narrow_and_roundtrip(
    migrator_engine: AsyncEngine, scan_engine: AsyncEngine
) -> None:
    before = await _snapshot(migrator_engine)
    migration_state = await prepare_migration_roundtrip(migrator_engine)
    async with scan_session_bypassing_rls(scan_engine) as session:
        await session.execute("SELECT cursor FROM risk_owner_state LIMIT 1")
        await session.execute("SELECT watermark FROM risk_price_publication")
    for statement in (
        "SELECT book FROM risk_owner_state LIMIT 1",
        "SELECT payload FROM market_risk_price_frames LIMIT 1",
        "UPDATE risk_owner_state SET cursor=cursor WHERE false",
        "UPDATE risk_price_publication SET watermark=watermark WHERE false",
    ):
        with pytest.raises(NotPermittedError):
            async with scan_session_bypassing_rls(scan_engine) as session:
                await session.execute(statement)
    try:
        _alembic("downgrade", "0057")
        for statement in (
            "SELECT cursor FROM risk_owner_state LIMIT 1",
            "SELECT watermark FROM risk_price_publication",
        ):
            with pytest.raises(NotPermittedError):
                async with scan_session_bypassing_rls(scan_engine) as session:
                    await session.execute(statement)
        async with scan_session_bypassing_rls(scan_engine) as session:
            await session.execute("SELECT user_id,mode,due_at FROM risk_owner_state LIMIT 1")
    finally:
        _alembic("upgrade", "head")
        await restore_migration_roundtrip(migrator_engine, migration_state)
    assert await _snapshot(migrator_engine) == before
