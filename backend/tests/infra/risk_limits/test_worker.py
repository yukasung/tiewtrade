import asyncio
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.risk_limits.test_requests import seed_setting, submission
from tiewtrade.core.money import Money
from tiewtrade.core.orders import TradingMode
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits import storage
from tiewtrade.infra.risk_limits.dispatch import (
    DueRiskRequest,
    RiskClaim,
    RiskClaimLostError,
    claim_request,
)
from tiewtrade.infra.risk_limits.records import RiskAction, RiskReceipt
from tiewtrade.infra.risk_limits.requests import authorize_increase, submit_request
from tiewtrade.infra.risk_limits.storage import process_request


async def claim(engine: AsyncEngine, owner: UUID, receipt: RiskReceipt) -> RiskClaim:
    due = DueRiskRequest(receipt.receipt_id, owner, receipt.submission.scope.mode)
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        result = await claim_request(session, due, worker="risk-worker-test")
    assert result is not None
    return result


async def test_amount_application_is_atomic_and_duplicate_worker_cannot_reapply(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(api_engine, owner) as session:
        receipt = await submit_request(session, submission(owner, wallet))
    current = await claim(engine_engine, owner, receipt)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await process_request(session, current)
    with pytest.raises(RiskClaimLostError):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_request(session, current)
    async with user_session(api_engine, owner) as session:
        row = (await session.execute("SELECT * FROM risk_limit_settings")).one()
        assert row.revision == 1 and Money.of(row.amount, "USDT") == Money.of(100, "USDT")
        result = (await session.execute("SELECT * FROM risk_limit_results")).one()
        assert result.state == "APPLIED" and result.revision == 1
        assert (await session.execute("SELECT count(*) FROM risk_limit_events")).scalar_one() == 1
        evaluation = (await session.execute("SELECT * FROM risk_limit_evaluations")).one()
        assert evaluation.reason == "RISK_SOURCE_UNAVAILABLE" and evaluation.replay_pending


async def test_audit_failure_rolls_back_setting_event_result_and_terminal_transition(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with user_session(api_engine, owner) as session:
        receipt = await submit_request(session, submission(owner, wallet))
    current = await claim(engine_engine, owner, receipt)

    async def audit_failure(*args: object, **kwargs: object) -> None:
        raise RuntimeError("controlled audit write failure")

    with monkeypatch.context() as patch:
        patch.setattr(storage, "record_event", audit_failure)
        with pytest.raises(RuntimeError):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await process_request(session, current)
    async with user_session(api_engine, owner) as session:
        for table in ("risk_limit_settings", "risk_limit_events", "risk_limit_results"):
            assert (await session.execute(f"SELECT count(*) FROM {table}")).scalar_one() == 0
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await process_request(session, current)


async def test_concurrent_claim_has_one_winner_and_expired_worker_loses_fence(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(api_engine, owner) as session:
        receipt = await submit_request(session, submission(owner, wallet))
    due = DueRiskRequest(receipt.receipt_id, owner, TradingMode.PAPER)

    async def take(worker: str) -> RiskClaim | None:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            return await claim_request(session, due, worker=worker)

    claims = await asyncio.gather(take("first"), take("second"))
    winners = [value for value in claims if value is not None]
    assert len(winners) == 1
    old = winners[0]
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute(
            "UPDATE risk_limit_dispatch SET lease_until=clock_timestamp()-interval '1 second'"
        )
    fresh = await take("replacement")
    assert fresh is not None and fresh.revision == old.revision + 1
    with pytest.raises(RiskClaimLostError):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_request(session, old)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await process_request(session, fresh)


async def test_queued_setting_change_is_rejected_when_another_request_wins_revision(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    first_value = submission(owner, wallet)
    async with user_session(api_engine, owner) as session:
        first = await submit_request(session, first_value)
        second = await submit_request(
            session, replace(first_value, key=uuid4(), amount=Money.of(200, "USDT"))
        )
    for receipt in (first, second):
        current = await claim(engine_engine, owner, receipt)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_request(session, current)
    async with user_session(api_engine, owner) as session:
        assert Money.of(
            (await session.execute("SELECT amount FROM risk_limit_settings")).scalar_one(), "USDT"
        ) == Money.of(100, "USDT")
        row = (
            await session.execute(
                "SELECT state,failure_code FROM risk_limit_results WHERE request_id=:id",
                {"id": second.receipt_id},
            )
        ).one()
        assert row.state == "REJECTED" and row.failure_code == "RISK_REVISION_CONFLICT"


async def test_limit_edits_and_unavailable_reset_never_clear_an_existing_latch(
    api_engine: AsyncEngine,
    auth_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    await seed_setting(engine_engine, owner)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute("UPDATE risk_limit_settings SET latched=true")
    decrease = replace(
        submission(owner, wallet),
        action=RiskAction.DECREASE,
        expected_revision=1,
        amount=Money.of(50, "USDT"),
    )
    increase = replace(
        decrease,
        action=RiskAction.INCREASE,
        key=uuid4(),
        expected_revision=2,
        amount=Money.of(200, "USDT"),
    )
    reset = replace(
        decrease, action=RiskAction.RESET, key=uuid4(), expected_revision=3, amount=None
    )
    for value in (decrease, increase, reset):
        if value.action is RiskAction.INCREASE:
            async with user_session(auth_engine, owner, role=DatabaseRole.AUTH) as session:
                await authorize_increase(session, value)
        async with user_session(api_engine, owner) as session:
            receipt = await submit_request(session, value)
        current = await claim(engine_engine, owner, receipt)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_request(session, current)
    async with user_session(api_engine, owner) as session:
        row = (
            await session.execute("SELECT amount,revision,latched FROM risk_limit_settings")
        ).one()
        assert Money.of(row.amount, "USDT") == Money.of(200, "USDT")
        assert row.revision == 3 and row.latched
        rejected = (
            await session.execute(
                "SELECT failure_code FROM risk_limit_results WHERE request_id=:id",
                {"id": receipt.receipt_id},
            )
        ).scalar_one()
        assert rejected == "RISK_SOURCE_UNAVAILABLE"
