"""Safe owner-scoped single trading account metadata."""

from dataclasses import fields
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.api_keys import ApiKeyStatus, delete_key
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.errors import SessionKindError
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.trading_account import (
    AccountUse,
    TradingAccountActivityUnknownError,
    TradingAccountKeyUnavailableError,
    get_account,
    select_use,
)

from .conftest import active_key


async def test_initial_account_is_null_and_disabled(api_engine: AsyncEngine, owner: UUID) -> None:
    async with user_session(api_engine, owner) as session:
        account = await get_account(session)
        assert account.use is None and account.key is None
        assert not account.may_trade and not account.may_change_use
        assert {f.name for f in fields(account)} == {"use", "key", "may_trade", "may_change_use"}
        with pytest.raises(TradingAccountKeyUnavailableError):
            await select_use(session, AccountUse.MANUAL)


@pytest.mark.parametrize("use", list(AccountUse))
async def test_select_and_delete_preserve_use(
    api_engine: AsyncEngine, engine_engine: AsyncEngine, owner: UUID, use: AccountUse
) -> None:
    public = str(uuid4()) + "TAIL"
    key = await active_key(api_engine, engine_engine, owner, public=public)
    async with user_session(api_engine, owner) as session:
        account = await select_use(session, use)
        assert account.use is use and account.key is not None and account.key.id == key
        assert account.key.status is ApiKeyStatus.ACTIVE and account.key.public_tail == "TAIL"
        assert public not in repr(account) and not account.may_trade and not account.may_change_use
    async with user_session(api_engine, owner) as session:
        for requested in AccountUse:
            with pytest.raises(TradingAccountActivityUnknownError):
                await select_use(session, requested)
        await delete_key(session, key)
    async with user_session(api_engine, owner) as session:
        after = await get_account(session)
        assert after.use is use and after.key is None
        with pytest.raises(TradingAccountActivityUnknownError):
            await select_use(session, use)


@pytest.mark.parametrize("status", ["PENDING", "UNVERIFIABLE", "REJECTED"])
async def test_non_active_key_refused(
    api_engine: AsyncEngine, engine_engine: AsyncEngine, owner: UUID, status: str
) -> None:
    key = await active_key(api_engine, engine_engine, owner)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute(
            "UPDATE user_api_keys SET "
            "status=:status,verified_at=NULL,failure_code=:code,secret_sealed=CASE WHEN "
            ":status='REJECTED' THEN NULL ELSE secret_sealed END,key_version=CASE WHEN "
            ":status='REJECTED' THEN NULL ELSE key_version END WHERE id=:id",
            {
                "status": status,
                "code": None if status == "PENDING" else "VENUE_PROTOCOL",
                "id": key,
            },
        )
    with pytest.raises(TradingAccountKeyUnavailableError):
        async with user_session(api_engine, owner) as session:
            await select_use(session, AccountUse.BOT)


async def test_ownership_never_adopts_other_users_key(
    api_engine: AsyncEngine, engine_engine: AsyncEngine, owner: UUID
) -> None:
    from tiewtrade.infra.users import create_user

    other = uuid4()
    await create_user(api_engine, other)
    await active_key(api_engine, engine_engine, owner)
    async with user_session(api_engine, owner) as session:
        await select_use(session, AccountUse.BOT)
    async with user_session(api_engine, other) as session:
        account = await get_account(session)
        assert account.use is None and account.key is None
        with pytest.raises(TradingAccountKeyUnavailableError):
            await select_use(session, AccountUse.MANUAL)


@pytest.mark.parametrize("operation", ["read", "select"])
async def test_only_user_session(operation: str) -> None:
    with pytest.raises(SessionKindError):
        if operation == "read":
            await get_account(cast(UserSession, None))
        else:
            await select_use(cast(UserSession, None), AccountUse.MANUAL)
