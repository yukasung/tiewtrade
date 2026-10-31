"""Approved F18 runtime preserves safety and the original F15 defaults."""

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
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


async def test_loss_reset_retries_only_source_unavailable_with_new_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.infra.risk_limits import profile_workload as profile

    request_ids = [uuid4(), uuid4(), uuid4()]
    calls = 0
    delays: list[float] = []

    async def submit() -> UUID:
        nonlocal calls
        request_id = request_ids[calls]
        calls += 1
        if calls < 3:
            raise profile.RiskMutationRejectedError(request_id, "RISK_SOURCE_UNAVAILABLE")
        return request_id

    async def sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(asyncio, "sleep", sleep)
    evidence: list[dict[str, str]] = []
    assert await profile.retry_source_unavailable_reset(submit, evidence) == request_ids[-1]
    assert calls == 3 and delays == [0.25, 0.25]
    assert [row["request_id"] for row in evidence] == [str(value) for value in request_ids]
    assert [row["state"] for row in evidence] == ["REJECTED", "REJECTED", "APPLIED"]


async def test_loss_reset_does_not_retry_another_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.infra.risk_limits import profile_workload as profile

    delays: list[float] = []

    async def submit() -> UUID:
        raise profile.RiskMutationRejectedError(uuid4(), "RISK_REVISION_CONFLICT")

    async def sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(asyncio, "sleep", sleep)
    evidence: list[dict[str, str]] = []
    with pytest.raises(profile.RiskMutationRejectedError, match="RISK_REVISION_CONFLICT"):
        await profile.retry_source_unavailable_reset(submit, evidence)
    assert len(evidence) == 1 and delays == []


async def test_loss_reset_stops_after_three_source_unavailable_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.infra.risk_limits import profile_workload as profile

    calls = 0
    delays: list[float] = []

    async def submit() -> UUID:
        nonlocal calls
        calls += 1
        raise profile.RiskMutationRejectedError(uuid4(), "RISK_SOURCE_UNAVAILABLE")

    async def sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(asyncio, "sleep", sleep)
    evidence: list[dict[str, str]] = []
    with pytest.raises(profile.RiskMutationRejectedError, match="RISK_SOURCE_UNAVAILABLE"):
        await profile.retry_source_unavailable_reset(submit, evidence)
    assert calls == 3 and len(evidence) == 3 and delays == [0.25, 0.25]


def test_dedicated_loss_setup_precedes_core_risk_and_baseline() -> None:
    from tests.infra.risk_limits import profile_workload as profile

    sequence = profile.SetupSequence()
    for stage in profile.SETUP_STAGES:
        sequence.advance(stage)
    assert sequence.completed == [
        "DEDICATED_LOSS",
        "CORE_RISK_SETTINGS",
        "STOP_OWNER_RISK_SETTINGS",
        "CORE_BASELINE",
    ]

    invalid = profile.SetupSequence()
    with pytest.raises(
        RuntimeError,
        match="F19_SETUP_ORDER_INVALID:DEDICATED_LOSS:CORE_BASELINE",
    ):
        invalid.advance("CORE_BASELINE")

    missing_stop_owner_state = profile.SetupSequence()
    missing_stop_owner_state.advance("DEDICATED_LOSS")
    missing_stop_owner_state.advance("CORE_RISK_SETTINGS")
    with pytest.raises(
        RuntimeError,
        match="F19_SETUP_ORDER_INVALID:STOP_OWNER_RISK_SETTINGS:CORE_BASELINE",
    ):
        missing_stop_owner_state.advance("CORE_BASELINE")


def test_order_request_rejection_preserves_durable_identities() -> None:
    from tests.infra.risk_limits import profile_workload as profile

    request_id, command_id = uuid4(), uuid4()
    error = profile.OrderRequestRejectedError(
        request_id=request_id,
        command_id=command_id,
        intake_failure_code=None,
        command_failure_code="RISK_SOURCE_UNAVAILABLE",
    )
    assert str(error) == "F18_POSITIVE_REQUEST_REJECTED:None:RISK_SOURCE_UNAVAILABLE"
    assert error.request_id == request_id
    assert error.command_id == command_id
    assert error.command_failure_code == "RISK_SOURCE_UNAVAILABLE"


