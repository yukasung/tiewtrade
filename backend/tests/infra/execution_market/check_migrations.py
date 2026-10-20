"""Run once against a fresh isolated DB: populated 0032 -> 0034 -> 0033 -> 0034.

Uses the usual role URL environment. Does not drop a database or erase financial history.
Kept separate from pytest's shared DB because the refusal case intentionally retains history.
"""

import asyncio
import sys
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tiewtrade.core.money import Money
from tiewtrade.core.orders import SimulationProfile
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.paper_orders.storage import pin_execution_profile
from tiewtrade.infra.paper_wallet import PaperWalletAction, admit_command, get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.users import create_user
from tiewtrade.services.engine.paper_wallet import run_paper_wallet_round


def config() -> Config:
    # Same migration tree as alembic.ini, without Windows' explicit locale file decoding.
    value = Config()
    value.set_main_option("script_location", str(Path(__file__).parents[3] / "migrations"))
    return value


async def seed() -> tuple[UUID, PaperWalletSnapshot]:
    api, engine, scan = (
        create_engine_for(role)
        for role in (DatabaseRole.API, DatabaseRole.ENGINE, DatabaseRole.ENGINE_SCAN)
    )
    try:
        owner = uuid4()
        await create_user(api, owner)
        async with user_session(api, owner) as session:
            await admit_command(
                session,
                action=PaperWalletAction.CREATE,
                idempotency_key=uuid4(),
                capital_text="2500",
                expected_episode_id=None,
            )
        await run_paper_wallet_round(engine=engine, scan_engine=scan, worker="f15-migration-check")
        async with user_session(api, owner) as session:
            wallet = await get_wallet(session)
        assert wallet is not None and wallet.balance == Money.of(2500, "USDT")
        return owner, wallet
    finally:
        await asyncio.gather(api.dispose(), engine.dispose(), scan.dispose())


async def verify(owner: UUID, before: PaperWalletSnapshot, *, pin: bool = False) -> None:
    api, engine = create_engine_for(DatabaseRole.API), create_engine_for(DatabaseRole.ENGINE)
    try:
        async with user_session(api, owner) as session:
            wallet = await get_wallet(session)
        assert wallet is not None
        assert (wallet.wallet_id, wallet.episode_id, wallet.balance, wallet.initial_capital) == (
            before.wallet_id,
            before.episode_id,
            before.balance,
            before.initial_capital,
        )
        if pin:
            async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                state = (
                    await session.execute(
                        "SELECT availability FROM paper_order_activity WHERE episode_id=:episode",
                        {"episode": before.episode_id},
                    )
                ).scalar_one()
                assert state == "UNKNOWN"
                await pin_execution_profile(
                    session,
                    wallet_id=before.wallet_id,
                    episode_id=before.episode_id,
                    profile=SimulationProfile(),
                )
    finally:
        await asyncio.gather(api.dispose(), engine.dispose())


async def verify_refusal_rolled_back() -> None:
    engine = create_engine_for(DatabaseRole.MIGRATOR)
    try:
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one() == "0034"
            rows = (
                (
                    await connection.execute(
                        text("""SELECT relname,relforcerowsecurity FROM pg_class
              WHERE relname IN
                ('paper_execution_profiles','paper_execution_inputs','paper_wallet_ledger')""")
                    )
                )
                .mappings()
                .all()
            )
            assert len(rows) == 3 and all(row["relforcerowsecurity"] for row in rows)
    finally:
        await engine.dispose()


def main() -> None:
    command.upgrade(config(), "0032")
    owner, wallet = asyncio.run(seed())
    command.upgrade(config(), "0034")
    asyncio.run(verify(owner, wallet))
    command.downgrade(config(), "0033")
    asyncio.run(verify(owner, wallet))
    command.upgrade(config(), "0034")
    asyncio.run(verify(owner, wallet, pin=True))
    try:
        command.downgrade(config(), "0033")
    except DBAPIError as error:
        assert "Paper financial history prevents downgrade" in str(error)
    else:
        raise AssertionError("downgrade erased Paper history")
    asyncio.run(verify_refusal_rolled_back())
    asyncio.run(verify(owner, wallet))
    sys.stdout.write(
        "PASS: populated upgrade, capital-preserving downgrade/upgrade, "
        "history refusal and FORCE RLS rollback\n"
    )


if __name__ == "__main__":
    main()
