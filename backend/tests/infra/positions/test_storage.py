import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.positions import ExecutionFact, ExecutionSide, FeeEffect
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.positions import (
    PositionEventKind,
    PositionIntegrityError,
    PositionWriteStatus,
    apply_position_event,
    initialize_position_source,
    read_position_activity,
    read_position_snapshot,
    read_valued_position_snapshot,
)


def _fact(
    execution_id: UUID,
    sequence: int,
    *,
    quote: str = "100",
    fee: Quantity | None = None,
    base: str = "BTC",
) -> ExecutionFact:
    from tiewtrade.core.positions import PositionPair

    return ExecutionFact(
        execution_id=execution_id,
        pair=PositionPair(base, "USDT"),
        side=ExecutionSide.BUY,
        gross_quantity=Quantity.of("1", base),
        quote_amount=Money.of(quote, "USDT"),
        fee=None if fee is None else FeeEffect(fee),
        source_sequence=sequence,
        occurred_at=datetime(2026, 10, 16, tzinfo=UTC),
    )


async def _reset_btc_price(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """UPDATE market_price_feed SET connected=false,
                lease_until=clock_timestamp(),last_failure_code='MISSING'
                WHERE source='primary_spot'"""
            )
        )
        await connection.execute(
            text(
                """UPDATE market_latest_prices SET amount=NULL,trade_id=NULL,
                trade_at=NULL,received_at=NULL,observation_kind=NULL,
                reconciled_generation=0,effective_readiness='MISSING',
                reason='MISSING',unavailable_since=clock_timestamp(),revision=revision+1
                WHERE source='primary_spot' AND base='BTC' AND quote='USDT'"""
            )
        )