async def test_setup_order_waits_for_ready_then_submits_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.infra.risk_limits import profile_workload as profile

    readiness = iter((False, False, True))
    stages: list[str] = []
    submits = 0

    async def ready() -> bool:
        return next(readiness)

    async def submit() -> str:
        nonlocal submits
        submits += 1
        return "submitted"

    async def observe(stage: str) -> None:
        stages.append(stage)

    async def sleep(_: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", sleep)
    assert await profile.submit_setup_order_when_ready(ready, submit, observe) == "submitted"
    assert submits == 1
    assert stages == ["WAIT_START", "READY"]


async def test_setup_order_timeout_does_not_submit() -> None:
    from tests.infra.risk_limits import profile_workload as profile

    stages: list[str] = []
    submits = 0

    async def ready() -> bool:
        await asyncio.sleep(1)
        return False

    async def submit() -> None:
        nonlocal submits
        submits += 1

    async def observe(stage: str) -> None:
        stages.append(stage)

    with pytest.raises(RuntimeError, match="F19_SETUP_RISK_NOT_READY"):
        await profile.submit_setup_order_when_ready(ready, submit, observe, timeout_seconds=0.001)
    assert submits == 0
    assert stages == ["WAIT_START", "TIMEOUT"]


async def test_setup_order_terminal_rejection_is_not_retried() -> None:
    from tests.infra.risk_limits import profile_workload as profile

    submits = 0

    async def ready() -> bool:
        return True

    async def submit() -> None:
        nonlocal submits
        submits += 1
        raise RuntimeError("F15_WORKLOAD_ORDER_REJECTED:RISK_SOURCE_UNAVAILABLE")

    async def observe(_: str) -> None:
        return None

    with pytest.raises(RuntimeError, match="F15_WORKLOAD_ORDER_REJECTED"):
        await profile.submit_setup_order_when_ready(ready, submit, observe)
    assert submits == 1


async def test_scheduled_partial_source_window_restores_after_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.infra.risk_limits import profile_workload as profile

    fixture = cast(Any, object.__new__(profile.Fixture))
    fixture.publisher_stats = {"last_ask_quantity": "1000000"}
    transitions: list[tuple[str, str]] = []

    async def set_quantity(quantity: str, stage: str) -> None:
        transitions.append((stage, quantity))

    monkeypatch.setattr(fixture, "set_scheduled_partial_quantity", set_quantity)
    with pytest.raises(RuntimeError, match="scenario failed"):
        async with fixture.scheduled_partial_source_window() as (install, _):
            await install()
            raise RuntimeError("scenario failed")
    assert transitions == [("INSTALL", "0.5"), ("RESTORE", "1000000")]


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


async def test_r6_retry_hint_requires_matching_nonpending_bounded_tail(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tests.infra.risk_limits import profile_workload as profile
    from tests.infra.risk_limits.test_execution import runtime
    from tests.infra.risk_limits.test_requests import submission
    from tiewtrade.infra.risk_limits.monitor import replay_monitor
    from tiewtrade.infra.risk_limits.storage import read_setting

    async with runtime(api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            setting = await read_setting(session, submission(owner, wallet).scope)
            await replay_monitor(session, setting)
        async with migrator_engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('tiewtrade.current_user_id',:owner,true)"),
                {"owner": str(owner)},
            )
            row = (
                await connection.execute(
                    text("""SELECT o.cursor,s.revision,e.loss FROM risk_owner_state o
                    JOIN risk_limit_settings s USING(user_id,mode)
                    JOIN risk_limit_evaluations e USING(user_id,mode)
                    WHERE o.user_id=:owner AND o.mode='PAPER'"""),
                    {"owner": owner},
                )
            ).one()
        cursor, revision, loss = int(row.cursor), int(row.revision), row.loss

        async def set_case(
            *,
            lag: int = 0,
            evaluation_cursor: int | None = None,
            evaluation_pending: bool = False,
            owner_pending: bool = False,
            setting_revision: int | None = None,
            latched: bool = False,
            reason: str = "READY",
        ) -> None:
            async with migrator_engine.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('tiewtrade.current_user_id',:owner,true)"),
                    {"owner": str(owner)},
                )
                await connection.execute(
                    text("UPDATE risk_price_publication SET watermark=:watermark"),
                    {"watermark": cursor + lag},
                )
                await connection.execute(
                    text("""UPDATE risk_owner_state SET cursor=:cursor,
                    replay_pending=:pending WHERE user_id=:owner AND mode='PAPER'"""),
                    {"cursor": cursor, "pending": owner_pending, "owner": owner},
                )
                await connection.execute(
                    text("""UPDATE risk_limit_settings SET latched=:latched
                    WHERE user_id=:owner AND mode='PAPER'"""),
                    {"latched": latched, "owner": owner},
                )
                await connection.execute(
                    text("""UPDATE risk_limit_evaluations SET price_watermark=:cursor,
                    replay_pending=:pending,setting_revision=:revision,reason=:reason,
                    loss=CASE WHEN :reason='READY'
                      THEN CAST(:loss AS tiewtrade_money_amount) ELSE NULL END
                    WHERE user_id=:owner AND mode='PAPER'"""),
                    {
                        "cursor": cursor if evaluation_cursor is None else evaluation_cursor,
                        "pending": evaluation_pending,
                        "revision": revision if setting_revision is None else setting_revision,
                        "reason": reason,
                        "loss": loss,
                        "owner": owner,
                    },
                )

        async def ready(
            *, wallet_id: UUID = wallet.wallet_id, episode_id: UUID = wallet.episode_id
        ) -> bool:
            async with user_session(api_engine, owner) as session:
                return await profile.risk_retry_ready(
                    session, wallet_id=wallet_id, episode_id=episode_id
                )

        for lag in (0, 1, 100):
            await set_case(lag=lag)
            assert await ready()
        await set_case(lag=-1)
        assert not await ready()
        await set_case(lag=101)
        assert not await ready()
        await set_case(evaluation_cursor=cursor - 1)
        assert not await ready()
        await set_case(evaluation_pending=True)
        assert not await ready()
        await set_case(owner_pending=True)
        assert not await ready()
        await set_case(setting_revision=revision + 1)
        assert not await ready()
        await set_case(latched=True)
        assert not await ready()
        await set_case(reason="RISK_SOURCE_UNAVAILABLE")
        assert not await ready()
        await set_case()
        assert not await ready(wallet_id=uuid4())
        assert not await ready(episode_id=uuid4())


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
