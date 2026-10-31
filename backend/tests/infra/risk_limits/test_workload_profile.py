"""Approved F18 runtime preserves safety and the original F15 defaults."""

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import Mock
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_workload as f15
from tests.infra.risk_limits.profile_workload import DURATION, RATE
from tiewtrade.core.money import Money
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot


def samples(duration: int, growth_percent: int = 0) -> list[dict[str, object]]:
    start = datetime(2026, 10, 27, tzinfo=UTC)
    return [
        {
            "at": start + timedelta(seconds=offset),
            "total_rss_bytes": 10000 if offset < duration * 3 / 4 else 10000 + growth_percent * 100,
        }
        for offset in range(0, duration + 1, 30)
    ]


def test_f18_durations_keep_original_command_rates() -> None:
    assert {phase: DURATION[phase] for phase in ("W1", "W2", "W3")} == {
        "W1": 600,
        "W2": 300,
        "W3": 1800,
    }
    assert [RATE[phase] for phase in ("W1", "W2", "W3")] == [10, 100, 10]


@pytest.mark.parametrize("growth, passed", [(0, True), (20, True), (21, False)])
def test_short_endurance_retains_growth_limit(growth: int, passed: bool) -> None:
    result = f15.endurance_rss(samples(1800, growth), duration_seconds=1800)
    assert result["passed"] is passed
    assert result["warmup_seconds"] == 112.5
    assert result["window_seconds"] == 450


def test_short_endurance_rejects_incomplete_measurement() -> None:
    assert f15.endurance_rss(samples(900), duration_seconds=1800)["passed"] is False
    assert f15.endurance_rss(samples(1800))["passed"] is False
    with pytest.raises(ValueError, match="positive"):
        f15.endurance_rss(samples(1800), duration_seconds=0)


def test_original_f15_four_hour_contract_is_preserved() -> None:
    result = f15.endurance_rss(samples(14400))
    assert result["passed"] is True
    assert result["warmup_seconds"] == 900
    assert result["window_seconds"] == 3600
    assert result["first_stable_hour_average_bytes"] == 10000
    assert result["last_hour_average_bytes"] == 10000


def test_short_schedule_preserves_all_faults_and_fits_cycles() -> None:
    path = Path(__file__).with_name("w3_fault_schedule.json")
    events, cycles, digest = f15.load_fault_schedule(path)
    original, _, _ = f15.load_fault_schedule(
        path.parent.parent / "execution_market" / "w3_fault_schedule.json"
    )
    assert len(events) == len(original) == 7
    assert [(event.kind, event.duration_seconds) for event in events] == [
        (event.kind, event.duration_seconds) for event in original
    ]
    previous_end = 0.0
    for event in events:
        assert previous_end < event.offset_seconds
        previous_end = event.offset_seconds + event.duration_seconds
        assert previous_end <= DURATION["W3"]
    assert cycles == 30
    assert (
        cycles * 100 * 5 / RATE["W3"] + sum(event.duration_seconds for event in events)
        <= DURATION["W3"]
    )
    assert len(digest) == 64


