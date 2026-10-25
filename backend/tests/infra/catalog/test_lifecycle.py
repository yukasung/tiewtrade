from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.market_data import CandleSeries, initial_window
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.timeframes import Timeframe
from tiewtrade.infra.db import (
    CatalogIdempotencyConflictError,
    CatalogStateError,
    DatabaseRole,
    create_engine_for,
    user_session,
)
from tiewtrade.infra.db.session import market_data_session, presented_session
from tiewtrade.infra.indicators.session import indicator_writer_session
from tiewtrade.infra.market_data.candle_preview import acquire as acquire_preview
from tiewtrade.infra.market_data.claims import claim_next, lock_claim
from tiewtrade.infra.market_data.realtime_storage import database_now
from tiewtrade.infra.market_data.records import StaleClaimError
from tiewtrade.infra.paper_orders.storage import lock_pair_catalog
from tiewtrade.infra.platform import (
    CatalogAction,
    CatalogCommand,
    CatalogReason,
    ConstraintEvidence,
    RuntimeSymbol,
    activate,
    enable_mutations,
    fail_preparation,
    prepare,
    read_catalog,
    reconcile_maintenance_proofs,
    reconcile_removal_effects,
    record_price_readiness,
    record_protocol_heartbeat,
    record_timeframe_readiness,
    replay_command,
    request_add,
    request_remove,
    runtime_symbols,
)
from tiewtrade.infra.realtime.notifications import RedisNotifications
from tiewtrade.infra.users import create_user
from tiewtrade.services.market_data.candle_realtime import CandleSupervisor
from tiewtrade.services.market_data.ingestion import _publish_preparation_readiness
from tiewtrade.venues.fake import FakeCandleFeed