async def test_apply_replay_and_replace_rebuild_are_exact(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    initialization_id, event_id, correction_id, execution_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    original = _fact(execution_id, 1, fee=Quantity.of("0.01", "BNB"))
    replacement = _fact(execution_id, 1, quote="110", fee=Quantity.of("0.02", "ETH"))

    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        ready = await initialize_position_source(
            session, wallet.episode_id, initialization_id, "a" * 64
        )
        applied = await apply_position_event(
            session, wallet.episode_id, event_id, PositionEventKind.RECORD, original
        )
    assert ready.availability.value == "READY"
    assert applied.status is PositionWriteStatus.APPLIED

    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        replay = await apply_position_event(
            session, wallet.episode_id, uuid4(), PositionEventKind.RECORD, original
        )
    assert replay.status is PositionWriteStatus.REPLAYED
    assert replay.event_id == event_id

    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        corrected = await apply_position_event(
            session,
            wallet.episode_id,
            correction_id,
            PositionEventKind.REPLACE,
            replacement,
            event_id,
        )
        correction_replay = await apply_position_event(
            session,
            wallet.episode_id,
            uuid4(),
            PositionEventKind.REPLACE,
            replacement,
            event_id,
        )
        snapshot = await read_position_snapshot(session, wallet.episode_id)

    assert corrected.status is PositionWriteStatus.APPLIED
    assert correction_replay.status is PositionWriteStatus.REPLAYED
    assert correction_replay.event_id == correction_id
    assert corrected.activity.source_sequence == 1
    assert corrected.effects is not None
    assert [
        (effect.asset, effect.as_parts()["quantity"])
        for effect in corrected.effects.external_asset_effects
    ] == [("BNB", "0.01"), ("ETH", "-0.02")]
    assert snapshot is not None
    assert snapshot.positions[0].total_cost == Money.of("110", "USDT")


async def test_sequence_gap_is_durable_and_idempotent(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    event_id = uuid4()
    fact = _fact(uuid4(), 2)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_position_source(session, wallet.episode_id, uuid4(), "b" * 64)
        first = await apply_position_event(
            session, wallet.episode_id, event_id, PositionEventKind.RECORD, fact
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        replay = await apply_position_event(
            session, wallet.episode_id, event_id, PositionEventKind.RECORD, fact
        )
        activity = await read_position_activity(session, wallet.episode_id)

    assert first.status is replay.status is PositionWriteStatus.CONFLICTED
    assert first.failure_code == replay.failure_code == "POSITION_SEQUENCE_GAP"
    assert activity is not None and activity.revision == first.activity.revision


async def test_source_initialization_retry_remains_idempotent_after_fills(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    proof = "7" * 64
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_position_source(session, wallet.episode_id, uuid4(), proof)
        applied = await apply_position_event(
            session,
            wallet.episode_id,
            uuid4(),
            PositionEventKind.RECORD,
            _fact(uuid4(), 1),
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        retried = await initialize_position_source(session, wallet.episode_id, uuid4(), proof)
        conflicts = (
            await session.execute(
                "SELECT count(*) FROM paper_position_conflicts WHERE episode_id=:episode",
                {"episode": wallet.episode_id},
            )
        ).scalar_one()

    assert retried == applied.activity
    assert conflicts == 0


async def test_conflict_keeps_projection_at_the_activity_revision(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_position_source(session, wallet.episode_id, uuid4(), "6" * 64)
        await apply_position_event(
            session,
            wallet.episode_id,
            uuid4(),
            PositionEventKind.RECORD,
            _fact(uuid4(), 1),
        )
        conflict = await apply_position_event(
            session,
            wallet.episode_id,
            uuid4(),
            PositionEventKind.RECORD,
            _fact(uuid4(), 3),
        )
        snapshot = await read_position_snapshot(session, wallet.episode_id)
        valued = await read_valued_position_snapshot(session, wallet.episode_id)

    assert conflict.status is PositionWriteStatus.CONFLICTED
    assert snapshot is not None and snapshot.activity == conflict.activity
    assert snapshot.positions[0].last_sequence == 1
    assert valued is not None and valued.activity == conflict.activity
    assert valued.positions[0].unrealized_pnl is None
    assert valued.positions[0].reason == "POSITION_SOURCE_UNKNOWN"


async def test_snapshot_rejects_a_missing_projection(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_position_source(session, wallet.episode_id, uuid4(), "5" * 64)
        await apply_position_event(
            session,
            wallet.episode_id,
            uuid4(),
            PositionEventKind.RECORD,
            _fact(uuid4(), 1),
        )
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text("ALTER TABLE paper_position_projections NO FORCE ROW LEVEL SECURITY")
        )
        await connection.execute(
            text("DELETE FROM paper_position_projections WHERE episode_id=:episode"),
            {"episode": wallet.episode_id},
        )
        await connection.execute(
            text("ALTER TABLE paper_position_projections FORCE ROW LEVEL SECURITY")
        )

    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        with pytest.raises(PositionIntegrityError, match="incomplete"):
            await read_position_snapshot(session, wallet.episode_id)
        with pytest.raises(PositionIntegrityError, match="incomplete"):
            await read_valued_position_snapshot(session, wallet.episode_id)


async def test_concurrent_execution_replay_has_one_economic_effect(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    fact = _fact(uuid4(), 1)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_position_source(session, wallet.episode_id, uuid4(), "c" * 64)

    async def write(event_id: UUID) -> PositionWriteStatus:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            result = await apply_position_event(
                session, wallet.episode_id, event_id, PositionEventKind.RECORD, fact
            )
            return result.status

    statuses = await asyncio.gather(write(uuid4()), write(uuid4()))

    assert sorted(status.value for status in statuses) == ["APPLIED", "REPLAYED"]
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        count = (
            await session.execute(
                "SELECT count(*) FROM paper_position_events WHERE episode_id=:episode",
                {"episode": wallet.episode_id},
            )
        ).scalar_one()
    assert count == 1


@pytest.mark.parametrize("reuse_event_id", [True, False])
async def test_duplicate_identity_or_sequence_conflict_is_durable_and_idempotent(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    reuse_event_id: bool,
) -> None:
    event_id, execution_id = uuid4(), uuid4()
    original = _fact(execution_id, 1)
    conflicting = _fact(execution_id if reuse_event_id else uuid4(), 1, quote="101")
    conflicting_event_id = event_id if reuse_event_id else uuid4()
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_position_source(session, wallet.episode_id, uuid4(), "4" * 64)
        await apply_position_event(
            session, wallet.episode_id, event_id, PositionEventKind.RECORD, original
        )
        first = await apply_position_event(
            session,
            wallet.episode_id,
            conflicting_event_id,
            PositionEventKind.RECORD,
            conflicting,
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        replay = await apply_position_event(
            session,
            wallet.episode_id,
            conflicting_event_id,
            PositionEventKind.RECORD,
            conflicting,
        )
        conflict_count = (
            await session.execute(
                "SELECT count(*) FROM paper_position_conflicts WHERE episode_id=:episode",
                {"episode": wallet.episode_id},
            )
        ).scalar_one()
        audit_count = (
            await session.execute(
                """SELECT count(*) FROM audit_events
                WHERE owner_user_id=:owner AND action='PAPER_POSITION_CONFLICTED'""",
                {"owner": owner},
            )
        ).scalar_one()

    assert first.status is replay.status is PositionWriteStatus.CONFLICTED
    assert first.activity.revision == replay.activity.revision
    assert conflict_count == audit_count == 1


async def test_caller_failure_rolls_back_event_projection_activity_and_audit(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    event_id = uuid4()
    fact = _fact(uuid4(), 1)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        ready = await initialize_position_source(session, wallet.episode_id, uuid4(), "d" * 64)

    with pytest.raises(RuntimeError, match="injected"):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await apply_position_event(
                session, wallet.episode_id, event_id, PositionEventKind.RECORD, fact
            )
            raise RuntimeError("injected")

    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        activity = await read_position_activity(session, wallet.episode_id)
        count = (
            await session.execute(
                "SELECT count(*) FROM paper_position_events WHERE episode_id=:episode",
                {"episode": wallet.episode_id},
            )
        ).scalar_one()
        retried = await apply_position_event(
            session, wallet.episode_id, event_id, PositionEventKind.RECORD, fact
        )
    assert activity == ready
    assert count == 0
    assert retried.status is PositionWriteStatus.APPLIED


async def test_multi_pair_snapshot_uses_one_activity_revision(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_position_source(session, wallet.episode_id, uuid4(), "e" * 64)
        await apply_position_event(
            session, wallet.episode_id, uuid4(), PositionEventKind.RECORD, _fact(uuid4(), 1)
        )
        await apply_position_event(
            session,
            wallet.episode_id,
            uuid4(),
            PositionEventKind.RECORD,
            _fact(uuid4(), 2, base="ETH"),
        )
        snapshot = await read_position_snapshot(session, wallet.episode_id)

    assert snapshot is not None
    assert snapshot.snapshot_at.tzinfo is not None
    assert snapshot.activity.source_sequence == 2
    assert {position.last_sequence for position in snapshot.positions} == {2}
    assert {position.pair.base for position in snapshot.positions} == {"BTC", "ETH"}


async def test_void_keeps_source_completeness_and_clears_position(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    event_id, execution_id = uuid4(), uuid4()
    fact = _fact(execution_id, 1)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_position_source(session, wallet.episode_id, uuid4(), "f" * 64)
        await apply_position_event(
            session, wallet.episode_id, event_id, PositionEventKind.RECORD, fact
        )
        voided = await apply_position_event(
            session,
            wallet.episode_id,
            uuid4(),
            PositionEventKind.VOID,
            fact,
            event_id,
        )
        snapshot = await read_position_snapshot(session, wallet.episode_id)

    assert voided.status is PositionWriteStatus.APPLIED
    assert voided.activity.source_sequence == 1
    assert voided.effects is not None
    assert voided.effects.base_delta == Quantity.of("-1", "BTC")
    assert snapshot is not None
    assert snapshot.positions[0].held_quantity == Quantity.of("0", "BTC")


async def test_replace_can_reinstate_a_voided_execution_at_the_original_sequence(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    record_id, void_id, execution_id = uuid4(), uuid4(), uuid4()
    original = _fact(execution_id, 1)
    replacement = _fact(execution_id, 1, quote="120")
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_position_source(session, wallet.episode_id, uuid4(), "7" * 64)
        await apply_position_event(
            session, wallet.episode_id, record_id, PositionEventKind.RECORD, original
        )
        await apply_position_event(
            session,
            wallet.episode_id,
            void_id,
            PositionEventKind.VOID,
            original,
            record_id,
        )
        reinstated = await apply_position_event(
            session,
            wallet.episode_id,
            uuid4(),
            PositionEventKind.REPLACE,
            replacement,
            void_id,
        )
        snapshot = await read_position_snapshot(session, wallet.episode_id)

    assert reinstated.status is PositionWriteStatus.APPLIED
    assert reinstated.activity.source_sequence == 1
    assert snapshot is not None
    assert snapshot.positions[0].total_cost == Money.of("120", "USDT")


async def test_initialization_conflict_is_durable_without_a_fake_pair(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    conflict_id = uuid4()
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_position_source(session, wallet.episode_id, uuid4(), "1" * 64)
        await apply_position_event(
            session,
            wallet.episode_id,
            uuid4(),
            PositionEventKind.RECORD,
            _fact(uuid4(), 1),
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        conflicted = await initialize_position_source(
            session, wallet.episode_id, conflict_id, "2" * 64
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        replay = await initialize_position_source(session, wallet.episode_id, conflict_id, "2" * 64)
        snapshot = await read_position_snapshot(session, wallet.episode_id)
        audit = (
            (
                await session.execute(
                    """SELECT subject_kind,details FROM audit_events
                    WHERE owner_user_id=:owner AND action='PAPER_POSITION_CONFLICTED'""",
                    {"owner": owner},
                )
            )
            .mappings()
            .one()
        )

    assert conflicted.availability.value == "CONFLICTED"
    assert replay.revision == conflicted.revision
    assert snapshot is not None and snapshot.activity == conflicted
    assert audit["subject_kind"] == "PAPER_POSITION_ACTIVITY"
    assert set(audit["details"]) == {"episode_id", "initialization_id"}


async def test_valuation_requires_a_fresh_reconciled_price(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    await _reset_btc_price(migrator_engine)
    fact = _fact(uuid4(), 1)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_position_source(session, wallet.episode_id, uuid4(), "8" * 64)
        await apply_position_event(
            session, wallet.episode_id, uuid4(), PositionEventKind.RECORD, fact
        )
        missing = await read_valued_position_snapshot(session, wallet.episode_id)
    assert missing is not None
    assert missing.positions[0].unrealized_pnl is None
    assert missing.positions[0].reason == "PRICE_MISSING"

    async with migrator_engine.begin() as connection:
        await connection.execute(
            text(
                """UPDATE market_price_feed SET connected=true,
                lease_until=clock_timestamp()+interval '5 minutes'
                WHERE source='primary_spot'"""
            )
        )
        await connection.execute(
            text(
                """UPDATE market_latest_prices SET amount=150,trade_id=1,
                trade_at=clock_timestamp(),received_at=clock_timestamp(),
                observation_kind='STREAM',
                reconciled_generation=(SELECT generation FROM market_price_feed
                                       WHERE source='primary_spot'),
                effective_readiness='READY',reason=NULL,revision=revision+1
                WHERE source='primary_spot' AND base='BTC' AND quote='USDT'"""
            )
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        fresh = await read_valued_position_snapshot(session, wallet.episode_id)
    assert fresh is not None
    assert fresh.activity.user_id == owner
    assert fresh.activity.mode == "PAPER"
    assert fresh.activity.source_proof == "8" * 64
    assert fresh.positions[0].unrealized_pnl == Money.of("50", "USDT")
    assert fresh.positions[0].reason is None

    async with migrator_engine.begin() as connection:
        await connection.execute(
            text(
                """UPDATE market_price_feed SET connected=false
                WHERE source='primary_spot'"""
            )
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        disconnected = await read_valued_position_snapshot(session, wallet.episode_id)
    assert disconnected is not None
    assert disconnected.positions[0].unrealized_pnl is None
    assert disconnected.positions[0].reason == "PRICE_DISCONNECTED"

    async with migrator_engine.begin() as connection:
        await connection.execute(
            text(
                """UPDATE market_price_feed SET connected=true,
                lease_until=clock_timestamp()-interval '1 second'
                WHERE source='primary_spot'"""
            )
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        unavailable = await read_valued_position_snapshot(session, wallet.episode_id)
    assert unavailable is not None
    assert unavailable.positions[0].unrealized_pnl is None
    assert unavailable.positions[0].reason == "PRICE_PRODUCER_UNAVAILABLE"

    async with migrator_engine.begin() as connection:
        await connection.execute(
            text(
                """UPDATE market_price_feed SET lease_until=clock_timestamp()+interval '5 minutes'
                WHERE source='primary_spot'"""
            )
        )
        await connection.execute(
            text(
                """UPDATE market_latest_prices SET reconciled_generation=0,revision=revision+1
                WHERE source='primary_spot' AND base='BTC' AND quote='USDT'"""
            )
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        unreconciled = await read_valued_position_snapshot(session, wallet.episode_id)
    assert unreconciled is not None
    assert unreconciled.positions[0].unrealized_pnl is None
    assert unreconciled.positions[0].reason == "PRICE_UNRECONCILED"

    async with migrator_engine.begin() as connection:
        await connection.execute(
            text(
                """UPDATE market_latest_prices SET
                reconciled_generation=(SELECT generation FROM market_price_feed
                                       WHERE source='primary_spot'),
                trade_at=clock_timestamp()+interval '5 minutes',revision=revision+1
                WHERE source='primary_spot' AND base='BTC' AND quote='USDT'"""
            )
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        future = await read_valued_position_snapshot(session, wallet.episode_id)
    assert future is not None
    assert future.positions[0].unrealized_pnl is None
    assert future.positions[0].reason == "PRICE_INVALID_TIME"

    async with migrator_engine.begin() as connection:
        await connection.execute(
            text(
                """UPDATE market_latest_prices SET trade_at=clock_timestamp(),
                effective_readiness='RECOVERING',revision=revision+1
                WHERE source='primary_spot' AND base='BTC' AND quote='USDT'"""
            )
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        recovering = await read_valued_position_snapshot(session, wallet.episode_id)
    assert recovering is not None
    assert recovering.positions[0].unrealized_pnl is None
    assert recovering.positions[0].reason == "PRICE_UNAVAILABLE"

    async with migrator_engine.begin() as connection:
        await connection.execute(
            text(
                """UPDATE market_latest_prices
                SET trade_at=clock_timestamp()-interval '11 seconds',
                    effective_readiness='READY',revision=revision+1
                WHERE source='primary_spot' AND base='BTC' AND quote='USDT'"""
            )
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        stale = await read_valued_position_snapshot(session, wallet.episode_id)
    assert stale is not None
    assert stale.positions[0].unrealized_pnl is None
    assert stale.positions[0].reason == "PRICE_STALE"

    await _reset_btc_price(migrator_engine)
