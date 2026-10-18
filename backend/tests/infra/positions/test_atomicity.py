import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.positions import ExecutionFact, ExecutionSide, FeeEffect, PositionPair
from tiewtrade.infra.audit import AuditEvent
from tiewtrade.infra.audit import record_event as audit_record_event
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.errors import DatabaseTimeoutError, InfraError
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.positions import (
    PositionEventKind,
    PositionWriteStatus,
    apply_position_event,
    initialize_position_source,
    read_position_activity,
    read_position_snapshot,
)


def _fact(*, external_fee: bool = False) -> ExecutionFact:
    return ExecutionFact(
        uuid4(),
        PositionPair("BTC", "USDT"),
        ExecutionSide.BUY,
        Quantity.of("1", "BTC"),
        Money.of("100", "USDT"),
        FeeEffect(Quantity.of("0.01", "BNB")) if external_fee else None,
        1,
        datetime(2026, 10, 16, tzinfo=UTC),
    )


async def _install_trigger(
    engine: AsyncEngine,
    *,
    name: str,
    table: str,
    operation: str,
    deferred: bool = False,
    sleep: bool = False,
) -> None:
    body = "PERFORM pg_sleep(1); RETURN NEW;" if sleep else "RAISE EXCEPTION 'injected';"
    trigger_kind = "CONSTRAINT TRIGGER" if deferred else "TRIGGER"
    deferral = "DEFERRABLE INITIALLY DEFERRED" if deferred else ""
    async with engine.begin() as connection:
        await connection.execute(
            text(
                f"CREATE FUNCTION {name}_fn() RETURNS trigger LANGUAGE plpgsql "
                f"AS $$ BEGIN {body} END $$"
            )
        )
        await connection.execute(
            text(
                f"CREATE {trigger_kind} {name} AFTER {operation} ON {table} "
                f"{deferral} FOR EACH ROW EXECUTE FUNCTION {name}_fn()"
            )
        )


async def _drop_trigger(engine: AsyncEngine, *, name: str, table: str) -> None:
    async with engine.begin() as connection:
        await connection.execute(text(f"DROP TRIGGER IF EXISTS {name} ON {table}"))
        await connection.execute(text(f"DROP FUNCTION IF EXISTS {name}_fn()"))


async def _counts(engine: AsyncEngine, owner: UUID, episode_id: UUID) -> tuple[int, int, int, int]:
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        values = []
        for table in (
            "paper_position_events",
            "paper_position_projections",
            "paper_position_external_fees",
            "audit_events",
        ):
            result = await session.execute(
                f"SELECT count(*) FROM {table} WHERE "
                + (
                    "owner_user_id=:owner AND action LIKE 'PAPER_POSITION_%'"
                    if table == "audit_events"
                    else "episode_id=:episode"
                ),
                {"owner": owner, "episode": episode_id},
            )
            values.append(int(result.scalar_one()))
    return values[0], values[1], values[2], values[3]


@pytest.mark.parametrize(
    ("table", "operation", "external_fee"),
    [
        ("paper_position_events", "INSERT", False),
        ("paper_position_projections", "INSERT", False),
        ("paper_position_external_fees", "INSERT", True),
        ("paper_position_activity", "UPDATE", False),
        ("audit_events", "INSERT", False),
    ],
)
async def test_each_write_boundary_rolls_back_and_retry_applies_once(
    migrator_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    table: str,
    operation: str,
    external_fee: bool,
) -> None:
    fact, event_id = _fact(external_fee=external_fee), uuid4()
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        ready = await initialize_position_source(session, wallet.episode_id, uuid4(), "3" * 64)
    name = f"test_f14_{uuid4().hex}"
    await _install_trigger(migrator_engine, name=name, table=table, operation=operation)
    try:
        with pytest.raises(InfraError):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await apply_position_event(
                    session, wallet.episode_id, event_id, PositionEventKind.RECORD, fact
                )
    finally:
        await _drop_trigger(migrator_engine, name=name, table=table)

    assert await _counts(engine_engine, owner, wallet.episode_id) == (0, 0, 0, 0)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        activity = await read_position_activity(session, wallet.episode_id)
        retried = await apply_position_event(
            session, wallet.episode_id, event_id, PositionEventKind.RECORD, fact
        )
    assert activity == ready
    assert retried.status is PositionWriteStatus.APPLIED
    assert await _counts(engine_engine, owner, wallet.episode_id) == (
        1,
        1,
        1 if external_fee else 0,
        1,
    )


