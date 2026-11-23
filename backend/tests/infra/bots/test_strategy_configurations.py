import asyncio
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.market_data import Timeframe
from tiewtrade.core.money import Money
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.strategy_config import RsiStepGridConfig
from tiewtrade.infra.bots.configurations import create_configuration, read_configuration
from tiewtrade.infra.bots.requests import BotRequestConflictError
from tiewtrade.infra.db import DatabaseRole, InfraError, user_session
from tiewtrade.infra.users import create_user


@pytest.mark.asyncio
async def test_concurrent_config_create_is_durable_and_owner_scoped(
    api_engine: AsyncEngine,
) -> None:
    owner, other, key = uuid4(), uuid4(), uuid4()
    await create_user(api_engine, owner)
    await create_user(api_engine, other)
    config = RsiStepGridConfig(
        PositionPair("BTC", "USDT"), Timeframe.M5, Money.of("100", "USDT"), 3
    )

    async def create() -> UUID:
        async with user_session(api_engine, owner) as session:
            return await create_configuration(session, key=key, configuration=config)

    async with asyncio.timeout(10):
        first, second = await asyncio.gather(create(), create())
    assert first == second
    async with user_session(api_engine, owner) as session:
        assert await read_configuration(session, f"f21:{first}") == config
        with pytest.raises(BotRequestConflictError):
            await create_configuration(
                session, key=key, configuration=replace(config, max_entries=4)
            )
    async with user_session(api_engine, other) as session:
        assert await read_configuration(session, f"f21:{first}") is None
        assert await read_configuration(session, "f21:not-a-uuid") is None
    with pytest.raises(InfraError):
        async with user_session(api_engine, owner) as session:
            await session.execute(
                "UPDATE bot_strategy_configurations SET configuration='{}'::jsonb WHERE id=:id",
                {"id": first},
            )


@pytest.mark.asyncio
async def test_f21_storage_does_not_grant_runtime_financial_authority(
    api_engine: AsyncEngine,
) -> None:
    async with user_session(api_engine, uuid4(), role=DatabaseRole.API) as session:
        result = await session.execute("""SELECT
          has_table_privilege('tiewtrade_api','bot_strategy_baskets','UPDATE'),
          has_table_privilege('tiewtrade_api','bot_basket_triggers','INSERT'),
          has_table_privilege('tiewtrade_api','bot_strategy_entries','INSERT'),
          has_table_privilege('tiewtrade_engine','bot_basket_triggers','UPDATE'),
          has_table_privilege('tiewtrade_engine_scan','bot_strategy_configurations','SELECT')""")
        assert tuple(result.one()) == (False, False, False, False, False)
