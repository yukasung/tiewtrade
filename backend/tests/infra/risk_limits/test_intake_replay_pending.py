"""Bounded replay progress and queued-intake deferral share one atomic commit."""

from collections.abc import AsyncIterator
from dataclasses import replace
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_dispatch import intent
from tests.infra.risk_limits.test_execution import runtime
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import ScanSession, UserSession
from tiewtrade.infra.paper_orders.request_dispatch import (
    ClaimedRequest,
    DueRequest,
    defer_request_claim,
    due_requests,
)
from tiewtrade.infra.paper_orders.requests import admit_new_request
from tiewtrade.infra.paper_orders.views import request_view
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy
from tiewtrade.services.engine import manual_order
from tiewtrade.services.engine.manual_order import run_manual_order_round


@pytest.fixture(autouse=True)
async def own_intake_candidates(
    monkeypatch: pytest.MonkeyPatch, owner: UUID, engine_engine: AsyncEngine
) -> AsyncIterator[None]:
    original = due_requests

    async def own(scan: ScanSession, *, limit: int = 20) -> tuple[DueRequest, ...]:
        return tuple(hint for hint in await original(scan, limit=limit) if hint.user_id == owner)

    monkeypatch.setattr(manual_order, "due_requests", own)
    yield
    # These tests prove transfer, before native financial execution. Retire only
    # this owner's mutable test dispatch so later global scanners stay isolated.
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute("""UPDATE paper_order_dispatch SET state='TERMINAL',
          worker=NULL,claim_id=NULL,lease_until=NULL""")
        await session.execute("""UPDATE paper_order_request_dispatch SET state='TERMINAL',
          worker=NULL,claim_id=NULL,lease_until=NULL""")


@pytest.mark.parametrize("rollback", [False, True])
async def test_pending_replay_commits_progress_then_transfers_exactly_once(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
    rollback: bool,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"
    ) as sources:
        async with user_session(api_engine, owner) as session:
            receipt = await admit_new_request(
                session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
            )
            before = await get_wallet(session)
            assert before is not None
            cursor = (await session.execute("SELECT cursor FROM risk_owner_state")).scalar_one()
        for _ in range(51):
            await sources.price("100")
        if rollback:
            from tiewtrade.infra.paper_orders import request_worker

            original = defer_request_claim

            async def fail_after_defer(session: UserSession, claim: ClaimedRequest) -> None:
                await original(session, claim)
                raise RuntimeError("rollback pending progress")

            with monkeypatch.context() as patch:
                patch.setattr(request_worker, "defer_request_claim", fail_after_defer)
                failed = await run_manual_order_round(
                    engine=engine_engine,
                    scan_engine=scan_engine,
                    worker="rollback",
                    policy=TransactionalRiskPolicy(),
                )
                assert failed.deferred == 1
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                assert (
                    await session.execute("SELECT cursor FROM risk_owner_state")
                ).scalar_one() == cursor
                await session.execute(
                    "UPDATE paper_order_request_dispatch SET next_attempt_at=clock_timestamp()"
                )
        result = await run_manual_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="pending",
            policy=TransactionalRiskPolicy(),
        )
        assert (result.processed, result.deferred) == (0, 1)
        async with user_session(api_engine, owner) as session:
            view = await request_view(session, receipt.request_id)
            assert view is not None and view.intake_state == "PENDING" and view.command_id is None
            current = await get_wallet(session)
            assert current is not None
            assert (
                replace(current, snapshot_at=before.snapshot_at, revision=before.revision) == before
            )
            state = (
                await session.execute("SELECT cursor,replay_pending FROM risk_owner_state")
            ).one()
            assert state.cursor == cursor + 100 and state.replay_pending
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            dispatch = (
                await session.execute("""SELECT state,attempts,claim_id,
              next_attempt_at>clock_timestamp() AS backoff FROM paper_order_request_dispatch""")
            ).one()
            assert tuple(dispatch) == ("PENDING", 2 if rollback else 1, None, True)
            await session.execute(
                "UPDATE paper_order_request_dispatch SET next_attempt_at=clock_timestamp()"
            )
        result = await run_manual_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="retry",
            policy=TransactionalRiskPolicy(),
        )
        assert (result.processed, result.deferred) == (1, 0)
        again = await run_manual_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="again",
            policy=TransactionalRiskPolicy(),
        )
        assert again.processed == 0
        async with user_session(api_engine, owner) as session:
            view = await request_view(session, receipt.request_id)
            assert view is not None and view.intake_state == "TRANSFERRED"
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == 1
            current = await get_wallet(session)
            assert current is not None
            assert (
                replace(current, snapshot_at=before.snapshot_at, revision=before.revision) == before
            )


@pytest.mark.parametrize("fault", ["integrity", "wrong_use", "breach"])
async def test_pending_retry_does_not_replace_terminal_safety_refusals(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    from unittest.mock import AsyncMock

    from tests.infra.risk_limits.test_execution import fill_buy
    from tiewtrade.core.risk_limits import RiskUnavailableError
    from tiewtrade.infra.risk_limits import monitor

    async with runtime(
        api_engine,
        engine_engine,
        migrator_engine,
        owner,
        wallet,
        limit="0.01" if fault == "breach" else "1000",
        account_use="BOT" if fault == "wrong_use" else "MANUAL",
    ) as sources:
        if fault == "breach":
            await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        async with user_session(api_engine, owner) as session:
            receipt = await admit_new_request(
                session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
            )
        for _ in range(51):
            await sources.price("50" if fault == "breach" else "100")
        if fault == "integrity":
            monkeypatch.setattr(
                monitor, "read_frames", AsyncMock(side_effect=RiskUnavailableError("corrupt frame"))
            )
        result = await run_manual_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="refuse",
            policy=TransactionalRiskPolicy(),
        )
        assert (result.processed, result.deferred) == (1, 0)
        async with user_session(api_engine, owner) as session:
            view = await request_view(session, receipt.request_id)
            assert view is not None and view.intake_state == "REJECTED" and view.command_id is None
            if fault == "breach":
                assert (
                    await session.execute("SELECT latched FROM risk_limit_settings")
                ).scalar_one()
