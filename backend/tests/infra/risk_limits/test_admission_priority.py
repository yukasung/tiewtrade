"""R10 bounded priority before the hint cut, with normal cross-owner progress."""

import asyncio
from dataclasses import replace
from itertools import islice
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_workload as f15
from tests.infra.risk_limits.test_execution import drive, fill_buy
from tests.infra.risk_limits.test_same_pair_dispatch import Queue, resting
from tests.infra.risk_limits.test_same_pair_dispatch import queue as queue
from tests.infra.risk_limits.test_scheduler import another_wallet, ready
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import BaseSize
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.core.risk_limits import RiskUnavailableError
from tiewtrade.infra.db import DatabaseRole, scan_session_bypassing_rls, user_session
from tiewtrade.infra.paper_orders.dispatch import due_orders, submit_cancel, submit_order
from tiewtrade.infra.risk_limits import monitor
from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy
from tiewtrade.services.engine import paper_order_main as runtime
from tiewtrade.services.engine.paper_order import matching_round_modes, run_paper_order_round


@pytest.mark.parametrize("queue", [True], indirect=True)
async def test_priority_includes_owner_outside_original_twenty_heads(
    queue: Queue, api_engine: AsyncEngine, engine_engine: AsyncEngine, scan_engine: AsyncEngine
) -> None:
    owners = [uuid4() for _ in range(20)]
    try:
        for owner in owners:
            wallet = await another_wallet(api_engine, engine_engine, scan_engine, owner)
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await submit_order(
                    session, wallet_id=wallet.wallet_id, intent=resting(owner, wallet.episode_id)
                )
                await session.execute(
                    "UPDATE paper_order_dispatch SET next_attempt_at="
                    "clock_timestamp()-interval '2 days'"
                )
        async with scan_session_bypassing_rls(scan_engine) as session:
            r8 = await due_orders(session)
            r9 = await due_orders(session, prefer_same_pair=True)
            priority = await due_orders(session, prefer_same_pair=True, admission_first=True)
        assert len(r8) == len(r9) == len(priority) == 20
        assert queue.owner not in {row.user_id for row in r8}
        assert r9 == r8  # R9's original global head order is preserved.
        assert priority[0].command_id == queue.new.command_id
        assert priority[0].anchor_command_id == queue.head.command_id
        assert priority[0].anchor_due_at == queue.due
        assert priority[1:] == r8[:19]
    finally:
        for owner in owners:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await session.execute("UPDATE paper_order_dispatch SET state='TERMINAL'")


@pytest.mark.parametrize("queue", [True], indirect=True)
@pytest.mark.parametrize("work", ["resting", "cancel", "reduction"])
async def test_priority_stream_keeps_cross_owner_normal_progress(
    queue: Queue,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    work: str,
) -> None:
    owner = uuid4()
    wallet = await another_wallet(api_engine, engine_engine, scan_engine, owner)
    try:
        async with user_session(api_engine, owner) as session:
            await session.execute(
                "INSERT INTO user_trading_preferences(user_id,use) VALUES(:id,'MANUAL')",
                {"id": owner},
            )
        await ready(engine_engine, owner, wallet)
        value = resting(owner, wallet.episode_id)
        if work == "reduction":
            await fill_buy(api_engine, engine_engine, owner, wallet, queue.sources)
            value = replace(
                value,
                side=ExecutionSide.SELL,
                size=BaseSize(Quantity.of("0.5", "BTC")),
                limit_price=Money.of(99, "USDT"),
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        await drive(engine_engine, owner, command.command_id)
        if work == "cancel":
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                command = await submit_cancel(
                    session,
                    wallet_id=wallet.wallet_id,
                    episode_id=wallet.episode_id,
                    order_id=value.order_id,
                    idempotency_key=uuid4(),
                )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            held = Quantity.of(
                (
                    await session.execute(
                        "SELECT coalesce(sum(held_quantity),0) FROM paper_position_projections"
                    )
                ).scalar_one(),
                "BTC",
            )
            cash = Money.of(
                (await session.execute("SELECT sum(amount) FROM paper_wallet_ledger")).scalar_one(),
                "USDT",
            )
        for index in range(3 if work == "resting" else 1):
            await asyncio.sleep(0.21)
            await queue.sources.next_book()
            await queue.sources.price("100")
            if index:
                async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as s:
                    await submit_order(
                        s,
                        wallet_id=queue.wallet.wallet_id,
                        intent=resting(queue.owner, queue.wallet.episode_id),
                    )
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await session.execute(
                    "UPDATE paper_order_dispatch SET next_attempt_at="
                    "clock_timestamp()+interval '1 hour' WHERE state<>'TERMINAL'"
                )
                old_due = (
                    await session.execute(
                        "UPDATE paper_order_dispatch SET next_attempt_at="
                        "clock_timestamp()-interval '2 days' WHERE command_id=:id "
                        "RETURNING next_attempt_at",
                        {"id": command.command_id},
                    )
                ).scalar_one()
            result = await run_paper_order_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                worker="r10-priority",
                policy=TransactionalRiskPolicy(),
                claim_limit=1,
                prefer_same_pair=True,
                admission_first=True,
            )
            assert result.processed == 1 and result.deferred == 0
            # A following ordinary round must service the older other owner,
            # even while new admissions continue on the preferred owner's pair.
            with monkeypatch.context() as patch:
                if work == "reduction":
                    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as s:
                        await s.execute("UPDATE risk_owner_state SET replay_pending=true")
                    patch.setattr(
                        monitor,
                        "read_frames",
                        AsyncMock(side_effect=RiskUnavailableError("controlled risk gap")),
                    )
                normal = await run_paper_order_round(
                    engine=engine_engine,
                    scan_engine=scan_engine,
                    worker="r10-normal",
                    policy=TransactionalRiskPolicy(),
                    claim_limit=1,
                )
            assert normal.processed == 1 and normal.deferred == 0
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                row = (
                    await session.execute(
                        "SELECT state,next_attempt_at FROM paper_order_dispatch "
                        "WHERE command_id=:id",
                        {"id": command.command_id},
                    )
                ).one()
                assert row.next_attempt_at > old_due
                if work == "cancel":
                    assert row.state == "TERMINAL"
                    assert (
                        await session.execute(
                            "SELECT status FROM paper_order_projections WHERE order_id=:id",
                            {"id": value.order_id},
                        )
                    ).scalar_one() == "CANCELED"
                    assert Money.of(
                        (
                            await session.execute(
                                "SELECT sum(quote_reserved) FROM paper_reservations"
                            )
                        ).scalar_one(),
                        "USDT",
                    ) == Money.of(0, "USDT")
                if work == "reduction":
                    assert Quantity.of(
                        (
                            await session.execute(
                                "SELECT sum(held_quantity) FROM paper_position_projections"
                            )
                        ).scalar_one(),
                        "BTC",
                    ) == held - Quantity.of("0.5", "BTC")
                    assert Money.of(
                        (
                            await session.execute("SELECT sum(amount) FROM paper_wallet_ledger")
                        ).scalar_one(),
                        "USDT",
                    ) == cash + Money.of("49.4505", "USDT")
    finally:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute("UPDATE paper_order_dispatch SET state='TERMINAL'")


