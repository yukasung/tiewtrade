from collections.abc import AsyncIterator, Mapping
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.positions.test_storage import _fact
from tests.infra.risk_limits.test_requests import seed_setting
from tiewtrade.core.money import Money
from tiewtrade.core.orders import TradingMode
from tiewtrade.core.risk_limits import RiskReason, RiskScope
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.errors import RiskProtocolError
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_orders.initialization import enable_financial_writer
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.positions import PositionEventKind, apply_position_event
from tiewtrade.infra.risk_limits.boundaries import financial_boundary
from tiewtrade.infra.risk_limits.monitor import initialize_monitor
from tiewtrade.infra.risk_limits.storage import read_setting


@pytest.fixture
async def financial_protocol(
    migrator_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> AsyncIterator[None]:
    await seed_setting(engine_engine, owner)
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text("UPDATE risk_protocol_control SET publication_enabled=true,financial_enabled=true")
        )
    try:
        yield
    finally:
        async with migrator_engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE risk_protocol_control SET admission_enabled=false,"
                    "financial_enabled=false,publication_enabled=false"
                )
            )


async def test_financial_source_and_boundary_commit_or_rollback_together(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    financial_protocol: None,
) -> None:
    event = uuid4()
    fact = _fact(uuid4(), 1)
    with pytest.raises(RuntimeError, match="crash"):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await enable_financial_writer(session)
            await apply_position_event(
                session, wallet.episode_id, event, PositionEventKind.RECORD, fact
            )
            raise RuntimeError("crash before commit")
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert (
            await session.execute("SELECT count(*) FROM risk_boundary_claims")
        ).scalar_one() == 0
        assert (
            await session.execute("SELECT count(*) FROM paper_position_events")
        ).scalar_one() == 0
        await enable_financial_writer(session)
        async with financial_boundary(session, episode_id=wallet.episode_id, kind="FILL"):
            # F-14 nested writer must reuse the cash writer's boundary.
            await apply_position_event(
                session, wallet.episode_id, event, PositionEventKind.RECORD, fact
            )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        row = (await session.execute("SELECT * FROM risk_financial_boundaries")).one()
        assert row.before_state["source_sequence"] == 0
        assert row.after_state["source_sequence"] == 1
        assert isinstance(row.after_state["positions"][0]["total_cost"], str)
        assert Money.of(row.after_state["positions"][0]["total_cost"], "USDT") == Money.of(
            100, "USDT"
        )
        assert row.replay_pending
        assert (
            await session.execute("SELECT count(*) FROM risk_boundary_claims")
        ).scalar_one() == 1


async def test_old_financial_writer_cannot_spoof_fence_or_unfinalized_claim(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    financial_protocol: None,
) -> None:
    for shared_fence in (False, True):
        with pytest.raises(RiskProtocolError):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await enable_financial_writer(session)
                if shared_fence:
                    await session.execute("SELECT risk_financial_fence()")
                await session.execute(
                    "UPDATE paper_position_activity SET revision=revision+1 WHERE episode_id=:id",
                    {"id": wallet.episode_id},
                )
    with pytest.raises(RiskProtocolError):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            watermark = (await session.execute("SELECT risk_financial_fence()")).scalar_one()
            await session.execute(
                """INSERT INTO risk_boundary_claims
                (id,user_id,mode,wallet_id,episode_id,kind,price_watermark,before_state)
                VALUES(:id,:owner,'PAPER',:wallet,:episode,'FILL',:watermark,'{}')""",
                {
                    "id": uuid4(),
                    "owner": owner,
                    "wallet": wallet.wallet_id,
                    "episode": wallet.episode_id,
                    "watermark": watermark,
                },
            )


