"""The release acceptance gate must reject late, incomplete and rolled-back evidence."""

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_workload as f15
from tests.infra.risk_limits.profile_workload import sla_summary, telemetry
from tests.infra.risk_limits.test_monitor import start
from tests.infra.risk_limits.test_prices import publication as publication
from tests.infra.risk_limits.test_requests import seed_setting, submission
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits.monitor import initialize_monitor
from tiewtrade.infra.risk_limits.storage import read_setting


def inputs(path: Path) -> None:
    rows = [
        {"kind": "PRICE", "cursor": 1, "ready_at": "2026-10-26T00:00:00+00:00", "measured": True},
        {
            "kind": "PRICE",
            "cursor": 2,
            "ready_at": "2026-10-26T00:00:00.200+00:00",
            "measured": True,
        },
    ]
    (path / "inputs.jsonl").write_text("\n".join(json.dumps(row) for row in rows))


def test_one_late_decision_cannot_be_hidden_by_a_fast_average(tmp_path: Path) -> None:
    owner = uuid4()
    inputs(tmp_path)
    (tmp_path / "monitor.risk.jsonl").write_text(
        json.dumps(
            {
                "owner": str(owner),
                "cursor": 2,
                "boundary": 0,
                "pending": False,
                "committed_observed_at": "2026-10-26T00:00:03.001+00:00",
            }
        )
        + "\n"
    )
    result = sla_summary(tmp_path, [owner])
    assert result["samples"] == result["expected"] == 2
    assert result["service_miss_count"] == 1 and result["miss_count"] == 0
    assert result["max_seconds"] == 3.001
    assert result["passed"] is False


@pytest.mark.parametrize(
    ("seconds", "target_misses", "service_misses", "hard_misses"),
    [
        ("01.000", 0, 0, 0),
        ("01.001", 1, 0, 0),
        ("02.000", 2, 0, 0),
        ("02.001", 2, 0, 0),
        ("03.000", 2, 0, 0),
        ("03.001", 2, 1, 0),
        ("05.000", 2, 2, 0),
        ("05.001", 2, 2, 1),
        ("05.201", 2, 2, 2),
    ],
)
def test_paper_hard_bound_and_target_are_reported_separately(
    tmp_path: Path, seconds: str, target_misses: int, service_misses: int, hard_misses: int
) -> None:
    owner = uuid4()
    inputs(tmp_path)
    (tmp_path / "monitor.risk.jsonl").write_text(
        json.dumps(
            {
                "owner": str(owner),
                "cursor": 2,
                "boundary": 0,
                "pending": False,
                "committed_observed_at": f"2026-10-26T00:00:{seconds}+00:00",
            }
        )
        + "\n"
    )
    result = sla_summary(tmp_path, [owner])
    assert result["hard_limit_seconds"] == 5 and result["target_seconds"] == 1
    assert result["target_miss_count"] == target_misses
    assert result["service_miss_count"] == service_misses
    assert result["miss_count"] == hard_misses
    assert result["passed"] is (hard_misses == 0 and service_misses == 0)


def test_missing_acknowledgements_still_fail_the_acceptance_gate(tmp_path: Path) -> None:
    owner = uuid4()
    inputs(tmp_path)
    result = sla_summary(tmp_path, [owner])
    assert result["unacknowledged"] == 2
    assert result["passed"] is False


def test_pending_replay_is_not_a_durable_ready_acknowledgement(tmp_path: Path) -> None:
    owner = uuid4()
    inputs(tmp_path)
    (tmp_path / "monitor.risk.jsonl").write_text(
        json.dumps(
            {
                "owner": str(owner),
                "cursor": 2,
                "boundary": 0,
                "pending": True,
                "committed_observed_at": "2026-10-26T00:00:00.500+00:00",
            }
        )
        + "\n"
    )
    result = sla_summary(tmp_path, [owner])
    assert result["samples"] == 0 and result["unacknowledged"] == 2
    assert result["passed"] is False


