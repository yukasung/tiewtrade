"""Manual inbox transfer, original catalog fences and owner/lease serialization."""

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_dispatch import intent
from tests.infra.execution_market.test_worker import (
    AllowPolicy,
    _restore_btc_seed_catalog,
    _simulate_btc_remove_and_readd,
    ready_public_sources,
)
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import scan_session_bypassing_rls
from tiewtrade.infra.paper_orders import request_worker
from tiewtrade.infra.paper_orders.request_dispatch import (
    DueRequest,
    RequestClaimLostError,
    claim_request,
    defer_request_claim,
    due_requests,
)
from tiewtrade.infra.paper_orders.request_worker import process_request
from tiewtrade.infra.paper_orders.requests import admit_new_request, request_audit
from tiewtrade.infra.paper_orders.views import request_view
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.services.engine.manual_order import run_manual_order_round
from tiewtrade.services.engine.paper_order import run_paper_order_round


async def select_use(engine: AsyncEngine, owner: UUID, value: str = "MANUAL") -> None:
    async with user_session(engine, owner) as session:
        await session.execute(
            "INSERT INTO user_trading_preferences(user_id,use) VALUES(:owner,:use)",
            {"owner": owner, "use": value},
        )


async def test_bridge_transfers_once_and_worker_admits_real_order(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    await select_use(api_engine, owner)
    value = intent(owner, wallet.episode_id)
    async with user_session(api_engine, owner) as session:
        receipt = await admit_new_request(session, wallet_id=wallet.wallet_id, intent=value)
    await asyncio.gather(
        *[
            run_manual_order_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                worker=f"bridge-{i}",
                policy=AllowPolicy(),
            )
            for i in range(2)
        ]
    )
    market, _, _, _ = await ready_public_sources()
    try:
        await run_paper_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="bridge-admit",
            policy=AllowPolicy(),
        )
        async with user_session(api_engine, owner) as session:
            view = await request_view(session, receipt.request_id)
            assert view is not None and view.intake_state == "TRANSFERRED"
            assert view.command_state == "SUCCEEDED" and view.order_state == "ACCEPTED"
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            count = (
                await session.execute(
                    "SELECT count(*) FROM paper_order_commands WHERE idempotency_key=:key",
                    {"key": value.idempotency_key},
                )
            ).scalar_one()
            revision = (
                await session.execute(
                    "SELECT payload->>'catalog_revision' FROM paper_order_commands WHERE id=:id",
                    {"id": view.command_id},
                )
            ).scalar_one()
            assert count == 1 and int(revision) == receipt.admitted_catalog_revision
    finally:
        await market.dispose()


@pytest.mark.parametrize("after_transfer", [False, True])
async def test_removal_readd_never_revives_inbox_buy(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    after_transfer: bool,
) -> None:
    await select_use(api_engine, owner)
    async with user_session(api_engine, owner) as session:
        receipt = await admit_new_request(
            session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
        )
    if after_transfer:
        await run_manual_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="before-removal",
            policy=AllowPolicy(),
        )
    events = await _simulate_btc_remove_and_readd(migrator_engine)
    market = None
    try:
        if after_transfer:
            market, _, _, _ = await ready_public_sources()
            await run_paper_order_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                worker="after-removal",
                policy=AllowPolicy(),
            )
        else:
            await run_manual_order_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                worker="after-removal",
                policy=AllowPolicy(),
            )
        async with user_session(api_engine, owner) as session:
            view = await request_view(session, receipt.request_id)
            assert view is not None
            code = view.command_failure_code if after_transfer else view.intake_failure_code
            assert code == "CATALOG_PAIR_REMOVED"
            assert view.order_state is None
            if not after_transfer:
                assert view.command_id is None
    finally:
        await _restore_btc_seed_catalog(migrator_engine, events)
        if market is not None:
            await market.dispose()


@pytest.mark.parametrize("use,policy", [("BOT", True), (None, True), ("MANUAL", False)])
async def test_bridge_closed_for_wrong_use_or_missing_policy(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    use: str | None,
    policy: bool,
) -> None:
    if use is not None:
        await select_use(api_engine, owner, use)
    async with user_session(api_engine, owner) as session:
        receipt = await admit_new_request(
            session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
        )
    await run_manual_order_round(
        engine=engine_engine,
        scan_engine=scan_engine,
        worker="closed",
        policy=AllowPolicy() if policy else None,
    )
    async with user_session(api_engine, owner) as session:
        view = await request_view(session, receipt.request_id)
        assert view is not None and view.intake_state == "REJECTED" and view.command_id is None
        assert view.intake_failure_code == (
            "MANUAL_USE_REQUIRED" if use != "MANUAL" else "ORDER_SAFETY_UNAVAILABLE"
        )


