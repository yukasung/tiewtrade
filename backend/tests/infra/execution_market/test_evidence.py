"""Evidence survives the public cache; owner/partition/immutability are DB-enforced."""

import asyncio
import hashlib
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Result
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_storage import prepared
from tests.order_book_fixtures import capability, snapshot
from tiewtrade.core.order_book import BookState
from tiewtrade.core.orders import OrderConflictError, SimulationProfile
from tiewtrade.core.positions import PositionPair
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.errors import InfraError, NotPermittedError
from tiewtrade.infra.db.session import UserSession, market_data_session, scan_session_bypassing_rls
from tiewtrade.infra.market_data.order_book_codec import input_payload
from tiewtrade.infra.market_data.order_book_storage import (
    ExecutionMetadata,
    StoredExecutionInput,
    invalidate_book,
    metadata_payload,
    publish_input,
    read_inputs,
)
from tiewtrade.infra.paper_orders.records import SavedExecutionInput
from tiewtrade.infra.paper_orders.storage import (
    append_execution_input,
    pin_execution_profile,
    read_execution_inputs,
)
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot


def source_record() -> StoredExecutionInput:
    at = datetime.now(UTC)
    source = snapshot(at)
    market = BookState(
        PositionPair("BTC", "USDT"), 1, 1, at, at, source.bids, source.asks, True, True
    )
    cap = capability(at)
    metadata = ExecutionMetadata(cap.market, cap.limit, at, cap.source_document)
    digest = hashlib.sha256(
        (input_payload(market) + "\n" + metadata_payload(metadata)).encode()
    ).hexdigest()
    return StoredExecutionInput(market, metadata, digest)


