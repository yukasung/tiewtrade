"""Single-account preference and sole-key invariants are enforced in PostgreSQL."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.api_keys import MAX_KEYS_PER_USER
from tiewtrade.infra.db import user_session
from tiewtrade.infra.db.errors import DuplicateValueError

from .conftest import active_key


async def test_single_key_constant() -> None:
    assert MAX_KEYS_PER_USER == 1


@pytest.mark.parametrize("status", ["PENDING", "ACTIVE", "REJECTED", "UNVERIFIABLE"])
async def test_one_key_database_guard(
    api_engine: AsyncEngine, engine_engine: AsyncEngine, owner: UUID, status: str
) -> None:
    first = await active_key(api_engine, engine_engine, owner)
    if status != "ACTIVE":
        from tiewtrade.infra.db import DatabaseRole

        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                "UPDATE user_api_keys SET status=:status,verified_at=NULL,failure_code=:code,"
                "secret_sealed=CASE WHEN :status='REJECTED' THEN NULL ELSE secret_sealed END,"
                "key_version=CASE WHEN :status='REJECTED' THEN NULL ELSE key_version END "
                "WHERE id=:id",
                {
                    "status": status,
                    "code": None if status == "PENDING" else "VENUE_PROTOCOL",
                    "id": first,
                },
            )
    from tiewtrade.infra.api_keys import TooManyKeysError, store_key
    from tiewtrade.infra.crypto import KeyPurpose, KeySource

    with pytest.raises(TooManyKeysError):
        async with user_session(api_engine, owner) as session:
            await store_key(
                session,
                KeySource.from_environment(KeyPurpose.VENUE_API_SECRET),
                user_id=owner,
                label="second",
                key_public="synthetic",
                secret="synthetic-secret",
            )
    with pytest.raises(DuplicateValueError):
        async with user_session(api_engine, owner) as session:
            await session.execute(
                "INSERT INTO user_api_keys "
                "(id,user_id,label,key_public,secret_sealed,key_version,status) SELECT "
                ":id,user_id,'second','synthetic-second',decode('abcd','hex'),'1',"
                "'PENDING' FROM user_api_keys WHERE id=:first",
                {"id": uuid4(), "first": first},
            )


async def test_preference_has_no_credential_columns(api_engine: AsyncEngine, owner: UUID) -> None:
    async with user_session(api_engine, owner) as session:
        await session.execute(
            "INSERT INTO user_trading_preferences (user_id,use) VALUES (:owner,'MANUAL')",
            {"owner": owner},
        )
        assert (
            await session.execute("SELECT user_id,use FROM user_trading_preferences")
        ).one() == (owner, "MANUAL")
