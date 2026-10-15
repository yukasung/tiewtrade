from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.users import create_user


@pytest.fixture
async def owner(api_engine: AsyncEngine) -> UUID:
    user_id = uuid4()
    await create_user(api_engine, user_id)
    return user_id
