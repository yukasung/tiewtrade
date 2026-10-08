from datetime import timedelta
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.auth.throttle import RULES, Bucket, TokenRule
from tiewtrade.infra.db import UserSession, user_session
from tiewtrade.infra.db.errors import SessionKindError
from tiewtrade.infra.realtime.connections import (
    USER_CONNECTION_SLOTS,
    ConnectionLease,
    claim,
    release,
    renew,
)
from tiewtrade.infra.users import create_user


def test_slots_and_handshake_contract() -> None:
    assert USER_CONNECTION_SLOTS == (1, 2, 3)
    assert RULES[Bucket.PRICE_STREAM_HANDSHAKE] == TokenRule(6, timedelta(seconds=10))
    assert Bucket.PRICE_STREAM_HANDSHAKE.table == "api_throttle"


async def test_three_slots_expiry_and_old_socket_cas(api_engine: AsyncEngine) -> None:
    owner, other = uuid4(), uuid4()
    await create_user(api_engine, owner)
    await create_user(api_engine, other)
    leases = []
    async with user_session(api_engine, owner) as session:
        for _ in range(3):
            lease = await claim(session, uuid4())
            assert lease is not None
            leases.append(lease)
        assert await claim(session, uuid4()) is None
        await session.execute(
            "UPDATE market_price_connections SET "
            "lease_until=clock_timestamp()-interval '1 second' WHERE slot=1"
        )
        replacement = await claim(session, uuid4())
        assert replacement is not None and replacement.slot == 1
        await release(session, leases[0])
        assert await renew(session, leases[0]) is None
        assert await renew(session, replacement) is not None
    async with user_session(api_engine, other) as session:
        assert (
            await session.execute("SELECT count(*) FROM market_price_connections")
        ).scalar_one() == 0
        assert await renew(session, replacement) is None
    async with user_session(api_engine, owner) as session:
        for lease in [*leases, replacement]:
            await release(session, lease)


async def test_requires_user_session() -> None:
    with pytest.raises(SessionKindError):
        await claim(cast(UserSession, object()), uuid4())


async def test_parallel_claims_cannot_exceed_three(api_engine: AsyncEngine) -> None:
    import asyncio

    owner = uuid4()
    await create_user(api_engine, owner)

    async def attempt() -> ConnectionLease | None:
        async with user_session(api_engine, owner) as session:
            return await claim(session, uuid4())

    results = await asyncio.gather(*(attempt() for _ in range(9)))
    claimed = [r for r in results if r is not None]
    assert len(claimed) == 3
    assert {r.slot for r in claimed} == set(USER_CONNECTION_SLOTS)
    async with user_session(api_engine, owner) as session:
        for lease in claimed:
            await release(session, lease)


async def test_schema_slot_constraint_matches_runtime(migrator_engine: AsyncEngine) -> None:
    from sqlalchemy import text

    async with migrator_engine.connect() as connection:
        constraint: str = (
            await connection.execute(
                text("""SELECT pg_get_constraintdef(oid)
            FROM pg_constraint WHERE conrelid='market_price_connections'::regclass
            AND contype='c'""")
            )
        ).scalar_one()
        assert "slot >= 1" in constraint and "slot <= 3" in constraint
        rls = (
            await connection.execute(
                text("""SELECT relrowsecurity,relforcerowsecurity
            FROM pg_class WHERE oid='market_price_connections'::regclass""")
            )
        ).one()
        assert rls == (True, True)


async def test_market_and_connection_grants(migrator_engine: AsyncEngine) -> None:
    from sqlalchemy import text

    async with migrator_engine.connect() as connection:
        for role in ("tiewtrade_api", "tiewtrade_engine"):
            selected: bool = (
                await connection.execute(
                    text("SELECT has_table_privilege(:role,'market_latest_prices','SELECT')"),
                    {"role": role},
                )
            ).scalar_one()
            assert selected
            updated: bool = (
                await connection.execute(
                    text("SELECT has_table_privilege(:role,'market_latest_prices','UPDATE')"),
                    {"role": role},
                )
            ).scalar_one()
            assert not updated
        for role in (
            "tiewtrade_market_data",
            "tiewtrade_engine",
            "tiewtrade_engine_scan",
            "tiewtrade_auth",
        ):
            permitted: bool = (
                await connection.execute(
                    text("SELECT has_table_privilege(:role,'market_price_connections','SELECT')"),
                    {"role": role},
                )
            ).scalar_one()

            assert not permitted
