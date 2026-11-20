"""F-20 consumes F-37 withdrawals in a dedicated, freshly migrated database."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.orders import TradingMode
from tiewtrade.infra.bots.catalog import CatalogStopHint, apply_catalog_stop
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import market_data_session, presented_session
from tiewtrade.infra.indicators.session import indicator_writer_session
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.platform import (
    CatalogReason,
    enable_mutations,
    reconcile_removal_effects,
    record_protocol_heartbeat,
    request_remove,
)
from tiewtrade.infra.users import create_user
from tiewtrade.services.engine.bot import run_bot_catalog_round

pytestmark = pytest.mark.fresh_global_state


async def seed_catalog_run(
    engine: AsyncEngine,
    owner: UUID,
    mode: TradingMode,
    base: str,
    *,
    pin: int,
    wallet: PaperWalletSnapshot | None = None,
) -> UUID:
    run = uuid4()
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute(
            """INSERT INTO bot_runs(id,user_id,mode,wallet_id,episode_id,strategy_name,
                strategy_version,configuration_version,state_version,configuration,
                strategy_state,status)
            VALUES(:id,:owner,:mode,:wallet,:episode,'fixture',1,1,1,'{}','{}','RUNNING')""",
            {
                "id": run,
                "owner": owner,
                "mode": mode.value,
                "wallet": None if wallet is None else wallet.wallet_id,
                "episode": None if wallet is None else wallet.episode_id,
            },
        )
        await session.execute(
            """INSERT INTO bot_run_events(id,run_id,user_id,mode,revision,event,details)
               VALUES(:id,:run,:owner,:mode,1,'START_REQUEST_APPLIED',
                 jsonb_build_object('base',CAST(:base AS text),'quote','USDT',
                                    'catalog_revision',CAST(:pin AS bigint)))""",
            {
                "id": uuid4(),
                "run": run,
                "owner": owner,
                "mode": mode.value,
                "base": base,
                "pin": pin,
            },
        )
    return run


async def enable_catalog(
    api: AsyncEngine, engine: AsyncEngine, migrator: AsyncEngine, owner: UUID
) -> None:
    generation = uuid4()
    async with migrator.begin() as connection:
        await connection.execute(
            text("SELECT set_config('tiewtrade.current_user_id',:owner,true)"),
            {"owner": str(owner)},
        )
        await connection.execute(
            text("INSERT INTO platform_memberships(user_id,role) VALUES(:id,'PLATFORM_OWNER')"),
            {"id": owner},
        )
    market = create_engine_for(DatabaseRole.MARKET_DATA)
    indicators = create_engine_for(DatabaseRole.INDICATOR_BUILDER)
    try:
        for kind, context in (
            ("API", presented_session(api, role=DatabaseRole.API)),
            ("ENGINE", presented_session(engine, role=DatabaseRole.ENGINE)),
            ("MARKET_DATA", market_data_session(market)),
            ("INDICATOR_BUILDER", indicator_writer_session(indicators)),
        ):
            async with context as session:
                now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
                await record_protocol_heartbeat(
                    session,
                    process_kind=kind,
                    instance_id=uuid4(),
                    protocol_version=1,
                    deployment_generation=generation,
                    lease_expires_at=now + timedelta(minutes=2),
                )
        async with user_session(api, owner) as session:
            await enable_mutations(session, deployment_generation=generation, expected_revision=2)
    finally:
        await market.dispose()
        await indicators.dispose()


async def test_catalog_removal_stops_scoped_runs_across_modes_and_replays_once(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    other, unaffected = uuid4(), uuid4()
    await create_user(api_engine, other)
    await create_user(api_engine, unaffected)
    paper = await seed_catalog_run(
        engine_engine, owner, TradingMode.PAPER, "BTC", pin=2, wallet=wallet
    )
    live = await seed_catalog_run(engine_engine, other, TradingMode.LIVE, "BTC", pin=2)
    control = await seed_catalog_run(engine_engine, unaffected, TradingMode.LIVE, "ETH", pin=2)
    await enable_catalog(api_engine, engine_engine, migrator_engine, owner)
    async with user_session(api_engine, owner) as session:
        removed = await request_remove(
            session,
            command_id=uuid4(),
            idempotency_key="f20-withdraw-btc",
            base="BTC",
            quote="USDT",
            expected_revision=2,
            reason=CatalogReason.RISK_REVIEW,
        )
    assert removed.revision == 3
    # Restart/duplicate delivery is represented by new worker transactions.
    assert await run_bot_catalog_round(engine=engine_engine, scan_engine=scan_engine) == 2
    assert await run_bot_catalog_round(engine=engine_engine, scan_engine=scan_engine) == 0
    for row_owner, run, expected in (
        (owner, paper, "STOPPED"),
        (other, live, "STOPPED"),
        (unaffected, control, "RUNNING"),
    ):
        async with user_session(engine_engine, row_owner, role=DatabaseRole.ENGINE) as session:
            status = (
                await session.execute("SELECT status FROM bot_runs WHERE id=:id", {"id": run})
            ).scalar_one()
            assert status == expected
            assert (
                await session.execute("SELECT count(*) FROM bot_catalog_stops")
            ).scalar_one() == (1 if expected == "STOPPED" else 0)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert not await apply_catalog_stop(
            session, CatalogStopHint(paper, owner, TradingMode.PAPER, 3)
        )
    async with presented_session(engine_engine, role=DatabaseRole.ENGINE) as session:
        await reconcile_removal_effects(session)
        assert (
            await session.execute(
                "SELECT bots_stopped,status FROM supported_symbol_effects WHERE event_revision=3"
            )
        ).one() == (2, "PARTIAL")
