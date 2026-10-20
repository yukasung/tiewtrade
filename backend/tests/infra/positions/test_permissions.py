from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.positions import ExecutionFact, ExecutionSide, PositionPair
from tiewtrade.infra.db import DatabaseRole, scan_session_bypassing_rls, user_session
from tiewtrade.infra.db.errors import AppendOnlyViolationError, InfraError, NotPermittedError
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.positions import (
    PositionEventKind,
    apply_position_event,
    initialize_position_source,
)


@pytest.mark.parametrize(
    "role",
    [
        DatabaseRole.API,
        DatabaseRole.ENGINE_SCAN,
    ],
)
async def test_non_writer_roles_cannot_read_position_state(
    role: DatabaseRole,
    api_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    engine = api_engine if role is DatabaseRole.API else scan_engine
    with pytest.raises(NotPermittedError):
        context = (
            scan_session_bypassing_rls(engine)
            if role is DatabaseRole.ENGINE_SCAN
            else user_session(engine, owner, role=role)
        )
        async with context as session:
            await session.execute(
                "SELECT * FROM paper_position_activity WHERE episode_id=:episode",
                {"episode": wallet.episode_id},
            )


async def test_engine_rls_hides_another_owners_activity(
    engine_engine: AsyncEngine,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as stranger_session:
        count = (
            await stranger_session.execute(
                "SELECT count(*) FROM paper_position_activity WHERE episode_id=:episode",
                {"episode": wallet.episode_id},
            )
        ).scalar_one()
    assert count == 0


async def test_position_events_are_append_only_for_the_writer(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    event_id = uuid4()
    fact = ExecutionFact(
        uuid4(),
        PositionPair("BTC", "USDT"),
        ExecutionSide.BUY,
        Quantity.of("1", "BTC"),
        Money.of("100", "USDT"),
        None,
        1,
        datetime(2026, 10, 16, tzinfo=UTC),
    )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_position_source(session, wallet.episode_id, uuid4(), "9" * 64)
        await apply_position_event(
            session, wallet.episode_id, event_id, PositionEventKind.RECORD, fact
        )
    with pytest.raises((AppendOnlyViolationError, NotPermittedError)):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                "UPDATE paper_position_events SET quote_amount=101 WHERE id=:event",
                {"event": event_id},
            )


async def test_writer_cannot_delete_a_position_projection(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_position_source(session, wallet.episode_id, uuid4(), "8" * 64)
        await apply_position_event(
            session,
            wallet.episode_id,
            uuid4(),
            PositionEventKind.RECORD,
            ExecutionFact(
                uuid4(),
                PositionPair("BTC", "USDT"),
                ExecutionSide.BUY,
                Quantity.of("1", "BTC"),
                Money.of("100", "USDT"),
                None,
                1,
                datetime(2026, 10, 16, tzinfo=UTC),
            ),
        )
    with pytest.raises(NotPermittedError):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                "DELETE FROM paper_position_projections WHERE episode_id=:episode",
                {"episode": wallet.episode_id},
            )


async def test_database_rejects_an_incomplete_record_event(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_position_source(session, wallet.episode_id, uuid4(), "7" * 64)
    with pytest.raises(InfraError):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                """INSERT INTO paper_position_events
                (id,execution_id,user_id,wallet_id,episode_id,event_kind,source_sequence,
                 request_fingerprint,base,quote,occurred_at)
                VALUES (:id,:execution,:owner,:wallet,:episode,'RECORD',1,
                        :fingerprint,'BTC','USDT',clock_timestamp())""",
                {
                    "id": uuid4(),
                    "execution": uuid4(),
                    "owner": owner,
                    "wallet": wallet.wallet_id,
                    "episode": wallet.episode_id,
                    "fingerprint": "0" * 64,
                },
            )
