"""Owner isolation and financial projection lineage enforced by actual PostgreSQL."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_bot_decisions import (
    bot_bracket_protocol as bot_bracket_protocol,
)
from tests.infra.execution_market.test_strategy_baskets import (
    accounting_indicator_heads as accounting_indicator_heads,
)
from tests.infra.execution_market.test_strategy_baskets import f21_run, queue_entry
from tests.infra.risk_limits.test_execution import runtime
from tiewtrade.infra.db import DatabaseRole, InfraError, user_session
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.users import create_user

pytestmark = pytest.mark.usefixtures(
    "accounting_indicator_heads", "internal_database", "bot_bracket_protocol"
)


@pytest.mark.parametrize("wrong", ["run", "episode", "mode"])
async def test_entry_projection_cannot_cross_its_order_run_episode_or_mode(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    wrong: str,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ):
        first = await f21_run(engine_engine, owner, wallet)
        order, _ = await queue_entry(engine_engine, owner, wallet, first)
        # Retain the historical command/link while constructing a subsequent
        # run. No orders are admitted or filled in this schema-boundary fixture.
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                "UPDATE bot_runs SET status='RETIRED' WHERE id=:id", {"id": first}
            )
        second = await f21_run(engine_engine, owner, wallet)
        await queue_entry(engine_engine, owner, wallet, second)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            basket = (
                await session.execute(
                    "SELECT id FROM bot_strategy_baskets WHERE run_id=:run", {"run": second}
                )
            ).scalar_one()
        statement, parameters = {
            "run": (
                "UPDATE bot_strategy_entries SET run_id=:run,basket_id=:basket,entry_sequence=2 "
                "WHERE order_id=:order",
                {"run": second, "basket": basket, "order": order},
            ),
            "episode": (
                "UPDATE bot_strategy_entries SET episode_id=:episode WHERE order_id=:order",
                {"episode": uuid4(), "order": order},
            ),
            "mode": (
                "UPDATE bot_strategy_entries SET mode='LIVE' WHERE order_id=:order",
                {"order": order},
            ),
        }[wrong]
        with pytest.raises(InfraError, match=r"23503|23514"):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await session.execute(statement, parameters)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute(
                    "SELECT run_id FROM bot_strategy_entries WHERE order_id=:order",
                    {"order": order},
                )
            ).scalar_one() == first
            assert (await session.execute("SELECT count(*) FROM paper_orders")).scalar_one() == 0
        other = uuid4()
        await create_user(api_engine, other)
        async with user_session(api_engine, other) as session:
            for table in ("bot_strategy_entries", "bot_strategy_baskets", "bot_strategy_progress"):
                assert (await session.execute(f"SELECT count(*) FROM {table}")).scalar_one() == 0