async def test_reservation_only_revision_does_not_need_publication_fence(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    financial_protocol: None,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await enable_financial_writer(session)
        await session.execute("UPDATE paper_wallet_state SET revision=revision+1")
        assert (
            await session.execute("SELECT count(*) FROM risk_boundary_claims")
        ).scalar_one() == 0


async def test_unconfigured_wallet_blocks_unfenced_writes_but_keeps_proven_sell_available(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from dataclasses import replace

    from tiewtrade.core.positions import ExecutionSide
    from tiewtrade.infra.positions.storage import _apply_position_event

    original = _fact(uuid4(), 1)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await enable_financial_writer(session)
        await apply_position_event(
            session, wallet.episode_id, uuid4(), PositionEventKind.RECORD, original
        )
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text("UPDATE risk_protocol_control SET publication_enabled=true,financial_enabled=true")
        )
    try:
        with pytest.raises(RiskProtocolError):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await enable_financial_writer(session)
                await session.execute("UPDATE paper_position_projections SET total_cost=total_cost")
        with pytest.raises(RiskProtocolError):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await enable_financial_writer(session)
                await _apply_position_event(
                    session, wallet.episode_id, uuid4(), PositionEventKind.RECORD, _fact(uuid4(), 2)
                )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await enable_financial_writer(session)
            await apply_position_event(
                session,
                wallet.episode_id,
                uuid4(),
                PositionEventKind.RECORD,
                replace(original, execution_id=uuid4(), side=ExecutionSide.SELL, source_sequence=2),
            )
            assert (
                await session.execute("SELECT held_quantity FROM paper_position_projections")
            ).scalar_one() == 0
            assert (
                await session.execute("SELECT count(*) FROM risk_limit_settings")
            ).scalar_one() == 0
    finally:
        async with migrator_engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE risk_protocol_control SET admission_enabled=false,"
                    "financial_enabled=false,publication_enabled=false"
                )
            )


@pytest.mark.parametrize("previous", ["0", "500ms"])
@pytest.mark.parametrize("timeout", [False, True])
@pytest.mark.parametrize("abort", [False, True])
async def test_optional_replay_timeout_restoration_keeps_financial_commit(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    financial_protocol: None,
    monkeypatch: pytest.MonkeyPatch,
    previous: str,
    timeout: bool,
    abort: bool,
) -> None:
    original = UserSession.execute
    restorations = 0

    async def delayed_restore(
        session: UserSession, statement: str, parameters: Mapping[str, object] | None = None
    ) -> Any:
        nonlocal restorations
        if statement == "SELECT set_config('statement_timeout',:previous,true)":
            restorations += 1
            assert (await original(session, "SHOW statement_timeout")).scalar_one() == "100ms"
            if timeout:
                # Real PostgreSQL cancellation aborts the current subtransaction.
                # Delaying in Python would not exercise statement_timeout/rollback.
                await original(session, "SELECT pg_sleep(0.2)")
        return await original(session, statement, parameters)

    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        scope = RiskScope(
            owner, TradingMode.PAPER, UUID(str(wallet.wallet_id)), UUID(str(wallet.episode_id))
        )
        await initialize_monitor(session, await read_setting(session, scope))

    monkeypatch.setattr(UserSession, "execute", delayed_restore)
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                "SELECT set_config('statement_timeout',:value,true)", {"value": previous}
            )
            await enable_financial_writer(session)
            async with financial_boundary(session, episode_id=wallet.episode_id, kind="FILL"):
                await apply_position_event(
                    session, wallet.episode_id, uuid4(), PositionEventKind.RECORD, _fact(uuid4(), 1)
                )
            assert (await session.execute("SHOW statement_timeout")).scalar_one() == previous
            if abort:
                raise RuntimeError("outer rollback")
    except RuntimeError as error:
        assert abort and str(error) == "outer rollback"
    else:
        assert not abort
    assert restorations == 1
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        if abort:
            counts = (
                await session.execute("""SELECT
                (SELECT count(*) FROM paper_position_events),
                (SELECT count(*) FROM risk_financial_boundaries),
                (SELECT count(*) FROM risk_boundary_claims)""")
            ).one()
            assert tuple(counts) == (0, 0, 0)
            return
        assert (
            await session.execute("SELECT count(*) FROM paper_position_events")
        ).scalar_one() == 1
        marker = (await session.execute("SELECT * FROM risk_financial_boundaries")).one()
        assert marker.before_state["source_sequence"] == 0
        assert marker.after_state["source_sequence"] == 1
        assert Money.of(marker.after_state["positions"][0]["total_cost"], "USDT") == Money.of(
            100, "USDT"
        )
        assert (await session.execute("SELECT finalized FROM risk_boundary_claims")).scalar_one()
        if timeout:
            evaluation = (
                await session.execute(
                    "SELECT reason,loss,replay_pending FROM risk_limit_evaluations"
                )
            ).one()
            assert evaluation.reason == RiskReason.SOURCE_UNAVAILABLE.value
            assert evaluation.loss is None and evaluation.replay_pending
            assert (
                await session.execute("SELECT replay_pending FROM risk_owner_state")
            ).scalar_one()
