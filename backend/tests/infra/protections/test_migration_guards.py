"""Rollback guards on a fresh database; every seeded F-17 row is rolled back."""

from collections.abc import AsyncIterator
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from tests.infra.db.test_migrations import BACKEND_ROOT
from tests.infra.execution_market.test_dispatch import intent
from tests.infra.manual_orders.test_bridge import select_use
from tests.infra.protections.test_lifecycle import buy
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import BaseSize, OrderOrigin, OrderScope, TradingMode
from tiewtrade.core.positions import ExecutionSide, PositionPair
from tiewtrade.core.protections import Protection, ProtectionPrices, ProtectionState
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.market_data.order_book_codec import canonical
from tiewtrade.infra.paper_orders.requests import admit_new_request
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.positions.views import held_and_reserved
from tiewtrade.infra.protections.codec import encode

pytestmark = pytest.mark.isolated_migration

TABLES = (
    "paper_protection_requests",
    "paper_protection_results",
    "paper_protections",
    "paper_protection_events",
    "paper_protection_exits",
    "paper_protection_exit_progress",
    "paper_protection_request_progress",
    "paper_order_requests",
    "audit_events",
    "paper_wallet_ledger",
)


@pytest.fixture
async def rollback_connection(migrator_engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    async with migrator_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            await transaction.rollback()


async def set_owner(connection: AsyncConnection, owner: UUID) -> None:
    await connection.execute(
        text("SELECT set_config('tiewtrade.current_user_id',:owner,true)"),
        {"owner": str(owner)},
    )


async def snapshot(connection: AsyncConnection) -> tuple[tuple[str, str], ...]:
    contents = []
    for table in (*TABLES, "paper_protection_protocol"):
        digest: str = (
            await connection.execute(
                text(f"""SELECT md5(coalesce(jsonb_agg(to_jsonb(r)
                    ORDER BY to_jsonb(r)::text),'[]'::jsonb)::text) FROM {table} r""")
            )
        ).scalar_one()
        contents.append((table, str(digest)))
    return tuple(contents)


async def forced_rls(connection: AsyncConnection) -> tuple[tuple[str, bool], ...]:
    rows = (
        await connection.execute(
            text("""SELECT relname,relforcerowsecurity FROM pg_class
                WHERE relnamespace='public'::regnamespace AND relname=ANY(:names)
                ORDER BY relname"""),
            {"names": list(TABLES)},
        )
    ).all()
    return tuple((str(row.relname), bool(row.relforcerowsecurity)) for row in rows)


def downgrade(connection: Connection, revision: str) -> None:
    script = ScriptDirectory.from_config(Config(str(BACKEND_ROOT / "alembic.ini")))
    migration = script.get_revision(revision)
    assert migration is not None
    with Operations.context(MigrationContext.configure(connection)):
        migration.module.downgrade()


@pytest.mark.parametrize("revision", ["0063", "0064"])
@pytest.mark.parametrize(
    "history", ["protocol", "request", "progress", "canceled", "bracket", "allocations", "audit"]
)
async def test_downgrade_refuses_each_protection_boundary_and_restores_rls(
    api_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    rollback_connection: AsyncConnection,
    revision: str,
    history: str,
) -> None:
    await select_use(api_engine, owner)
    # Ordinary requests are a permitted baseline. Only their F-17 attachments
    # should block rollback; this also proves ordinary history is preserved.
    async with user_session(api_engine, owner) as session:
        ordinary_buy = await admit_new_request(
            session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
        )
        ordinary_sell = await admit_new_request(
            session,
            wallet_id=wallet.wallet_id,
            intent=replace(
                intent(owner, wallet.episode_id),
                side=ExecutionSide.SELL,
                size=BaseSize(Quantity.of("0.1", "BTC")),
            ),
        )
    connection = rollback_connection
    await set_owner(connection, owner)
    group_id, request_id, event_id = uuid4(), uuid4(), uuid4()
    params = {
        "owner": owner,
        "wallet": wallet.wallet_id,
        "episode": wallet.episode_id,
        "group": group_id,
        "request": request_id,
        "event": event_id,
    }
    if history == "protocol":
        await connection.execute(text("UPDATE paper_protection_protocol SET enabled=true"))
        expected = "active protection protocol prevents downgrade"
    elif history in ("request", "progress"):
        await connection.execute(
            text("""INSERT INTO paper_protection_requests
                (id,user_id,wallet_id,episode_id,protection_id,action,idempotency_key,fingerprint,payload)
                VALUES(:request,:owner,:wallet,:episode,:group,'CREATE',:request,
                       repeat('0',64),'{}'::jsonb)"""),
            params,
        )
        if history == "progress":
            await connection.execute(
                text("""INSERT INTO paper_protection_request_progress
                    (request_id,user_id,episode_id,attempt,next_attempt_at)
                    VALUES(:request,:owner,:episode,2,clock_timestamp()+interval '1 second')"""),
                params,
            )
        expected = "protection history prevents downgrade"
    elif history == "canceled":
        value = Protection(
            group_id,
            OrderScope(owner, UUID(str(wallet.episode_id)), TradingMode.PAPER),
            OrderOrigin.MANUAL,
            ProtectionPrices(PositionPair("BTC", "USDT"), None, Money.of("90", "USDT")),
            Quantity.of(0, "BTC"),
            ProtectionState.CANCELED,
        )
        document = canonical(encode(value))
        await connection.execute(
            text("""INSERT INTO paper_protections
                (id,user_id,wallet_id,episode_id,base,quote,state,revision,quantity,document)
                VALUES(:group,:owner,:wallet,:episode,'BTC','USDT','CANCELED',1,0,
                       CAST(:document AS jsonb))"""),
            {**params, "document": document},
        )
        await connection.execute(
            text("""INSERT INTO paper_protection_events
                (id,user_id,episode_id,protection_id,revision,kind,document)
                VALUES(:event,:owner,:episode,:group,1,'CANCEL',CAST(:document AS jsonb))"""),
            {**params, "document": document},
        )
        expected = "protection history prevents downgrade"
    elif history in ("bracket", "allocations"):
        bracket = canonical({"tp": "110", "sl": "90"}) if history == "bracket" else None
        allocations = canonical(
            [{"protection_id": str(group_id), "quantity": "0.1", "expected_revision": 1}]
            if history == "allocations"
            else []
        )
        await connection.execute(
            text("""INSERT INTO paper_order_requests
                (id,user_id,wallet_id,episode_id,order_id,action,idempotency_key,request_fingerprint,
                 admitted_catalog_revision,payload,protection,protection_allocations)
                SELECT :request,user_id,wallet_id,episode_id,:group,action,:event,
                  request_fingerprint,admitted_catalog_revision,
                  payload || jsonb_build_object('order_id',CAST(CAST(:group AS uuid) AS text),
                    'key',CAST(CAST(:event AS uuid) AS text)),
                  CAST(:bracket AS jsonb),CAST(:allocations AS jsonb)
                FROM paper_order_requests WHERE id=:source"""),
            {
                **params,
                "source": ordinary_buy.request_id
                if history == "bracket"
                else ordinary_sell.request_id,
                "bracket": bracket,
                "allocations": allocations,
            },
        )
        expected = "protection intent or audit history prevents downgrade"
    else:
        details = canonical(
            {
                "episode_id": str(wallet.episode_id),
                "protection_id": str(group_id),
                "event_id": str(event_id),
                "revision": 1,
                "kind": "CREATE",
            }
        )
        await connection.execute(
            text("""INSERT INTO audit_events
                (id,owner_user_id,actor_kind,actor_id,action,subject_kind,subject_id,mode,outcome,details)
                VALUES(:event,:owner,'SYSTEM',NULL,'PROTECTION_EVENT','PAPER_ORDER_ACTIVITY',
                       :subject,'PAPER','SUCCEEDED',CAST(:details AS jsonb))"""),
            {**params, "subject": str(wallet.episode_id), "details": details},
        )
        expected = "protection intent or audit history prevents downgrade"
    # Flush deferred consistency checks as a committed fixture would, while
    # keeping the fixture inside the outer transaction for cleanup.
    await connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    before = await snapshot(connection)
    policies = await forced_rls(connection)
    assert policies and all(forced for _, forced in policies)
    # The migration must see another owner's history, even when its normal
    # current-user context cannot read those rows under FORCE RLS.
    await set_owner(connection, uuid4())
    with pytest.raises(DBAPIError, match=expected):
        async with connection.begin_nested():
            await connection.run_sync(lambda sync: downgrade(sync, revision))
    assert await forced_rls(connection) == policies
    await set_owner(connection, owner)
    assert await snapshot(connection) == before


@pytest.mark.parametrize("revision", ["0063", "0064"])
async def test_populated_financial_state_survives_refused_downgrade(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    rollback_connection: AsyncConnection,
    revision: str,
) -> None:
    async with migrator_engine.begin() as connection:
        await connection.execute(text("UPDATE paper_protection_protocol SET enabled=true"))
    market = None
    try:
        market, _, _, _, _ = await buy(api_engine, engine_engine, scan_engine, owner, wallet)
    finally:
        async with migrator_engine.begin() as connection:
            await connection.execute(text("UPDATE paper_protection_protocol SET enabled=false"))
        if market is not None:
            await market.dispose()
    connection = rollback_connection
    await set_owner(connection, owner)
    before = await snapshot(connection)
    policies = await forced_rls(connection)
    await set_owner(connection, uuid4())
    with pytest.raises(DBAPIError, match="protection history prevents downgrade"):
        async with connection.begin_nested():
            await connection.run_sync(lambda sync: downgrade(sync, revision))
    assert await forced_rls(connection) == policies
    await set_owner(connection, owner)
    assert await snapshot(connection) == before
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        cash = await get_wallet(session)
        assert cash is not None and cash.balance == Money.of("9900", "USDT")
        held, reserved = await held_and_reserved(
            session, wallet.episode_id, PositionPair("BTC", "USDT")
        )
        assert held == Quantity.of("0.999", "BTC") and reserved == Quantity.of(0, "BTC")
