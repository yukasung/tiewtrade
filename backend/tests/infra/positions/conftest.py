from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole, user_session
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
async def production_wallet(
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


@pytest.fixture
async def legacy_wallet(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
) -> PaperWalletSnapshot:
    """Build the pre-F-15 capital-only state used by F-14 source tests."""
    async with user_session(api_engine, owner) as session:
        command = await admit_command(
            session,
            action=PaperWalletAction.CREATE,
            idempotency_key=uuid4(),
            capital_text="10000",
            expected_episode_id=None,
        )
    wallet_id = uuid4()
    episode_id = uuid4()
    params = {
        "command": command.command_id,
        "wallet": wallet_id,
        "episode": episode_id,
        "ledger": uuid4(),
        "owner": owner,
    }
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute(
            "INSERT INTO paper_wallets(id,user_id) VALUES(:wallet,:owner)", params
        )
        await session.execute(
            """INSERT INTO paper_wallet_episodes
              (id,wallet_id,user_id,sequence,initial_capital,currency)
              VALUES(:episode,:wallet,:owner,1,10000,'USDT')""",
            params,
        )
        await session.execute(
            """INSERT INTO paper_wallet_state(wallet_id,user_id,active_episode_id)
              VALUES(:wallet,:owner,:episode)""",
            params,
        )
        await session.execute(
            """INSERT INTO paper_position_activity(episode_id,wallet_id,user_id)
              VALUES(:episode,:wallet,:owner)""",
            params,
        )
        await session.execute(
            """INSERT INTO paper_wallet_ledger
              (id,user_id,wallet_id,episode_id,kind,amount,currency,source_command_id)
              VALUES(:ledger,:owner,:wallet,:episode,'EXTERNAL_CAPITAL',10000,'USDT',:command)""",
            params,
        )
        await session.execute(
            """INSERT INTO paper_wallet_command_results
              (command_id,user_id,state,wallet_id,episode_id,initial_capital,balance,currency)
              VALUES(:command,:owner,'SUCCEEDED',:wallet,:episode,10000,10000,'USDT')""",
            params,
        )
        snapshot = await get_wallet(session)
    assert snapshot is not None
    assert snapshot.revision == 1
    assert not snapshot.reset_available and snapshot.reset_reason == "ACTIVITY_UNKNOWN"
    return snapshot


@pytest.fixture
def wallet(legacy_wallet: PaperWalletSnapshot) -> PaperWalletSnapshot:
    """Use the legacy baseline for the standalone F-14 test package."""
    return legacy_wallet
