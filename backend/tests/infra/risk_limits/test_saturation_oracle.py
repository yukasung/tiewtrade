"""SQL/role contract: an unknown admitted request cannot pass the R28 ID oracle."""

from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_workload as f15
from tests.infra.risk_limits.profile_saturation import Progress, verify_identities
from tiewtrade.infra.db import user_session
from tiewtrade.infra.paper_orders.requests import admit_new_request
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot


async def test_exact_identity_query_observes_owner_pending_request(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    tmp_path: Path,
) -> None:
    state = f15.OwnerState(owner, wallet)
    run = uuid4()
    progress = Progress([owner], 0)
    assert await verify_identities(
        engine_engine, [state], run, progress, 0, {}, tmp_path / "empty.json"
    )
    async with user_session(api_engine, owner) as session:
        await admit_new_request(
            session, wallet_id=UUID(str(wallet.wallet_id)), intent=f15.baseline(state, run, 0)
        )
    # Expected key/order are correct, but the durable request has no transfer/result.
    assert not await verify_identities(
        engine_engine, [state], run, progress, 1, {}, tmp_path / "pending.json"
    )


async def test_economic_snapshot_reads_canonical_ledger_balance_on_final_schema(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    state = f15.OwnerState(owner, wallet)
    before = await f15.economic_snapshot(engine_engine, [state])
    after = await f15.economic_snapshot(engine_engine, [state])
    assert before == after
    assert before == [
        {
            "fills": 0,
            "ledger_rows": 1,
            "position_events": 0,
            "balance": wallet.balance.as_parts()["amount"],
        }
    ]
