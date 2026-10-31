"""R16 uses the existing proof checks, owner scope and atomic replay writes."""

from dataclasses import replace
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.risk_limits.test_monitor import publish, start
from tests.infra.risk_limits.test_prices import publication as publication
from tests.infra.risk_limits.test_requests import submission
from tests.infra.risk_limits.test_scheduler import ready
from tiewtrade.core.orders import TradingMode
from tiewtrade.core.risk_limits import RiskReason
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits.dispatch import lock_risk_owner
from tiewtrade.infra.risk_limits.monitor import replay_monitor
from tiewtrade.infra.risk_limits.monitor_snapshot import read_monitor_snapshot
from tiewtrade.infra.risk_limits.storage import decode_monitor_owner, read_setting


@pytest.mark.parametrize("fault", ["missing", "checksum", "projection", "revision"])
async def test_snapshot_fault_cannot_publish_ready(
    publication: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    fault: str,
) -> None:
    lease = await publish(publication, await start(publication), "1000")
    await ready(engine_engine, owner, wallet)
    await publish(publication, lease, "900")
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await lock_risk_owner(session, TradingMode.PAPER)
        snapshot = await read_monitor_snapshot(session)
        assert snapshot.state["user_id"] == owner
        assert all(row["user_id"] == owner for row in snapshot.positions + snapshot.boundaries)
        if fault == "missing":
            snapshot = replace(snapshot, frames=snapshot.frames[:-1])
        elif fault == "checksum":
            snapshot = replace(
                snapshot, frames=[{**row, "valid": False} for row in snapshot.frames]
            )
        else:
            key = "source_record_count" if fault == "projection" else "revision"
            snapshot = replace(
                snapshot, positions=[{**row, key: row[key] + 1} for row in snapshot.positions]
            )
        setting = await read_setting(session, submission(owner, wallet).scope)
        result = await replay_monitor(session, setting, publication_fence=False, snapshot=snapshot)
        assert result.reason is RiskReason.SOURCE_UNAVAILABLE
        assert result.loss is None


async def test_snapshot_replay_rollback_and_other_owner_isolation(
    publication: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    lease = await publish(publication, await start(publication), "1000")
    await ready(engine_engine, owner, wallet)
    await publish(publication, lease, "900")
    before = None
    with pytest.raises(RuntimeError, match="rollback probe"):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await lock_risk_owner(session, TradingMode.PAPER)
            snapshot = await read_monitor_snapshot(session)
            before = snapshot.state["cursor"]
            state = decode_monitor_owner(owner, snapshot.owner)
            assert state is not None and state[1]
            await replay_monitor(session, state[0], publication_fence=False, snapshot=snapshot)
            raise RuntimeError("rollback probe")
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert (await session.execute("SELECT cursor FROM risk_owner_state")).scalar_one() == before
    async with user_session(
        engine_engine, UUID(int=owner.int ^ 1), role=DatabaseRole.ENGINE
    ) as session:
        await lock_risk_owner(session, TradingMode.PAPER)
        other = await read_monitor_snapshot(session)
        assert other.owner is None and other.state is None
        assert other.positions == other.boundaries == other.frames == []