def test_round_modes_keep_legacy_and_r9_defaults_and_validate_options() -> None:
    assert list(islice(matching_round_modes(), 3)) == [(False, False)] * 3
    assert list(islice(matching_round_modes(prefer_same_pair=True), 3)) == [(True, False)] * 3
    for kwargs in (
        {"alternate_admission": 1},
        {"prefer_same_pair": True, "alternate_admission": True},
    ):
        with pytest.raises(ValueError):
            matching_round_modes(**kwargs)


@pytest.mark.parametrize("driver", ["production", "harness"])
async def test_actual_loops_alternate_after_success_skip_defer_and_restart_legacy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, driver: str
) -> None:
    module = runtime if driver == "production" else f15
    engine = SimpleNamespace(sync_engine=Mock(), dispose=AsyncMock())
    stop = tmp_path / "stop"
    modes = []
    monkeypatch.setattr(module, "create_engine_for", lambda role: engine)
    monkeypatch.setattr(module, "run_manual_order_round", AsyncMock())
    monkeypatch.setattr(event, "listens_for", lambda *args, **kwargs: lambda fn: fn)
    monkeypatch.setattr(runtime, "ALTERNATE_ADMISSION_PRIORITY", True)

    async def paper(**kwargs: Any) -> Any:
        modes.append((kwargs["prefer_same_pair"], kwargs["admission_first"]))
        assert kwargs["claim_limit"] == 1 and kwargs["limit"] == 20
        if len(modes) == 4:
            raise asyncio.CancelledError
        return SimpleNamespace(
            processed=int(len(modes) == 1),
            skipped=int(len(modes) == 2),
            deferred=int(len(modes) == 3),
        )

    monkeypatch.setattr(module, "run_paper_order_round", paper)

    async def run() -> None:
        if driver == "production":
            await runtime.serve()
        else:
            await f15.run_worker_process(
                "r10-loop",
                stop,
                tmp_path / "metrics.json",
                manual_intake=True,
                round_limit=20,
                claim_limit=1,
                alternate_admission=True,
            )

    with pytest.raises(asyncio.CancelledError):
        await run()
    assert modes == [(False, False), (True, True), (False, False), (True, True)]

    async def scan_failure(**kwargs: Any) -> None:
        modes.append((kwargs["prefer_same_pair"], kwargs["admission_first"]))
        raise RuntimeError("controlled scan failure")

    monkeypatch.setattr(module, "run_paper_order_round", scan_failure)
    with pytest.raises(RuntimeError, match="controlled scan failure"):
        await run()
    assert modes[-1] == (False, False)
