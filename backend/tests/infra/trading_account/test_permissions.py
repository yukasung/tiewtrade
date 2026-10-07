"""Actual runtime role permissions and owner RLS on preferences."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.errors import NotPermittedError
from tiewtrade.infra.trading_account import AccountUse, select_use
from tiewtrade.infra.users import create_user

from .conftest import active_key


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE user_trading_preferences SET use='BOT' WHERE user_id=:owner",
        "DELETE FROM user_trading_preferences WHERE user_id=:owner",
        "SELECT created_at FROM user_trading_preferences",
        "SELECT secret_sealed,key_version FROM user_api_keys",
    ],
)
async def test_api_cannot_mutate_or_read_extra_columns(
    api_engine: AsyncEngine, engine_engine: AsyncEngine, owner: UUID, statement: str
) -> None:
    await active_key(api_engine, engine_engine, owner)
    async with user_session(api_engine, owner) as session:
        await select_use(session, AccountUse.MANUAL)
    with pytest.raises(NotPermittedError):
        async with user_session(api_engine, owner) as session:
            await session.execute(statement, {"owner": owner})


async def test_owner_forgery_and_reads_denied(api_engine: AsyncEngine, owner: UUID) -> None:
    other = uuid4()
    await create_user(api_engine, other)
    async with user_session(api_engine, owner) as session:
        await session.execute(
            "INSERT INTO user_trading_preferences (user_id,use) VALUES (:owner,'BOT')",
            {"owner": owner},
        )
    async with user_session(api_engine, other) as session:
        assert (
            await session.execute("SELECT user_id,use FROM user_trading_preferences")
        ).all() == []
    with pytest.raises(NotPermittedError):
        async with user_session(api_engine, other) as session:
            await session.execute(
                "INSERT INTO user_trading_preferences (user_id,use) VALUES (:owner,'MANUAL')",
                {"owner": owner},
            )


@pytest.mark.parametrize(
    "role",
    [DatabaseRole.ENGINE, DatabaseRole.ENGINE_SCAN, DatabaseRole.AUTH, DatabaseRole.MARKET_DATA],
)
async def test_other_runtime_roles_have_no_preference_access(role: DatabaseRole) -> None:
    engine = create_engine_for(role)
    try:
        with pytest.raises(SQLAlchemyError):
            async with engine.begin() as connection:
                await connection.execute(text("SELECT user_id FROM user_trading_preferences"))
    finally:
        await engine.dispose()


async def test_force_rls_and_column_shape(migrator_engine: AsyncEngine) -> None:
    async with migrator_engine.connect() as connection:
        assert (
            await connection.execute(
                text(
                    "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE "
                    "oid='public.user_trading_preferences'::regclass"
                )
            )
        ).one() == (True, True)
        columns: list[str] = list(
            (
                await connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns WHERE "
                        "table_name='user_trading_preferences' ORDER BY ordinal_position"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert columns == ["user_id", "use", "created_at"]
        assert (
            await connection.execute(text("SELECT to_regclass('public.wallet_registry')"))
        ).scalar_one() is None
