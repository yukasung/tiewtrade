from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.positions.conftest import owner as owner
from tests.infra.positions.conftest import production_wallet as wallet
from tiewtrade.infra.db import DatabaseRole, user_session

__all__ = ["owner", "wallet"]


@pytest.fixture(autouse=True)
async def _finish_test_order_dispatch(
    engine_engine: AsyncEngine, owner: UUID
) -> AsyncIterator[None]:
    yield
    # Like the existing risk scheduler fixtures, finish only this owner's mutable
    # test scheduling. Keep financial facts, reservations and audit history intact.
    # Trigger tests leave entry-cancel commands that otherwise fill the scanner's
    # bounded batch and hide later tests' owners.
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute("""UPDATE paper_order_dispatch SET state='TERMINAL',
            worker=NULL,claim_id=NULL,lease_until=NULL WHERE state<>'TERMINAL'""")
