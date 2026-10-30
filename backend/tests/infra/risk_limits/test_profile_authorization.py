"""Real database contract for R27's post-oracle fixture limit restoration."""

import asyncio
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_workload as f15
from tests.infra.risk_limits.profile_resources import connection_budget, returned_pools
from tests.infra.risk_limits.profile_workload import Fixture
from tiewtrade.core.money import Money
from tiewtrade.core.orders import TradingMode
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits.records import (
    RiskAction,
    RiskAuthorizationError,
    RiskConflictError,
)
from tiewtrade.infra.risk_limits.requests import receipt_by_key, submit_request
from tiewtrade.infra.risk_limits.storage import process_request


async def test_fixture_restoration_uses_verified_auth_and_applies_once(
    tmp_path: Path,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tests.infra.risk_limits.test_requests import seed_setting, submission
    from tests.infra.risk_limits.test_worker import claim

    await seed_setting(engine_engine, owner)
    key = uuid4()
    value = replace(
        submission(owner, wallet),
        action=RiskAction.INCREASE,
        key=key,
        expected_revision=1,
        amount=Money.of(1000, "USDT"),
    )
    async with user_session(api_engine, owner) as session:
        with pytest.raises(RiskAuthorizationError):
            await submit_request(session, value)
    fixture = Fixture(tmp_path)
    task = asyncio.create_task(
        fixture.mutation(
            f15.OwnerState(owner, wallet), RiskAction.INCREASE, "1000", idempotency_key=key
        )
    )
    try:
        async with asyncio.timeout(10):
            while True:
                if task.done():
                    await task
                async with user_session(api_engine, owner) as session:
                    receipt = await receipt_by_key(session, TradingMode.PAPER, key)
                if receipt is not None and not receipt.authorization_only:
                    break
                await asyncio.sleep(0.01)
            assert receipt.submission == value and receipt.authorization_id is not None
            async with user_session(fixture.auth, owner, role=DatabaseRole.AUTH) as session:
                assert (
                    await session.execute("SELECT last_accepted_step FROM user_totp")
                ).scalar_one() > 0
                assert (
                    await session.execute("SELECT count(*) FROM risk_limit_authorizations")
                ).scalar_one() == 1
            current = await claim(engine_engine, owner, receipt)
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await process_request(session, current)
            assert await task == receipt.receipt_id
        async with user_session(api_engine, owner) as session:
            row = (await session.execute("SELECT amount,revision FROM risk_limit_settings")).one()
            assert Money.of(row.amount, "USDT") == Money.of(1000, "USDT") and row.revision == 2
            observed = await get_wallet(session)
            assert observed is not None
            assert replace(observed, snapshot_at=wallet.snapshot_at) == wallet
            assert (
                await session.execute("SELECT count(*) FROM paper_position_projections")
            ).scalar_one() == 0
            assert await submit_request(session, value) == receipt
            assert (
                await session.execute("SELECT count(*) FROM risk_limit_events")
            ).scalar_one() == 1
        async with user_session(api_engine, owner) as session:
            with pytest.raises(RiskConflictError):
                await submit_request(session, replace(value, amount=Money.of(1001, "USDT")))
        budget = await connection_budget(
            fixture.migrator, [fixture.pools.path], expected_counts=[6]
        )
        auth = next(entry for entry in fixture.pools.entries if entry["role"] == "AUTH")
        assert (auth["pool_size"], auth["max_overflow"], auth["peak_checked_out"]) == (1, 0, 1)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await fixture.close()
    assert returned_pools([fixture.pools.path], budget)


@pytest.mark.parametrize("auth_target", ["missing", "remote", "other_database", "matching"])
def test_fixture_auth_is_restricted_to_same_isolated_database(
    monkeypatch: pytest.MonkeyPatch, auth_target: str
) -> None:
    from tests.infra.risk_limits.profile_workload import guard_release_database

    for role in ("API", "ENGINE", "ENGINE_SCAN", "MIGRATOR", "MARKET_DATA", "AUTH"):
        monkeypatch.setenv(
            f"TIEWTRADE_DATABASE_URL_{role}",
            "postgresql://127.0.0.1:5432/tiewtrade_f18_release_test",
        )
    if auth_target == "missing":
        monkeypatch.delenv("TIEWTRADE_DATABASE_URL_AUTH")
    elif auth_target == "remote":
        monkeypatch.setenv(
            "TIEWTRADE_DATABASE_URL_AUTH", "postgresql://example.com/tiewtrade_f18_release_test"
        )
    elif auth_target == "other_database":
        monkeypatch.setenv(
            "TIEWTRADE_DATABASE_URL_AUTH", "postgresql://127.0.0.1:5432/tiewtrade_f18_release_other"
        )
    if auth_target == "matching":
        guard_release_database()
    else:
        with pytest.raises(RuntimeError, match="ISOLATED_RELEASE_DATABASE_REQUIRED"):
            guard_release_database()