async def test_third_pair_completes_prepare_activate_remove_and_readd_lifecycle(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    owner = uuid4()
    generation = uuid4()
    market_engine = create_engine_for(DatabaseRole.MARKET_DATA)
    indicator_engine = create_engine_for(DatabaseRole.INDICATOR_BUILDER)
    await create_user(api_engine, owner)
    try:
        async with migrator_engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('tiewtrade.current_user_id',:owner,true)"),
                {"owner": str(owner)},
            )
            await connection.execute(
                text(
                    "INSERT INTO platform_memberships(user_id,role) VALUES(:owner,'PLATFORM_OWNER')"
                ),
                {"owner": owner},
            )

        expires = datetime.now(UTC) + timedelta(minutes=2)
        for role_engine, role, kind in (
            (api_engine, DatabaseRole.API, "API"),
            (engine_engine, DatabaseRole.ENGINE, "ENGINE"),
            (market_engine, DatabaseRole.MARKET_DATA, "MARKET_DATA"),
            (
                indicator_engine,
                DatabaseRole.INDICATOR_BUILDER,
                "INDICATOR_BUILDER",
            ),
        ):
            if role in {DatabaseRole.API, DatabaseRole.ENGINE}:
                async with presented_session(role_engine, role=role) as heartbeat_session:
                    await record_protocol_heartbeat(
                        heartbeat_session,
                        process_kind=kind,
                        instance_id=uuid4(),
                        protocol_version=1,
                        deployment_generation=generation,
                        lease_expires_at=expires,
                    )
                continue
            session_factory = (
                market_data_session
                if role is DatabaseRole.MARKET_DATA
                else indicator_writer_session
            )
            async with session_factory(role_engine) as worker_session:
                await record_protocol_heartbeat(
                    worker_session,
                    process_kind=kind,
                    instance_id=uuid4(),
                    protocol_version=1,
                    deployment_generation=generation,
                    lease_expires_at=expires,
                )

        async with user_session(api_engine, owner) as enable_session:
            await enable_mutations(
                enable_session, deployment_generation=generation, expected_revision=2
            )
            source_at = (await enable_session.execute("SELECT clock_timestamp()")).scalar_one()

        async def concurrent_add(command_id: UUID) -> CatalogCommand:
            async with user_session(api_engine, owner) as add_session:
                return await request_add(
                    add_session,
                    command_id=command_id,
                    idempotency_key="f37-lifecycle-add-sol",
                    base="SOL",
                    quote="USDT",
                    expected_revision=2,
                    reason=CatalogReason.LIQUIDITY_REVIEWED,
                    evidence=_evidence(source_at),
                )

        first, replay = await asyncio.gather(concurrent_add(uuid4()), concurrent_add(uuid4()))
        assert (first.state, first.revision) == ("REQUESTED", 3)
        assert replay.id == first.id
        async with user_session(api_engine, owner) as replay_session:
            assert (
                await replay_command(
                    replay_session,
                    idempotency_key="f37-lifecycle-add-sol",
                    action=CatalogAction.ADD,
                    base="SOL",
                    quote="USDT",
                    expected_revision=2,
                    reason=CatalogReason.LIQUIDITY_REVIEWED,
                )
            ) == first
        with pytest.raises(CatalogIdempotencyConflictError):
            async with user_session(api_engine, owner) as conflict_session:
                await request_add(
                    conflict_session,
                    command_id=uuid4(),
                    idempotency_key="f37-lifecycle-add-sol",
                    base="SOL",
                    quote="USDT",
                    expected_revision=3,
                    reason=CatalogReason.LIQUIDITY_REVIEWED,
                    evidence=_evidence(source_at),
                )

        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as prepare_session:
            assert (
                await prepare(prepare_session, base="SOL", quote="USDT", expected_revision=3) == 4
            )

        # Preview bootstrap enqueues backfill; it must not certify candle readiness.
        preview = CandleSupervisor(
            market_engine, FakeCandleFeed(()), cast(RedisNotifications, None)
        )
        preview.catalog = {
            ("SOL", "USDT"): RuntimeSymbol("SOL", "USDT", "PREPARING", 4, 4, "PREPARING")
        }
        preview.series = tuple(CandleSeries("SOL", "USDT", tf) for tf in Timeframe)
        async with market_data_session(market_engine) as market_writer:
            await market_writer.execute(
                """UPDATE market_candle_feed_state
                SET lease_until=clock_timestamp()-interval '1 second'"""
            )
            preview.lease = await acquire_preview(market_writer, uuid4())
        assert preview.lease is not None
        preview.epoch = preview.lease.epoch
        await preview._bootstrap(preview.epoch)
        async with market_data_session(market_engine) as market_writer:
            await _publish_preparation_readiness(market_writer)
        async with migrator_engine.connect() as connection:
            assert (
                await connection.execute(
                    text(
                        """SELECT count(*) FROM supported_symbol_timeframe_readiness
                    WHERE base='SOL' AND candles_ready_at IS NOT NULL"""
                    )
                )
            ).scalar_one() == 0

        with pytest.raises(CatalogStateError):
            async with market_data_session(market_engine) as stale_session:
                await record_timeframe_readiness(
                    stale_session,
                    base="SOL",
                    quote="USDT",
                    catalog_revision=4,
                    timeframe=Timeframe.M1,
                    ready_at=datetime(2000, 1, 1, tzinfo=UTC),
                )

        async with market_data_session(market_engine) as market_writer:
            ready_at = await database_now(market_writer)
            await record_price_readiness(
                market_writer,
                base="SOL",
                quote="USDT",
                catalog_revision=4,
                price_at=ready_at,
            )
        async with indicator_writer_session(indicator_engine) as indicator_writer:
            for timeframe in Timeframe:
                await record_timeframe_readiness(
                    indicator_writer,
                    base="SOL",
                    quote="USDT",
                    catalog_revision=4,
                    timeframe=timeframe,
                    ready_at=ready_at,
                )

        with pytest.raises(CatalogStateError):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                started_at = datetime.now(UTC)
                await activate(
                    session,
                    base="SOL",
                    quote="USDT",
                    expected_revision=4,
                    validation_started_at=started_at,
                    evidence=_evidence(datetime.now(UTC)),
                )
        async with market_data_session(market_engine) as market_writer:
            await market_writer.execute("DELETE FROM market_candle_demand WHERE base='SOL'")
            for timeframe in Timeframe:
                await record_timeframe_readiness(
                    market_writer,
                    base="SOL",
                    quote="USDT",
                    catalog_revision=4,
                    timeframe=timeframe,
                    ready_at=await database_now(market_writer),
                )

        async with user_session(
            engine_engine, owner, role=DatabaseRole.ENGINE
        ) as activation_session:
            assert (
                await activate(
                    activation_session,
                    base="SOL",
                    quote="USDT",
                    expected_revision=4,
                    validation_started_at=ready_at - timedelta(seconds=1),
                    evidence=_evidence(ready_at),
                )
                == 5
            )

        async with market_data_session(market_engine) as demand_session:
            window = initial_window(Timeframe.M1, datetime.now(UTC))
            await demand_session.execute(
                """INSERT INTO market_candle_demand(
                source,base,quote,timeframe,desired_start,desired_end,requested_at)
                VALUES('primary_spot','SOL','USDT','1m',:start,:end,clock_timestamp())""",
                {"start": window.start, "end": window.end},
            )
            claimed = await claim_next(demand_session, "f37-removal-race")
        assert claimed is not None and (claimed.base, claimed.quote) == ("SOL", "USDT")

        async with user_session(api_engine, owner) as remove_session:
            active = await read_catalog(remove_session)
            assert active.snapshot.supports("SOL", "USDT")
            removed = await request_remove(
                remove_session,
                command_id=uuid4(),
                idempotency_key="f37-lifecycle-remove-sol",
                base="SOL",
                quote="USDT",
                expected_revision=5,
                reason=CatalogReason.RISK_REVIEW,
            )
            assert (removed.state, removed.revision) == ("SUCCEEDED", 6)

        async with presented_session(engine_engine, role=DatabaseRole.ENGINE) as proof_session:
            assert await reconcile_removal_effects(proof_session) == 1
            effect = (
                await proof_session.execute(
                    "SELECT status,attempts,orders_unresolved,error_code "
                    "FROM supported_symbol_effects WHERE event_revision=6"
                )
            ).one()
            assert effect == ("PARTIAL", 1, 0, "DEPENDENCY_UNAVAILABLE")
            before_proof = await runtime_symbols(proof_session)
            assert any(row.base == "SOL" and row.mode == "MAINTENANCE" for row in before_proof)
            assert await reconcile_maintenance_proofs(proof_session) == 1
            assert not any(row.base == "SOL" for row in await runtime_symbols(proof_session))

        with pytest.raises(StaleClaimError):
            async with market_data_session(market_engine) as market_session:
                await lock_claim(market_session, claimed)

        async with user_session(api_engine, owner) as readd_session:
            readded = await request_add(
                readd_session,
                command_id=uuid4(),
                idempotency_key="f37-lifecycle-readd-sol",
                base="SOL",
                quote="USDT",
                expected_revision=6,
                reason=CatalogReason.LIQUIDITY_REVIEWED,
                evidence=_evidence(ready_at),
            )
            assert (readded.state, readded.revision) == ("REQUESTED", 7)
            assert not (await read_catalog(readd_session)).snapshot.supports("SOL", "USDT")

        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as fence_session:
            fence = await lock_pair_catalog(fence_session, PositionPair("SOL", "USDT"))
            assert fence.latest_removed_revision == 6
            assert fence.latest_removed_revision > 5
            assert not fence.latest_removed_revision > 7

        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as failure_session:
            assert (
                await prepare(failure_session, base="SOL", quote="USDT", expected_revision=7) == 8
            )
            assert (
                await fail_preparation(
                    failure_session,
                    base="SOL",
                    quote="USDT",
                    expected_revision=8,
                    failure_code="VENUE_PROTOCOL",
                )
                == 9
            )

        async with migrator_engine.connect() as connection:
            await connection.execute(
                text("SELECT set_config('tiewtrade.current_user_id',:owner,true)"),
                {"owner": str(owner)},
            )
            statuses = list(
                cast(
                    Sequence[str],
                    (
                        await connection.execute(
                            text(
                                "SELECT status FROM supported_symbol_events WHERE base='SOL' "
                                "ORDER BY revision"
                            )
                        )
                    )
                    .scalars()
                    .all(),
                )
            )
            failure_audit = (
                await connection.execute(
                    text(
                        "SELECT actor_kind,actor_id,outcome,failure_code FROM audit_events "
                        "WHERE owner_user_id=:owner AND action='CATALOG_PREPARATION_REJECTED'"
                    ),
                    {"owner": owner},
                )
            ).one()
        assert statuses == [
            "REQUESTED",
            "PREPARING",
            "ACTIVE",
            "REMOVED",
            "REQUESTED",
            "PREPARING",
            "FAILED",
        ]
        assert failure_audit == ("SYSTEM", None, "FAILED", "VENUE_PROTOCOL")
    finally:
        await market_engine.dispose()
        await indicator_engine.dispose()
        async with migrator_engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('tiewtrade.current_user_id',:owner,true)"),
                {"owner": str(owner)},
            )
            protected_tables = (
                "audit_events",
                "platform_memberships",
                "supported_symbol_constraint_snapshots",
                "supported_symbol_events",
                "supported_symbol_fences",
                "supported_symbol_maintenance_proofs",
                "supported_symbol_registry",
            )
            for table in protected_tables:
                await connection.execute(text(f"ALTER TABLE {table} DISABLE TRIGGER USER"))
            await connection.execute(
                text("ALTER TABLE platform_memberships NO FORCE ROW LEVEL SECURITY")
            )
            try:
                await connection.execute(
                    text(
                        "DELETE FROM supported_symbol_timeframe_readiness "
                        "WHERE base='SOL' AND quote='USDT'"
                    )
                )
                await connection.execute(
                    text(
                        "DELETE FROM supported_symbol_effects WHERE event_revision IN "
                        "(SELECT revision FROM supported_symbol_events "
                        "WHERE base='SOL' AND quote='USDT')"
                    )
                )
                await connection.execute(
                    text(
                        "DELETE FROM supported_symbol_maintenance_proofs "
                        "WHERE base='SOL' AND quote='USDT'"
                    )
                )
                await connection.execute(
                    text("DELETE FROM supported_symbol_readiness WHERE base='SOL' AND quote='USDT'")
                )
                await connection.execute(
                    text("DELETE FROM market_candle_demand WHERE base='SOL' AND quote='USDT'")
                )
                await connection.execute(
                    text("DELETE FROM supported_symbol_fences WHERE base='SOL' AND quote='USDT'")
                )
                await connection.execute(
                    text("DELETE FROM supported_symbol_events WHERE base='SOL' AND quote='USDT'")
                )
                await connection.execute(
                    text("DELETE FROM supported_symbol_commands WHERE requested_by=:owner"),
                    {"owner": owner},
                )
                await connection.execute(
                    text(
                        "DELETE FROM supported_symbol_constraint_snapshots "
                        "WHERE base='SOL' AND quote='USDT'"
                    )
                )
                await connection.execute(
                    text("DELETE FROM supported_symbol_registry WHERE base='SOL' AND quote='USDT'")
                )
                await connection.execute(
                    text("DELETE FROM audit_events WHERE owner_user_id=:owner"),
                    {"owner": owner},
                )
                await connection.execute(
                    text("DELETE FROM platform_memberships WHERE user_id=:owner"),
                    {"owner": owner},
                )
                await connection.execute(text("DELETE FROM catalog_protocol_heartbeats"))
                await connection.execute(
                    text(
                        "UPDATE supported_symbol_catalog_control SET current_revision=2,"
                        "mutations_enabled=false,deployment_generation=NULL WHERE id=1"
                    )
                )
            finally:
                await connection.execute(
                    text("ALTER TABLE platform_memberships FORCE ROW LEVEL SECURITY")
                )
                for table in reversed(protected_tables):
                    await connection.execute(text(f"ALTER TABLE {table} ENABLE TRIGGER USER"))


def _evidence(observed_at: datetime) -> ConstraintEvidence:
    return ConstraintEvidence(
        venue_symbol="SOLUSDT",
        observed_at=observed_at,
        source_document='{"symbol":"SOLUSDT","status":"TRADING"}',
        digest="a" * 64,
    )
