"""Price-only cursor saves preserve pair rows; real fills advance their source."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.risk_limits.test_execution import fill_buy, runtime
from tests.infra.risk_limits.test_requests import submission
from tiewtrade.core.money import Money
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits.monitor import replay_monitor
from tiewtrade.infra.risk_limits.storage import read_setting


async def test_price_ticks_preserve_pairs_and_a_second_real_fill_advances_them(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"
    ) as sources:
        await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await replay_monitor(
                session, await read_setting(session, submission(owner, wallet).scope)
            )
            first = (
                await session.execute(
                    "SELECT source_revision,xmin::text AS version FROM risk_limit_pairs"
                )
            ).one()
        await sources.price("101")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await replay_monitor(
                session, await read_setting(session, submission(owner, wallet).scope)
            )
            same = (
                await session.execute(
                    "SELECT source_revision,xmin::text AS version FROM risk_limit_pairs"
                )
            ).one()
            assert same == first
        await sources.price("100")
        await sources.next_book()
        await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await replay_monitor(
                session, await read_setting(session, submission(owner, wallet).scope)
            )
            changed = (
                await session.execute(
                    "SELECT source_revision,xmin::text AS version FROM risk_limit_pairs"
                )
            ).one()
            assert changed.source_revision > first.source_revision
            assert changed.version != first.version
            current = await get_wallet(session)
            assert current is not None and current.balance == Money.of(9800, "USDT")
