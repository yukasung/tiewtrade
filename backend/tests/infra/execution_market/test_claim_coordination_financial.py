"""Run existing financial oracles unchanged through the NC10 opt-in orchestration."""

import inspect
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.positions import ExecutionSide
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.services.engine.paper_order import run_paper_order_round


@pytest.mark.usefixtures("internal_database")
@pytest.mark.parametrize(
    "scenario,fault,side",
    [
        ("accept_restart_fill_and_cash_are_atomic", None, None),
        ("accept_restart_fill_and_cash_are_atomic", "lost_commit_reply", None),
        ("accept_restart_fill_and_cash_are_atomic", "commit_disconnect", None),
        ("accept_restart_fill_and_cash_are_atomic", "projections", None),
        ("fill_and_reset_linearize_on_the_financial_lock", None, None),
        ("downstream_position_conflict_is_durable_without_partial_fill", None, None),
        ("cancel_before_next_input_releases_remaining_reservation", None, None),
        ("duplicate_order_identity_is_terminal_and_does_not_block_cancel", None, None),
        ("two_orders_cannot_reserve_the_same_available_funds", None, ExecutionSide.BUY),
        ("two_orders_cannot_reserve_the_same_available_funds", None, ExecutionSide.SELL),
    ],
)
async def test_existing_financial_oracle_with_coordinated_selection(
    monkeypatch: pytest.MonkeyPatch,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    scenario: str,
    fault: str | None,
    side: ExecutionSide | None,
) -> None:
    from tests.infra.execution_market import test_worker as existing

    calls = 0

    async def coordinated(**kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return await run_paper_order_round(
            **{**kwargs, "coordinate_claims": True, "claim_limit": 1}
        )

    monkeypatch.setattr(existing, "run_paper_order_round", coordinated)
    oracle = getattr(existing, f"test_{scenario}")
    arguments = {
        "monkeypatch": monkeypatch,
        "api_engine": api_engine,
        "engine_engine": engine_engine,
        "scan_engine": scan_engine,
        "owner": owner,
        "wallet": wallet,
        "fault": fault,
        "side": side,
    }
    try:
        await oracle(**{name: arguments[name] for name in inspect.signature(oracle).parameters})
        assert calls > 0
    finally:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute("""UPDATE paper_order_dispatch SET state='TERMINAL',
              worker=NULL,claim_id=NULL,lease_until=NULL""")
