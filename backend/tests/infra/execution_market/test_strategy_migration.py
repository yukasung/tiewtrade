"""F-21 schema roundtrip, history preservation and public-source privilege boundary."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.db.test_migrations import _alembic, _failed_upgrade_or_downgrade, _snapshot
from tiewtrade.core.market_data import Timeframe
from tiewtrade.core.money import Money
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.strategy_config import RsiStepGridConfig
from tiewtrade.infra.bots.configurations import create_configuration
from tiewtrade.infra.db import DatabaseRole, user_session

pytestmark = pytest.mark.usefixtures("internal_database")


async def test_f21_roundtrip_keeps_existing_schema_and_narrow_source_grants(
    migrator_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
) -> None:
    before = await _snapshot(migrator_engine)
    _alembic("downgrade", "0073")
    _alembic("upgrade", "head")
    assert await _snapshot(migrator_engine) == before
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        grants = (
            await session.execute("""SELECT
          has_column_privilege('tiewtrade_engine','market_candle_demand','desired_end','UPDATE'),
          has_column_privilege('tiewtrade_engine','market_candle_demand','token','UPDATE'),
          has_column_privilege('tiewtrade_engine','market_candle_demand','failure_code','UPDATE'),
          has_column_privilege('tiewtrade_engine','market_candle_demand','bot_recovery_at','UPDATE'),
          has_table_privilege('tiewtrade_engine','market_candles','UPDATE'),
          has_table_privilege('tiewtrade_engine_scan','bot_strategy_configurations','SELECT'),
          has_table_privilege('tiewtrade_api','bot_strategy_baskets','UPDATE'),
          has_table_privilege('tiewtrade_engine','bot_basket_triggers','UPDATE')""")
        ).one()
        assert tuple(grants) == (True, False, False, False, False, False, False, False)


async def test_f21_configuration_history_refuses_downgrade_and_restores_forced_rls(
    api_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
) -> None:
    async with user_session(api_engine, owner) as session:
        config = RsiStepGridConfig(
            PositionPair("BTC", "USDT"), Timeframe.M5, Money.of(100, "USDT"), 3
        )
        identity = await create_configuration(session, key=uuid4(), configuration=config)
    refusal = _failed_upgrade_or_downgrade("downgrade", "0073")
    assert "F-21 history prevents destructive downgrade" in refusal.stderr
    async with migrator_engine.connect() as connection:
        assert (
            await connection.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one() == "0074"
        forced: list[bool] = list(
            (
                await connection.execute(
                    text(
                        "SELECT relforcerowsecurity FROM pg_class "
                        "WHERE relname LIKE 'bot_strategy_%' "
                        "AND relkind='r'"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert forced and all(forced)
    async with user_session(api_engine, owner) as session:
        assert (
            await session.execute("SELECT id FROM bot_strategy_configurations")
        ).scalar_one() == identity
