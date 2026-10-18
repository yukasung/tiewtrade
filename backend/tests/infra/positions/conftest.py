from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import user_session
from tiewtrade.infra.paper_wallet import PaperWalletAction, admit_command, get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.users import create_user
from tiewtrade.services.engine.paper_wallet import run_paper_wallet_round


@pytest.fixture
async def owner(api_engine: AsyncEngine) -> UUID:
    owner_id = uuid4()
    await create_user(api_engine, owner_id)
    return owner_id


@pytest.fixture
async def wallet(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
) -> PaperWalletSnapshot:
    async with user_session(api_engine, owner) as session:
        await admit_command(
            session,
            action=PaperWalletAction.CREATE,
            idempotency_key=uuid4(),
            capital_text="10000",
            expected_episode_id=None,
        )
    await run_paper_wallet_round(
        engine=engine_engine, scan_engine=scan_engine, worker=f"position-{uuid4()}"
    )
    async with user_session(api_engine, owner) as session:
        result = await get_wallet(session)
    assert result is not None
    return result