async def test_projection_cannot_reference_another_orders_event(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    orders, events = (uuid4(), uuid4()), (uuid4(), uuid4())
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await pin_execution_profile(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            profile=SimulationProfile(),
        )
        for sequence, (order, event) in enumerate(zip(orders, events, strict=True), 1):
            params = {
                "command": uuid4(),
                "order": order,
                "event": event,
                "user": owner,
                "wallet": wallet.wallet_id,
                "episode": wallet.episode_id,
                "sequence": sequence,
                "key": uuid4(),
            }
            await session.execute(
                """INSERT INTO paper_order_commands
                (id,user_id,wallet_id,episode_id,action,idempotency_key,order_id,request_fingerprint,payload)
                VALUES(:command,:user,:wallet,:episode,'NEW',:key,:order,repeat('0',64),'{}')""",
                params,
            )
            await session.execute(
                """INSERT INTO paper_orders
                (id,user_id,wallet_id,episode_id,command_id,sequence,base,quote,origin,side,kind,
                 budget,accepted_at,constraints)
                VALUES(:order,:user,:wallet,:episode,:command,:sequence,'BTC','USDT','MANUAL',
                       'BUY','MARKET',100,clock_timestamp(),'{}')""",
                params,
            )
            await session.execute(
                """INSERT INTO paper_order_events
                (id,order_id,user_id,episode_id,base,quote,sequence,event_kind,payload,occurred_at)
                VALUES(:event,:order,:user,:episode,'BTC','USDT',1,'ACCEPTED','{}',clock_timestamp())""",
                params,
            )
    for event, valid in ((events[1], False), (events[0], True)):

        async def insert_projection(selected_event: UUID) -> None:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await session.execute(
                    """INSERT INTO paper_order_projections
                    (order_id,user_id,episode_id,base,quote,status,filled_quantity,spent,resting,
                     revision,last_event_id)
                    VALUES(:order,:user,:episode,'BTC','USDT','ACCEPTED',0,0,false,1,:event)""",
                    {
                        "order": orders[0],
                        "user": owner,
                        "episode": wallet.episode_id,
                        "event": selected_event,
                    },
                )

        if valid:
            await insert_projection(event)
        else:
            with pytest.raises(InfraError, match="SQLSTATE 23503"):
                await insert_projection(event)


async def test_owner_evidence_atomic_replay_and_cross_owner_isolation(
    engine_engine: AsyncEngine,
    owner: UUID,
    legacy_wallet: PaperWalletSnapshot,
) -> None:
    wallet = legacy_wallet
    record = source_record()
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await pin_execution_profile(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            profile=SimulationProfile(),
        )
        assert (
            await session.execute(
                """SELECT availability FROM paper_order_activity
          WHERE episode_id=:episode""",
                {"episode": wallet.episode_id},
            )
        ).scalar_one_or_none() in (None, "UNKNOWN")

    async def append(identity: UUID) -> SavedExecutionInput:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            return await append_execution_input(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                evidence_id=identity,
                record=record,
            )

    first, second = await asyncio.gather(append(uuid4()), append(uuid4()))
    assert first == second and first.record == record
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        rows = await read_execution_inputs(
            session, episode_id=wallet.episode_id, pair=record.market.pair
        )
        assert rows == (first,)
        count = (
            await session.execute(
                "SELECT count(*) FROM paper_execution_input_keys WHERE episode_id=:episode",
                {"episode": wallet.episode_id},
            )
        ).scalar_one()
        assert count == 1
        with pytest.raises(OrderConflictError):
            await append_execution_input(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                evidence_id=uuid4(),
                record=replace(record, digest="0" * 64),
            )
    async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
        assert (
            await read_execution_inputs(
                session, episode_id=wallet.episode_id, pair=record.market.pair
            )
            == ()
        )


async def test_rebase_evidence_preserves_and_authenticates_public_source(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    original = source_record()
    assert isinstance(original.market, BookState)
    source_market = replace(original.market, rebase=False)
    record = StoredExecutionInput(
        source_market,
        original.metadata,
        hashlib.sha256(
            (input_payload(source_market) + "\n" + metadata_payload(original.metadata)).encode()
        ).hexdigest(),
    )
    decision = replace(source_market, rebase=True)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await pin_execution_profile(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            profile=SimulationProfile(),
        )
        saved = await append_execution_input(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            evidence_id=uuid4(),
            record=record,
            decision_market=decision,
        )
        assert saved.record.market == decision
        replayed = await read_execution_inputs(
            session, episode_id=wallet.episode_id, pair=decision.pair
        )
        assert replayed == (saved,)
        with pytest.raises(OrderConflictError, match="changed source content"):
            await append_execution_input(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                evidence_id=uuid4(),
                record=record,
                decision_market=replace(decision, ready=False),
            )


async def test_evidence_parent_and_child_reject_privileged_mutation(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    record = source_record()
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await pin_execution_profile(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            profile=SimulationProfile(),
        )
        saved = await append_execution_input(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            evidence_id=uuid4(),
            record=record,
        )
    child = "paper_execution_inputs_" + saved.recorded_at.astimezone(UTC).strftime("%Y%m%d")
    for table in ("paper_execution_inputs", child):
        for mutation in (
            f"UPDATE {table} SET digest=repeat('0',64)",
            f"DELETE FROM {table}",
            f"TRUNCATE {table} CASCADE",
        ):
            with pytest.raises(DBAPIError) as failure:
                async with migrator_engine.begin() as connection:
                    await connection.execute(
                        text("SELECT set_config('tiewtrade.current_user_id',:owner,true)"),
                        {"owner": str(owner)},
                    )
                    await connection.execute(text(mutation))
            assert getattr(failure.value.orig, "sqlstate", None) == "TT001"
        async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
            assert (await session.execute(f"SELECT count(*) FROM {table}")).scalar_one() == 0
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert (
            len(
                await read_execution_inputs(
                    session, episode_id=wallet.episode_id, pair=record.market.pair
                )
            )
            == 1
        )


async def test_api_market_data_and_scanner_cannot_read_evidence_or_financial_payload(
    api_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
) -> None:
    async with user_session(api_engine, owner) as session:
        with pytest.raises(NotPermittedError):
            await session.execute("SELECT * FROM paper_execution_inputs")
    async with scan_session_bypassing_rls(scan_engine) as session:
        with pytest.raises(NotPermittedError):
            await session.execute("SELECT * FROM paper_order_commands")
    async with scan_session_bypassing_rls(scan_engine) as session:
        await session.execute("SELECT command_id,user_id,next_attempt_at FROM paper_order_dispatch")
    async with scan_session_bypassing_rls(scan_engine) as session:
        with pytest.raises(NotPermittedError):
            await session.execute("SELECT worker FROM paper_order_dispatch")
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(engine) as session:
            with pytest.raises(NotPermittedError):
                await session.execute("SELECT * FROM paper_execution_inputs")
    finally:
        await engine.dispose()


async def test_partition_provisioning_applies_owner_policy_and_grants(
    migrator_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    legacy_wallet: PaperWalletSnapshot,
) -> None:
    wallet = legacy_wallet
    target = datetime.now(UTC).date() + timedelta(days=2)
    name = "paper_execution_inputs_" + target.strftime("%Y%m%d")
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text("SELECT create_paper_execution_input_partition(:day)"), {"day": target}
        )
        row = (
            (
                await connection.execute(
                    text("""SELECT c.relrowsecurity,c.relforcerowsecurity,
          has_table_privilege('tiewtrade_engine',c.oid,'INSERT') can_insert,
          has_table_privilege('tiewtrade_api',c.oid,'SELECT') api_read
          FROM pg_class c WHERE c.relname=:name"""),
                    {"name": name},
                )
            )
            .mappings()
            .one()
        )
        assert (
            row["relrowsecurity"]
            and row["relforcerowsecurity"]
            and row["can_insert"]
            and not row["api_read"]
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        with pytest.raises(NotPermittedError):
            await session.execute(
                """INSERT INTO paper_execution_profiles
              (episode_id,wallet_id,user_id,fee_version,model_version)
              VALUES(:episode,:wallet,:owner,'PAPER_STANDARD_V1','PAPER_DEPTH_SHADOW_V1')""",
                {"episode": wallet.episode_id, "wallet": wallet.wallet_id, "owner": uuid4()},
            )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        with pytest.raises(InfraError, match="SQLSTATE 23503"):
            await session.execute(
                """INSERT INTO paper_execution_profiles
              (episode_id,wallet_id,user_id,fee_version,model_version)
              VALUES(:episode,:wallet,:owner,'PAPER_STANDARD_V1','PAPER_DEPTH_SHADOW_V1')""",
                {"episode": wallet.episode_id, "wallet": uuid4(), "owner": owner},
            )


async def test_evidence_and_registry_rollback_together_then_retry(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = source_record()
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await pin_execution_profile(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            profile=SimulationProfile(),
        )
    original = UserSession.execute

    async def fail_registry(
        session: UserSession,
        statement: str,
        parameters: Mapping[str, object] | None = None,
    ) -> Result[Any]:
        if "INSERT INTO paper_execution_input_keys" in statement:
            raise RuntimeError("injected registry failure")
        return await original(session, statement, parameters)

    identity = uuid4()
    with monkeypatch.context() as scoped:
        scoped.setattr(UserSession, "execute", fail_registry)
        with pytest.raises(RuntimeError, match="injected registry failure"):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await append_execution_input(
                    session,
                    wallet_id=wallet.wallet_id,
                    episode_id=wallet.episode_id,
                    evidence_id=identity,
                    record=record,
                )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert (
            await read_execution_inputs(
                session, episode_id=wallet.episode_id, pair=record.market.pair
            )
            == ()
        )
        saved = await append_execution_input(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            evidence_id=identity,
            record=record,
        )
        assert saved.evidence_id == identity


async def test_private_evidence_survives_public_cache_replacement(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        lease, book, metadata = await prepared(engine)
        async with market_data_session(engine) as session:
            await publish_input(session, lease, book, metadata)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            record = (await read_inputs(session, book.pair, after=book.input_id - 1))[0]
            await pin_execution_profile(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                profile=SimulationProfile(),
            )
            saved = await append_execution_input(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                evidence_id=uuid4(),
                record=record,
            )
        async with market_data_session(engine) as session:
            await invalidate_book(session, lease, "CACHE_REPLACED")
            await session.execute(
                """UPDATE market_execution_buffer SET payload='{}'::jsonb,digest=repeat('0',64)
              WHERE base='BTC' AND input_id=:input""",
                {"input": book.input_id},
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert await read_execution_inputs(
                session, episode_id=wallet.episode_id, pair=book.pair
            ) == (saved,)
    finally:
        await engine.dispose()