async def test_cancellation_after_activity_write_rolls_back_and_connection_is_reusable(
    monkeypatch: pytest.MonkeyPatch,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    fact, event_id = _fact(), uuid4()
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        ready = await initialize_position_source(session, wallet.episode_id, uuid4(), "4" * 64)
    reached = asyncio.Event()

    async def block_audit(*args: object, **kwargs: object) -> None:
        reached.set()
        await asyncio.Future()

    async def write() -> None:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await apply_position_event(
                session, wallet.episode_id, event_id, PositionEventKind.RECORD, fact
            )

    with monkeypatch.context() as context:
        context.setattr("tiewtrade.infra.positions.storage.record_event", block_audit)
        task = asyncio.create_task(write())
        await asyncio.wait_for(reached.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert await _counts(engine_engine, owner, wallet.episode_id) == (0, 0, 0, 0)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert await read_position_activity(session, wallet.episode_id) == ready
        result = await apply_position_event(
            session, wallet.episode_id, event_id, PositionEventKind.RECORD, fact
        )
    assert result.status is PositionWriteStatus.APPLIED


async def test_statement_timeout_rolls_back_the_whole_write(
    migrator_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    fact, event_id = _fact(), uuid4()
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_position_source(session, wallet.episode_id, uuid4(), "5" * 64)
    name = f"test_f14_{uuid4().hex}"
    await _install_trigger(
        migrator_engine,
        name=name,
        table="paper_position_projections",
        operation="INSERT",
        sleep=True,
    )
    try:
        with pytest.raises(DatabaseTimeoutError):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await session.execute("SET LOCAL statement_timeout='50ms'")
                await apply_position_event(
                    session, wallet.episode_id, event_id, PositionEventKind.RECORD, fact
                )
    finally:
        await _drop_trigger(migrator_engine, name=name, table="paper_position_projections")
    assert await _counts(engine_engine, owner, wallet.episode_id) == (0, 0, 0, 0)


async def test_deferred_commit_failure_rolls_back_the_whole_write(
    migrator_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    fact, event_id = _fact(), uuid4()
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_position_source(session, wallet.episode_id, uuid4(), "6" * 64)
    name = f"test_f14_{uuid4().hex}"
    await _install_trigger(
        migrator_engine,
        name=name,
        table="paper_position_activity",
        operation="UPDATE",
        deferred=True,
    )
    try:
        with pytest.raises(InfraError):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                result = await apply_position_event(
                    session, wallet.episode_id, event_id, PositionEventKind.RECORD, fact
                )
                assert result.status is PositionWriteStatus.APPLIED
    finally:
        await _drop_trigger(migrator_engine, name=name, table="paper_position_activity")
    assert await _counts(engine_engine, owner, wallet.episode_id) == (0, 0, 0, 0)


async def test_snapshot_racing_a_writer_is_wholly_before_or_after_commit(
    monkeypatch: pytest.MonkeyPatch,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    first = _fact()
    second = ExecutionFact(
        uuid4(),
        PositionPair("ETH", "USDT"),
        ExecutionSide.BUY,
        Quantity.of("1", "ETH"),
        Money.of("50", "USDT"),
        None,
        2,
        datetime(2026, 10, 16, tzinfo=UTC),
    )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_position_source(session, wallet.episode_id, uuid4(), "0" * 64)
        await apply_position_event(
            session, wallet.episode_id, uuid4(), PositionEventKind.RECORD, first
        )

    reached, release = asyncio.Event(), asyncio.Event()

    async def pause_audit(session: object, event: AuditEvent) -> None:
        reached.set()
        await release.wait()
        await audit_record_event(session, event)

    async def write() -> None:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await apply_position_event(
                session, wallet.episode_id, uuid4(), PositionEventKind.RECORD, second
            )

    with monkeypatch.context() as context:
        context.setattr("tiewtrade.infra.positions.storage.record_event", pause_audit)
        task = asyncio.create_task(write())
        await asyncio.wait_for(reached.wait(), 2)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            before = await read_position_snapshot(session, wallet.episode_id)
        release.set()
        await task

    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        after = await read_position_snapshot(session, wallet.episode_id)
    assert before is not None and after is not None
    assert before.activity.source_sequence == 1
    assert {position.pair.base for position in before.positions} == {"BTC"}
    assert after.activity.source_sequence == 2
    assert {position.pair.base for position in after.positions} == {"BTC", "ETH"}
    assert {position.last_sequence for position in after.positions} == {2}