async def test_claim_expiry_replacement_fences_old_worker(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    await select_use(api_engine, owner)
    async with user_session(api_engine, owner) as session:
        receipt = await admit_new_request(
            session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
        )
    async with scan_session_bypassing_rls(scan_engine) as scan:
        due = next(x for x in await due_requests(scan) if x.request_id == receipt.request_id)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        first = await claim_request(session, due, worker="first")
        assert first is not None
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute(
            """UPDATE paper_order_request_dispatch
            SET lease_until=clock_timestamp()-interval '1 second'
            WHERE request_id=:id""",
            {"id": receipt.request_id},
        )
        second = await claim_request(session, due, worker="replacement")
        assert second is not None
    with pytest.raises(RequestClaimLostError):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_request(session, first, policy=AllowPolicy())
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await defer_request_claim(session, first)
        await process_request(session, second, policy=AllowPolicy())
    async with user_session(api_engine, owner) as session:
        view = await request_view(session, receipt.request_id)
        assert view is not None and view.intake_state == "TRANSFERRED"


async def test_audit_failure_rolls_back_both_queues_then_same_claim_recovers(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await select_use(api_engine, owner)
    value = intent(owner, wallet.episode_id)
    async with user_session(api_engine, owner) as session:
        receipt = await admit_new_request(session, wallet_id=wallet.wallet_id, intent=value)
    async with scan_session_bypassing_rls(scan_engine) as scan:
        due = next(x for x in await due_requests(scan) if x.request_id == receipt.request_id)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        claim = await claim_request(session, due, worker="crash-before-commit")
        assert claim is not None
    original = request_audit

    async def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit failure")

    monkeypatch.setattr(request_worker, "request_audit", fail)
    with pytest.raises(RuntimeError, match="audit failure"):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_request(session, claim, policy=AllowPolicy())
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert (
            await session.execute(
                "SELECT count(*) FROM paper_order_commands WHERE idempotency_key=:key",
                {"key": value.idempotency_key},
            )
        ).scalar_one() == 0
    monkeypatch.setattr(request_worker, "request_audit", original)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await process_request(session, claim, policy=AllowPolicy())
    async with user_session(api_engine, owner) as session:
        view = await request_view(session, receipt.request_id)
        assert view is not None and view.intake_state == "TRANSFERRED"


async def test_engine_account_use_read_is_owner_scoped_and_read_only(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
) -> None:
    from tiewtrade.infra.db import InfraError
    from tiewtrade.infra.users import create_user

    await select_use(api_engine, owner)
    other = uuid4()
    await create_user(api_engine, other)
    async with user_session(engine_engine, other, role=DatabaseRole.ENGINE) as session:
        assert (
            await session.execute(
                "SELECT use FROM user_trading_preferences WHERE user_id=:owner", {"owner": owner}
            )
        ).scalar_one_or_none() is None
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert (
            await session.execute("SELECT use FROM user_trading_preferences")
        ).scalar_one() == "MANUAL"
    with pytest.raises(InfraError):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                "UPDATE user_trading_preferences SET use='BOT' WHERE user_id=:owner",
                {"owner": owner},
            )


async def test_reset_cannot_cross_the_inbox_to_financial_queue_transition(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from collections.abc import Mapping
    from typing import Any

    from sqlalchemy import Result

    from tiewtrade.infra.db.session import UserSession
    from tiewtrade.infra.paper_wallet import (
        PaperWalletAction,
        admit_command,
        get_command,
        get_wallet,
    )
    from tiewtrade.services.engine.paper_wallet import run_paper_wallet_round

    await select_use(api_engine, owner)
    async with user_session(api_engine, owner) as session:
        receipt = await admit_new_request(
            session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
        )
        reset = await admit_command(
            session,
            action=PaperWalletAction.RESET,
            idempotency_key=uuid4(),
            capital_text="5000",
            expected_episode_id=wallet.episode_id,
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        due_at = (
            await session.execute(
                "SELECT next_attempt_at FROM paper_order_request_dispatch WHERE request_id=:id",
                {"id": receipt.request_id},
            )
        ).scalar_one()
        due = DueRequest(receipt.request_id, owner, due_at)
        claim = await claim_request(session, due, worker="transfer-reset-race")
        assert claim is not None
    waiting = asyncio.Event()
    original = UserSession.execute

    async def observe(
        session: UserSession, statement: str, parameters: Mapping[str, object] | None = None
    ) -> Result[Any]:
        if (
            session.user_id == owner
            and "pg_advisory_xact_lock(hashtextextended(:scope" in statement
        ):
            waiting.set()
        return await original(session, statement, parameters)

    monkeypatch.setattr(UserSession, "execute", observe)
    task = None
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_request(session, claim, policy=AllowPolicy())
            task = asyncio.create_task(
                run_paper_wallet_round(
                    engine=engine_engine, scan_engine=scan_engine, worker="reset-waits-for-transfer"
                )
            )
            await asyncio.wait_for(waiting.wait(), 10)
            assert not task.done()
            # MVCC readers still see the pending inbox until the transfer commits.
            async with user_session(api_engine, owner) as reader:
                before = await get_wallet(reader)
                assert before is not None and not before.reset_available
        await asyncio.wait_for(task, 10)
        async with user_session(api_engine, owner) as session:
            result = await get_command(session, reset.command_id)
            snapshot = await get_wallet(session)
            assert result is not None and result.failure_code == "RESET_UNSAFE"
            assert snapshot is not None and snapshot.episode_id == wallet.episode_id
            assert not snapshot.reset_available
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_transferred_request_rechecks_missing_policy_at_execution(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    await select_use(api_engine, owner)
    async with user_session(api_engine, owner) as session:
        receipt = await admit_new_request(
            session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
        )
    await run_manual_order_round(
        engine=engine_engine, scan_engine=scan_engine, worker="ready-bridge", policy=AllowPolicy()
    )
    market, _, _, _ = await ready_public_sources()
    try:
        await run_paper_order_round(
            engine=engine_engine, scan_engine=scan_engine, worker="closed-execution", policy=None
        )
        async with user_session(api_engine, owner) as session:
            result = await request_view(session, receipt.request_id)
            assert result is not None and result.intake_state == "TRANSFERRED"
            assert result.command_state == "REJECTED"
            assert result.command_failure_code == "ORDER_SAFETY_UNAVAILABLE"
            assert result.order_state is None
    finally:
        await market.dispose()


async def test_competing_inbox_orders_cannot_overreserve_cash(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from dataclasses import replace

    from tiewtrade.core.money import Money, Quantity
    from tiewtrade.core.orders import BaseSize, OrderType, TimeInForce
    from tiewtrade.infra.paper_orders.dispatch import DueOrder, claim_order
    from tiewtrade.infra.paper_orders.worker import process_claimed_order

    await select_use(api_engine, owner)

    async def intake() -> UUID:
        value = replace(
            intent(owner, wallet.episode_id),
            kind=OrderType.LIMIT,
            size=BaseSize(Quantity.of(1, "BTC")),
            limit_price=Money.of(9000, "USDT"),
            time_in_force=TimeInForce.GTC,
        )
        async with user_session(api_engine, owner) as session:
            receipt = await admit_new_request(session, wallet_id=wallet.wallet_id, intent=value)
            return receipt.request_id

    requests = await asyncio.gather(intake(), intake())
    # The fair scanner intentionally transfers at most one request per owner/round.
    for _ in requests:
        await run_manual_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="overspend-bridge",
            policy=AllowPolicy(),
        )
    commands = []
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        for request_id in requests:
            view = await request_view(session, request_id)
            assert view is not None and view.command_id is not None
            commands.append(view.command_id)
    market, _, _, _ = await ready_public_sources()
    try:

        async def execute(command_id: UUID) -> bool:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                due_at = (
                    await session.execute(
                        "SELECT next_attempt_at FROM paper_order_dispatch WHERE command_id=:id",
                        {"id": command_id},
                    )
                ).scalar_one()
                claim = await claim_order(
                    session, DueOrder(command_id, owner, due_at), worker="competing-command"
                )
                if claim is None:
                    return False
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await process_claimed_order(session, claim, policy=AllowPolicy())
            return True

        executed = await asyncio.gather(*(execute(command_id) for command_id in commands))
        for command_id, done in zip(commands, executed, strict=True):
            if not done:
                assert await execute(command_id)
        async with user_session(api_engine, owner) as session:
            views = [await request_view(session, request_id) for request_id in requests]
            assert sorted(
                v.command_state for v in views if v is not None and v.command_state is not None
            ) == [
                "REJECTED",
                "SUCCEEDED",
            ]
            rejected = next(v for v in views if v is not None and v.command_state == "REJECTED")
            assert rejected.command_failure_code == "ORDER_INSUFFICIENT_FUNDS"
            reserved = (
                await session.execute(
                    "SELECT sum(quote_reserved) FROM paper_reservations WHERE episode_id=:episode",
                    {"episode": wallet.episode_id},
                )
            ).scalar_one()
            assert Money.of(reserved, "USDT") == Money.of(9000, "USDT")
    finally:
        await market.dispose()


async def test_unavailable_manual_scan_does_not_stop_financial_worker_loop(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from tiewtrade.infra.db.errors import DatabaseTimeoutError
    from tiewtrade.services.engine import manual_order

    async def unavailable(*args: object, **kwargs: object) -> None:
        raise DatabaseTimeoutError("private database exception")

    monkeypatch.setattr(manual_order, "due_requests", unavailable)
    result = await run_manual_order_round(
        engine=engine_engine, scan_engine=scan_engine, worker="scan-outage", policy=None
    )
    assert result.processed == 0
    assert "manual request scan unavailable" in caplog.text
    assert "private database exception" not in caplog.text
