"""Owned PostgreSQL migration/history and runtime-privilege boundaries."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.db.test_migrations import _alembic, _failed_upgrade_or_downgrade, _snapshot
from tiewtrade.core.market_data import Timeframe
from tiewtrade.core.money import Money
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.strategy_config import PaperTestConfig
from tiewtrade.infra.bots.configurations import create_configuration
from tiewtrade.infra.db import user_session

pytestmark = pytest.mark.usefixtures("internal_database")


async def test_empty_upgrade_downgrade_roundtrip_and_narrow_grants(
    migrator_engine: AsyncEngine,
) -> None:
    before = await _snapshot(migrator_engine)
    _alembic("downgrade", "0074")
    _alembic("upgrade", "head")
    assert await _snapshot(migrator_engine) == before
    async with migrator_engine.connect() as connection:
        grants = (
            await connection.execute(
                text("""SELECT
          has_table_privilege('tiewtrade_api','bot_test_strategy_configurations','INSERT'),
          has_table_privilege('tiewtrade_api','bot_test_strategy_configurations','UPDATE'),
          has_table_privilege('tiewtrade_engine','bot_test_entry_anchors','INSERT'),
          has_column_privilege('tiewtrade_engine','bot_test_entry_anchors','atr','UPDATE'),
          has_column_privilege('tiewtrade_engine','bot_test_entry_anchors','take_profit','UPDATE'),
          has_table_privilege('tiewtrade_engine_scan','bot_test_entry_anchors','SELECT'),
          has_table_privilege('tiewtrade_market_data','bot_test_entry_anchors','SELECT')""")
            )
        ).one()
        assert tuple(grants) == (True, False, True, False, True, False, False)


async def test_configuration_history_prevents_destructive_downgrade(
    api_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
) -> None:
    async with user_session(api_engine, owner) as session:
        identity = await create_configuration(
            session,
            key=uuid4(),
            configuration=PaperTestConfig(
                PositionPair("BTC", "USDT"), Timeframe.M1, Money.of(100, "USDT")
            ),
        )
    refusal = _failed_upgrade_or_downgrade("downgrade", "0074")
    assert "Paper test history prevents destructive downgrade" in refusal.stderr
    async with migrator_engine.connect() as connection:
        assert (
            await connection.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one() == "0075"
        forced: list[bool] = list(
            (
                await connection.execute(
                    text(
                        "SELECT relforcerowsecurity FROM pg_class WHERE relname IN "
                        "('bot_test_strategy_configurations','bot_test_entry_anchors')"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(forced) == 2 and all(forced)
    async with user_session(api_engine, owner) as session:
        assert (
            await session.execute("SELECT id FROM bot_test_strategy_configurations")
        ).scalar_one() == identity