async def test_ready_scheduling_hint_never_bypasses_full_intake_policy(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.infra.execution_market.test_dispatch import intent
    from tests.infra.risk_limits import profile_workload as profile
    from tests.infra.risk_limits.test_execution import runtime
    from tiewtrade.infra.paper_orders.manual_policy import manual_policy_for

    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"
    ) as sources:
        # R6 can verify a benign price tail, but cannot repair financial pending.
        # Even a stale/false-positive READY hint cannot authorize the intake.
        await sources.price("100")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute("UPDATE risk_owner_state SET replay_pending=true")
        fixture = profile.Fixture(tmp_path)
        fixture.started = True
        original_policy = manual_policy_for
        original_execute = UserSession.execute
        policy_calls = hint_reads = 0
        checked_again = asyncio.Event()

        async def checked_policy(*args: Any, **kwargs: Any) -> Any:
            nonlocal policy_calls
            policy_calls += 1
            try:
                return await original_policy(*args, **kwargs)
            finally:
                if policy_calls >= 2:
                    checked_again.set()

        async def stale_ready_hint(
            session: UserSession, statement: str, parameters: Mapping[str, object] | None = None
        ) -> Any:
            nonlocal hint_reads
            if "SELECT EXISTS(SELECT 1 FROM risk_limit_evaluations" in statement:
                hint_reads += 1
                result = Mock()
                result.scalar_one.return_value = True
                return result
            return await original_execute(session, statement, parameters)

        with monkeypatch.context() as patch:
            patch.setattr(profile, "manual_policy_for", checked_policy)
            patch.setattr(UserSession, "execute", stale_ready_hint)
            task = asyncio.create_task(
                fixture.request(f15.OwnerState(owner, wallet), intent(owner, wallet.episode_id))
            )
            try:
                await asyncio.wait_for(checked_again.wait(), timeout=3)
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                await fixture.close()
        assert policy_calls >= 2 and hint_reads >= 1
        async with user_session(api_engine, owner) as session:
            assert (
                await session.execute("SELECT count(*) FROM paper_order_requests")
            ).scalar_one() == 0
            current = await get_wallet(session)
            assert current is not None and current.balance == Money.of(10000, "USDT")
            assert (
                await session.execute("SELECT count(*) FROM risk_evaluation_requests")
            ).scalar_one() > 0


def test_transaction_percentiles_exclude_setup_and_recovery_but_keep_slow_tail(
    tmp_path: Path,
) -> None:
    import json

    from tests.infra.risk_limits.profile_workload import measured_transaction_seconds

    path = tmp_path / "paper-0.json"
    setup = [{"started": 1, "finished": 1.001, "seconds": 0.001}] * 10000
    measured = [
        {"started": 10, "finished": 10.5, "seconds": 0.5},
        {"started": 19.5, "finished": 21.5, "seconds": 2},
    ]
    recovery = [{"started": 20, "finished": 20.001, "seconds": 0.001}]
    path.write_text(json.dumps({"transaction_samples": setup + measured + recovery}))
    values = measured_transaction_seconds([path], started=10, ended=20)
    assert values == [0.5, 2]
    assert f15.percentile(values, 0.95) > 0.250
    assert f15.percentile(values, 0.99) > 1
    path.write_text(json.dumps({"transaction_seconds": [0.001]}))
    with pytest.raises(KeyError, match="transaction_samples"):
        measured_transaction_seconds([path], started=10, ended=20)


async def test_global_oracle_counts_orders_in_bulk_cancel_checkpoint(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tests.infra.risk_limits.test_execution import drive, runtime
    from tests.infra.risk_limits.test_same_pair_dispatch import resting
    from tiewtrade.core.paper_matching import cancel_order
    from tiewtrade.infra.paper_orders.dispatch import submit_order
    from tiewtrade.infra.paper_orders.matching_storage import (
        load_matching_state,
        persist_checkpoint,
    )

    async with runtime(api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"):
        values = [resting(owner, wallet.episode_id) for _ in range(2)]
        for value in values:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
            await drive(engine_engine, owner, command.command_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            checkpoint = await load_matching_state(
                session, wallet_id=wallet.wallet_id, scope=values[0].scope, pair=values[0].pair
            )
            state = checkpoint.state
            for value in values:
                state = cancel_order(state, value.order_id, scope=value.scope)
            # A checkpoint may contain multiple terminal facts; a later checkpoint
            # repeating those facts must not count the cancellations twice.
            for _ in range(3):
                await persist_checkpoint(
                    session,
                    wallet_id=wallet.wallet_id,
                    state=state,
                    anchor_order_id=values[-1].order_id,
                    event_kind="CANCELED",
                    decision_kind="CANCEL",
                    occurred_at=datetime.now(UTC),
                )
        result = await f15.verify_global_invariants(
            engine_engine,
            [f15.OwnerState(owner, wallet)],
            baseline_orders=0,
            cycles_per_owner=0,
            extra_cancels=2,
        )
        assert result["cancels"] == result["expected_cancels"] == 2