async def test_savepoint_rollback_does_not_emit_a_commit_proof(
    tmp_path: Path,
    engine_engine: AsyncEngine,
    publication: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    await start(publication)
    await seed_setting(engine_engine, owner)
    path = tmp_path / "rollback.risk.jsonl"
    async with (
        telemetry(path),
        user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session,
    ):
        await session.execute("SAVEPOINT abandoned_evaluation")
        setting = await read_setting(session, submission(owner, wallet).scope)
        await initialize_monitor(session, setting)
        await session.execute("ROLLBACK TO SAVEPOINT abandoned_evaluation")
        await session.execute("RELEASE SAVEPOINT abandoned_evaluation")
    assert path.read_text() == ""


async def test_refused_workload_opening_commits_hint_without_order_intake(
    tmp_path: Path,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    from tests.infra.risk_limits import profile_workload as workload
    from tiewtrade.core.risk_limits import RiskUnavailableError

    await seed_setting(engine_engine, owner)
    reached = asyncio.Event()

    async def unavailable(*args: object, **kwargs: object) -> None:
        reached.set()
        raise RiskUnavailableError("source pending")

    monkeypatch.setattr(workload, "manual_policy_for", unavailable)
    fixture = workload.Fixture(tmp_path)
    state = f15.OwnerState(owner, wallet)
    intent = f15.baseline(state, uuid4(), 0)
    task = asyncio.create_task(fixture.request(state, intent))
    try:
        async with asyncio.timeout(5):
            await reached.wait()
            while True:
                async with user_session(api_engine, owner) as session:
                    hints = (
                        await session.execute("SELECT count(*) FROM risk_evaluation_requests")
                    ).scalar_one()
                    orders = (
                        await session.execute("SELECT count(*) FROM paper_order_requests")
                    ).scalar_one()
                if hints:
                    assert hints == 1 and orders == 0
                    break
                await asyncio.sleep(0.01)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await fixture.close()


@pytest.mark.parametrize("expected", ["ACCEPTED", "PARTIALLY_FILLED", "FILLED"])
async def test_joined_observation_waits_for_expected_state_even_after_command_success(
    tmp_path: Path,
    api_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
    expected: str,
) -> None:
    import asyncio
    from dataclasses import replace
    from unittest.mock import AsyncMock

    from tests.infra.risk_limits import profile_workload as workload
    from tiewtrade.core.orders import OrderStatus
    from tiewtrade.infra.paper_orders.dispatch import OrderCommand
    from tiewtrade.infra.paper_orders.requests import admit_new_request
    from tiewtrade.infra.paper_orders.views import RequestView, request_view

    state = f15.OwnerState(owner, wallet)
    value = f15.baseline(state, uuid4(), 0)
    async with user_session(api_engine, owner) as session:
        receipt = await admit_new_request(session, wallet_id=wallet.wallet_id, intent=value)
        view = await request_view(session, receipt.request_id)
    assert view is not None
    command = OrderCommand(uuid4(), "SUCCEEDED")
    wrong = replace(
        view,
        intake_state="TRANSFERRED",
        command_id=command.command_id,
        command_state="SUCCEEDED",
        order_state="CANCELED",
    )
    reached, release = asyncio.Event(), asyncio.Event()
    reads = 0

    async def observed(*args: object) -> RequestView:
        nonlocal reads
        reads += 1
        if reads == 1:
            return wrong
        reached.set()
        await release.wait()
        return replace(wrong, order_state=expected)

    fetched = AsyncMock(return_value=command)
    monkeypatch.setattr(workload, "request_view", observed)
    monkeypatch.setattr(workload, "get_order_command", fetched)
    fixture = workload.Fixture(tmp_path)
    task = asyncio.create_task(fixture.request(state, value, expected_status=OrderStatus(expected)))
    try:
        await asyncio.wait_for(reached.wait(), 3)
        assert not task.done() and fetched.await_count == 0
        release.set()
        assert await asyncio.wait_for(task, 3) is command
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await fixture.close()
