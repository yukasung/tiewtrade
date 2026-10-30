"""Proven source adoption is atomic, idempotent, owner-bound and fences old writers."""

import asyncio
import subprocess
import sys
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import OrderConflictError
from tiewtrade.core.positions import (
    ExecutionFact,
    ExecutionSide,
    PositionAvailability,
    PositionPair,
)
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.errors import InfraError
from tiewtrade.infra.market_data.order_book_codec import canonical
from tiewtrade.infra.paper_orders import initialization
from tiewtrade.infra.paper_orders.initialization import initialize_order_source
from tiewtrade.infra.paper_orders.records import OrderSourceInitialization
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.positions import (
    PositionEventKind,
    apply_position_event,
    initialize_position_source,
    read_position_snapshot,
)


@pytest.fixture(name="wallet")
def legacy_wallet_fixture(legacy_wallet: PaperWalletSnapshot) -> PaperWalletSnapshot:
    """Run source-adoption tests against a pre-F-15 wallet."""
    return legacy_wallet


async def test_concurrent_adoption_is_one_receipt_revision_and_audit(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async def adopt() -> OrderSourceInitialization:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            return await initialize_order_source(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                initialization_id=uuid4(),
            )

    first, second = await asyncio.gather(adopt(), adopt())
    assert first == second
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        after = await get_wallet(session)
        assert after is not None and after.balance == wallet.balance
        assert after.revision == wallet.revision + 1
        assert after.reset_available and after.reset_reason is None
        position = await read_position_snapshot(session, wallet.episode_id)
        assert position is not None and position.activity.availability is PositionAvailability.READY
        assert position.positions == ()
        row = (
            await session.execute(
                "SELECT * FROM paper_order_activity WHERE episode_id=:episode",
                {"episode": wallet.episode_id},
            )
        ).one()
        assert row.availability == "READY" and row.source_sequence == 0 and row.revision == 1
        assert row.source_proof == first.source_proof
        count = (
            await session.execute(
                """SELECT count(*) FROM audit_events WHERE action='PAPER_ORDER_SOURCE_INITIALIZED'
            AND subject_id=:subject""",
                {"subject": str(wallet.episode_id)},
            )
        ).scalar_one()
        assert count == 1


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE paper_position_activity SET source_proof=repeat('f',64) WHERE episode_id=:episode",
        "UPDATE paper_position_activity SET availability='CONFLICTED', "
        "observed_at=clock_timestamp(),failure_code='INJECTED_CONFLICT' "
        "WHERE episode_id=:episode",
        "UPDATE paper_order_activity SET source_proof=repeat('f',64) WHERE episode_id=:episode",
        "UPDATE paper_order_activity SET availability='CONFLICTED', "
        "observed_at=clock_timestamp(),failure_code='INJECTED_CONFLICT' "
        "WHERE episode_id=:episode",
    ],
)
async def test_corrupt_or_conflicted_source_never_reports_reset_ready(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    mutation: str,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_order_source(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            initialization_id=uuid4(),
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        ready = await get_wallet(session)
        assert ready is not None and ready.reset_available
    table = (
        "paper_position_activity"
        if "paper_position_activity" in mutation
        else "paper_order_activity"
    )
    async with migrator_engine.begin() as connection:
        await connection.execute(text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
        await connection.execute(text(f"ALTER TABLE {table} DISABLE TRIGGER USER"))
        await connection.execute(text(mutation), {"episode": wallet.episode_id})
        await connection.execute(text(f"ALTER TABLE {table} ENABLE TRIGGER USER"))
        await connection.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        unsafe = await get_wallet(session)
    assert unsafe is not None
    assert not unsafe.reset_available and unsafe.reset_reason == "ACTIVITY_UNKNOWN"


async def test_failed_audit_rolls_back_all_sources_and_can_retry(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("injected initialization audit failure")

    with monkeypatch.context() as patch:
        patch.setattr(initialization, "record_event", fail)
        with pytest.raises(RuntimeError, match="injected initialization"):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await initialize_order_source(
                    session,
                    wallet_id=wallet.wallet_id,
                    episode_id=wallet.episode_id,
                    initialization_id=uuid4(),
                )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert (
            await session.execute(
                "SELECT count(*) FROM paper_order_initializations WHERE episode_id=:episode",
                {"episode": wallet.episode_id},
            )
        ).scalar_one() == 0
        position = await read_position_snapshot(session, wallet.episode_id)
        assert (
            position is not None and position.activity.availability is PositionAvailability.UNKNOWN
        )
        after = await get_wallet(session)
        assert after is not None and after.revision == wallet.revision
        assert not after.reset_available and after.reset_reason == "ACTIVITY_UNKNOWN"
        await initialize_order_source(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            initialization_id=uuid4(),
        )


@pytest.mark.parametrize("wrong_owner", [True, False])
async def test_owner_and_wallet_identity_required(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    wrong_owner: bool,
) -> None:
    async with user_session(
        engine_engine, uuid4() if wrong_owner else owner, role=DatabaseRole.ENGINE
    ) as session:
        with pytest.raises(OrderConflictError):
            await initialize_order_source(
                session,
                wallet_id=wallet.wallet_id if wrong_owner else uuid4(),
                episode_id=wallet.episode_id,
                initialization_id=uuid4(),
            )


async def test_preexisting_position_history_is_not_adopted_as_empty(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_position_source(session, wallet.episode_id, uuid4(), "1" * 64)
        await apply_position_event(
            session,
            wallet.episode_id,
            uuid4(),
            PositionEventKind.RECORD,
            ExecutionFact(
                uuid4(),
                PositionPair("BTC", "USDT"),
                ExecutionSide.BUY,
                Quantity.of(1, "BTC"),
                Money.of(100, "USDT"),
                None,
                1,
                datetime.now(UTC),
            ),
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        with pytest.raises(OrderConflictError):
            await initialize_order_source(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                initialization_id=uuid4(),
            )


async def test_old_writer_cannot_mutate_managed_episode_and_marker_does_not_leak(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_order_source(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            initialization_id=uuid4(),
        )
    for statement in (
        "UPDATE paper_wallet_state SET revision=revision+1 WHERE active_episode_id=:episode",
        "UPDATE paper_position_activity SET revision=revision+1 WHERE episode_id=:episode",
    ):
        with pytest.raises(InfraError, match="SQLSTATE TT015"):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await session.execute(statement, {"episode": wallet.episode_id})
    with pytest.raises(DBAPIError) as failure:
        async with migrator_engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('tiewtrade.current_user_id',:owner,true)"),
                {"owner": str(owner)},
            )
            await connection.execute(
                text("""INSERT INTO paper_wallet_episode_closures
                (episode_id,wallet_id,user_id,reset_command_id)
                VALUES(:episode,:wallet,:user,:command)"""),
                {
                    "episode": wallet.episode_id,
                    "wallet": wallet.wallet_id,
                    "user": owner,
                    "command": uuid4(),
                },
            )
    assert getattr(failure.value.orig, "sqlstate", None) == "TT015"
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        with pytest.raises(InfraError, match="SQLSTATE TT015"):
            await apply_position_event(
                session,
                wallet.episode_id,
                uuid4(),
                PositionEventKind.RECORD,
                ExecutionFact(
                    uuid4(),
                    PositionPair("BTC", "USDT"),
                    ExecutionSide.BUY,
                    Quantity.of(1, "BTC"),
                    Money.of(100, "USDT"),
                    None,
                    1,
                    datetime.now(UTC),
                ),
            )


@pytest.mark.parametrize("invalid", ["null_proof", "null_episode", "extra_field", "bad_id"])
async def test_database_rejects_invalid_source_audit_shape(
    engine_engine: AsyncEngine,
    owner: UUID,
    invalid: str,
) -> None:
    episode = uuid4()
    details: dict[str, object] = {
        "episode_id": str(episode),
        "initialization_id": str(uuid4()),
        "source_proof": "a" * 64,
    }
    if invalid == "null_proof":
        details["source_proof"] = None
    elif invalid == "null_episode":
        details["episode_id"] = None
    elif invalid == "extra_field":
        details["note"] = "undeclared field"
    else:
        details["initialization_id"] = "not-an-identifier"
    with pytest.raises(InfraError, match="SQLSTATE 23514"):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                """INSERT INTO audit_events
              (id,owner_user_id,actor_kind,action,subject_kind,subject_id,mode,outcome,details)
              VALUES(:id,:owner,'SYSTEM','PAPER_ORDER_SOURCE_INITIALIZED','PAPER_ORDER_ACTIVITY',
                     :subject,'PAPER','SUCCEEDED',CAST(:details AS jsonb))""",
                {
                    "id": uuid4(),
                    "owner": owner,
                    "subject": str(episode),
                    "details": canonical(details),
                },
            )


async def test_managed_history_refuses_fence_downgrade_and_keeps_force_rls(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_order_source(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            initialization_id=uuid4(),
        )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from alembic.config import Config; from alembic import command; "
            "c=Config(); c.set_main_option('script_location','migrations'); "
            "command.downgrade(c,'0034')",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert (
        "managed Paper episodes prevent writer fence downgrade" in result.stderr
        or "matching decision history prevents downgrade" in result.stderr
        or "Paper reset audit history prevents downgrade" in result.stderr
        or "historical Paper order revisions prevent downgrade" in result.stderr
        or "supported-symbol runtime history prevents downgrade" in result.stderr
        or "manual order request history prevents downgrade" in result.stderr
        or "manual order admission history prevents downgrade" in result.stderr
        or "unconfigured financial boundary history prevents downgrade" in result.stderr
        or "active risk writer protocol prevents downgrade" in result.stderr
        or "risk evaluation request history prevents downgrade" in result.stderr
        or "risk lifecycle history prevents downgrade" in result.stderr
        or "risk queued cutoff history prevents downgrade" in result.stderr
        or "risk stop history prevents downgrade" in result.stderr
        or "versioned risk financial history prevents downgrade" in result.stderr
        or "risk protocol history prevents downgrade" in result.stderr
        or "risk boundary history prevents downgrade" in result.stderr
        or "risk limit history prevents downgrade" in result.stderr
    )
    async with migrator_engine.connect() as connection:
        assert (
            await connection.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one() in {
            "0035",
            "0036",
            "0037",
            "0038",
            "0040",
            "0041",
            "0042",
            "0043",
            "0044",
            "0045",
            "0046",
            "0047",
            "0048",
            "0049",
            "0050",
            "0051",
            "0052",
            "0053",
            "0054",
        }
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert (
            await session.execute("""SELECT bool_and(relforcerowsecurity) FROM pg_class
            WHERE oid IN ('paper_order_initializations'::regclass,
              'paper_order_activity'::regclass,'paper_order_projections'::regclass,
              'paper_reservations'::regclass)""")
        ).scalar_one()
    restored = subprocess.run(
        [
            sys.executable,
            "-c",
            "from alembic.config import Config; from alembic import command; "
            "c=Config(); c.set_main_option('script_location','migrations'); "
            "command.upgrade(c,'head')",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert restored.returncode == 0, restored.stderr


async def test_initialization_receipt_is_private_and_append_only_even_for_owner(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_order_source(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            initialization_id=uuid4(),
        )
    async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
        assert (
            await session.execute("SELECT count(*) FROM paper_order_initializations")
        ).scalar_one() == 0
    for statement in (
        "UPDATE paper_order_initializations SET baseline='{}'::jsonb",
        "DELETE FROM paper_order_initializations",
        "TRUNCATE paper_order_initializations CASCADE",
    ):
        with pytest.raises(DBAPIError) as failure:
            async with migrator_engine.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('tiewtrade.current_user_id',:owner,true)"),
                    {"owner": str(owner)},
                )
                await connection.execute(text(statement))
        assert getattr(failure.value.orig, "sqlstate", None) == "TT001"
