"""Synthetic verified credentials for actual-role trading account integration tests."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.api_keys import store_key
from tiewtrade.infra.crypto import KeyPurpose, KeySource
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.users import create_user


@pytest.fixture
async def owner(api_engine: AsyncEngine) -> UUID:
    user = uuid4()
    await create_user(api_engine, user)
    return user


async def active_key(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    *,
    public: str | None = None,
    label: str | None = None,
) -> UUID:
    async with user_session(api_engine, owner) as session:
        key_id = await store_key(
            session,
            KeySource.from_environment(KeyPurpose.VENUE_API_SECRET),
            user_id=owner,
            label=label or str(uuid4()),
            key_public=public or str(uuid4()),
            secret="synthetic-trading-account-secret",
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute(
            "UPDATE user_api_keys SET status='ACTIVE', verified_at=now() WHERE id=:id",
            {"id": key_id},
        )
    return key_id
