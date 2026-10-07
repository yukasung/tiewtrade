"""Barriers and actual transactions enforce one initial preference and one key."""

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.audit import record_event
from tiewtrade.infra.db import user_session
from tiewtrade.infra.db.errors import DuplicateValueError
from tiewtrade.infra.trading_account import (
    AccountUse,
    TradingAccountActivityUnknownError,
    get_account,
    select_use,
)

from .conftest import active_key
from .test_audit import selected_event


async def test_initial_selections_one_succeeds(
    api_engine: AsyncEngine, engine_engine: AsyncEngine, owner: UUID
) -> None:
    await active_key(api_engine, engine_engine, owner)
    barrier = asyncio.Barrier(2)

    async def select(use: AccountUse) -> bool:
        try:
            async with user_session(api_engine, owner) as session:
                await barrier.wait()
                await select_use(session, use)
                await record_event(session, selected_event(owner, use))
            return True
        except TradingAccountActivityUnknownError:
            return False

    assert sorted(await asyncio.gather(*(select(use) for use in AccountUse))) == [False, True]
    async with user_session(api_engine, owner) as session:
        assert (await get_account(session)).use in AccountUse
        assert (
            await session.execute(
                "SELECT count(*) FROM audit_events WHERE action='TRADING_USE_SELECTED'"
            )
        ).scalar_one() == 1


async def test_direct_parallel_key_inserts_one_succeeds(
    api_engine: AsyncEngine, owner: UUID
) -> None:
    barrier = asyncio.Barrier(2)

    async def insert() -> bool:
        try:
            async with user_session(api_engine, owner) as session:
                await barrier.wait()
                await session.execute(
                    "INSERT INTO user_api_keys "
                    "(id,user_id,label,key_public,secret_sealed,key_version,status) "
                    "VALUES (:id,:owner,:label,'synthetic',decode('abcd','hex'),'1','PENDING')",
                    {"id": uuid4(), "owner": owner, "label": str(uuid4())},
                )
            return True
        except DuplicateValueError:
            return False

    assert sorted(await asyncio.gather(insert(), insert())) == [False, True]
    async with user_session(api_engine, owner) as session:
        assert (await session.execute("SELECT count(*) FROM user_api_keys")).scalar_one() == 1


@pytest.mark.parametrize("delete_first", [True, False])
async def test_selection_and_key_delete_both_lock_orders(
    api_engine: AsyncEngine, engine_engine: AsyncEngine, owner: UUID, delete_first: bool
) -> None:
    from tiewtrade.infra.api_keys import delete_key
    from tiewtrade.infra.trading_account import TradingAccountKeyUnavailableError

    key = await active_key(api_engine, engine_engine, owner)
    first_locked = asyncio.Event()
    contender_ready = asyncio.Event()
    release = asyncio.Event()

    async def select() -> None:
        if delete_first:
            await first_locked.wait()
            contender_ready.set()
            with pytest.raises(TradingAccountKeyUnavailableError):
                async with user_session(api_engine, owner) as session:
                    await select_use(session, AccountUse.BOT)
                    await record_event(session, selected_event(owner, AccountUse.BOT))
        else:
            async with user_session(api_engine, owner) as session:
                await select_use(session, AccountUse.BOT)
                await record_event(session, selected_event(owner, AccountUse.BOT))
                first_locked.set()
                await release.wait()

    async def delete() -> None:
        if not delete_first:
            await first_locked.wait()
            contender_ready.set()
        async with user_session(api_engine, owner) as session:
            assert await delete_key(session, key)
            if delete_first:
                first_locked.set()
                await release.wait()

    tasks = [asyncio.create_task(select()), asyncio.create_task(delete())]
    try:
        await asyncio.wait_for(contender_ready.wait(), 5)
        release.set()
        await asyncio.wait_for(asyncio.gather(*tasks), 5)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    async with user_session(api_engine, owner) as session:
        account = await get_account(session)
        assert account.key is None
        assert account.use is (None if delete_first else AccountUse.BOT)
        assert (
            await session.execute(
                "SELECT count(*) FROM audit_events WHERE action='TRADING_USE_SELECTED'"
            )
        ).scalar_one() == (0 if delete_first else 1)
