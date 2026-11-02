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


@pytest.mark.parametrize("phase", ["W1", "W2", "W3", "CHECK", None])
def test_explicit_f19_criteria_keep_strict_owner_quota_and_source_counts(phase: str | None) -> None:
    from tests.infra.risk_limits.profile_workload import acceptance_limits

    assert acceptance_limits("F19_SET5", phase) == (999, 0)
    assert acceptance_limits("F18_R34", phase) == (
        (995, 1) if phase in {"W1", "W2", "W3"} else (999, 0)
    )
    with pytest.raises(ValueError, match="unknown acceptance"):
        acceptance_limits("unknown", phase)


def test_same_receipts_can_pass_f18_but_fail_f19_owner_sla(tmp_path: Path) -> None:
    owners = [uuid4() for _ in range(10)]
    rows = [
        {
            "kind": "PRICE",
            "cursor": index,
            "ready_at": f"2026-10-26T00:00:{'00' if index <= 2 else '10'}+00:00",
            "measured": True,
        }
        for index in range(1, 1001)
    ]
    (tmp_path / "inputs.jsonl").write_text("\n".join(map(json.dumps, rows)))
    receipts = []
    for index, owner in enumerate(owners):
        first_commit = "03.100" if index == 0 else "01"
        receipts.extend(
            [
                {
                    "owner": str(owner),
                    "cursor": 2,
                    "boundary": 0,
                    "pending": False,
                    "committed_observed_at": f"2026-10-26T00:00:{first_commit}+00:00",
                },
                {
                    "owner": str(owner),
                    "cursor": 1000,
                    "boundary": 0,
                    "pending": False,
                    "committed_observed_at": "2026-10-26T00:00:11+00:00",
                },
            ]
        )
    receipts.sort(key=lambda value: str(value["committed_observed_at"]))
    (tmp_path / "monitor.risk.jsonl").write_text("\n".join(map(json.dumps, receipts)))
    f18 = sla_summary(tmp_path, owners, phase="W1")
    f19 = sla_summary(tmp_path, owners, phase="W1", acceptance_profile="F19_SET5")
    assert f18["passed"] is True and f19["passed"] is False
    assert f19["service_passed"] is True and f19["miss_count"] == 0
    assert f19["unacknowledged"] == f19["clock_errors"] == 0
    assert f19["minimum_owner_service_fraction"] == "0.999"


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


def risk_acknowledgement(
    owner: UUID, seconds: str, *, cursor: int = 2, pending: bool = False
) -> dict[str, object]:
    return {
        "owner": str(owner),
        "cursor": cursor,
        "boundary": 0,
        "pending": pending,
        "committed_observed_at": f"2026-10-26T00:00:{seconds}+00:00",
    }


def write_risk_stream(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(map(json.dumps, rows)))


@pytest.mark.parametrize("profile", ["F18_R34", "F19_SET5"])
@pytest.mark.parametrize("first,second", [("00.500", "00.400"), ("03.100", "01.000")])
def test_regressing_acknowledgements_reject_measurement_evidence(
    tmp_path: Path, profile: str, first: str, second: str
) -> None:
    owner = uuid4()
    inputs(tmp_path)
    rows = [risk_acknowledgement(owner, first), risk_acknowledgement(owner, second)]
    path = tmp_path / "monitor.risk.jsonl"
    write_risk_stream(path, rows)
    original = path.read_bytes()

    result = sla_summary(tmp_path, [owner], acceptance_profile=profile)

    assert result["samples"] == result["expected"] == 2
    assert result["clock_errors"] == 0
    assert result["stream_order_errors"] == 1
    assert result["first_stream_order_errors"] == [
        {
            "file": path.name,
            "previous_line": 1,
            "line": 2,
            "previous_observed_at": rows[0]["committed_observed_at"],
            "observed_at": rows[1]["committed_observed_at"],
        }
    ]
    assert result["passed"] is False
    assert path.read_bytes() == original


@pytest.mark.parametrize("filtered", ["pending", "foreign_owner"])
def test_stream_order_is_checked_before_filtering_and_after_input_coverage(
    tmp_path: Path, filtered: str
) -> None:
    owner = uuid4()
    inputs(tmp_path)
    ignored = risk_acknowledgement(
        uuid4() if filtered == "foreign_owner" else owner,
        "00.400",
        pending=filtered == "pending",
    )
    rows = [risk_acknowledgement(owner, "00.500"), ignored]
    write_risk_stream(tmp_path / "monitor.risk.jsonl", rows)

    result = sla_summary(tmp_path, [owner])

    assert result["samples"] == result["expected"] == 2
    assert result["stream_order_errors"] == 1
    assert result["clock_errors"] == 0
    assert result["passed"] is False


def test_equal_acknowledgement_timestamps_are_valid(tmp_path: Path) -> None:
    owner = uuid4()
    inputs(tmp_path)
    rows = [risk_acknowledgement(owner, "00.500") for _ in range(2)]
    write_risk_stream(tmp_path / "monitor.risk.jsonl", rows)

    result = sla_summary(tmp_path, [owner])

    assert result["samples"] == result["expected"] == 2
    assert result["stream_order_errors"] == 0
    assert result["first_stream_order_errors"] == []
    assert result["passed"] is True


def test_ordered_worker_streams_use_earliest_qualifying_acknowledgements(tmp_path: Path) -> None:
    owner = uuid4()
    inputs(tmp_path)
    streams = {
        "risk": [risk_acknowledgement(owner, "03.100")],
        "paper": [
            risk_acknowledgement(owner, "00.500", cursor=1),
            risk_acknowledgement(owner, "00.750"),
        ],
    }
    for name, rows in streams.items():
        write_risk_stream(tmp_path / f"{name}.risk.jsonl", rows)

    result = sla_summary(tmp_path, [owner], acceptance_profile="F19_SET5")

    assert result["samples"] == result["expected"] == 2
    assert result["stream_order_errors"] == result["service_miss_count"] == 0
    assert result["max_seconds"] == 0.55
    assert result["passed"] is True


def test_stream_order_diagnostics_are_bounded_without_losing_error_count(tmp_path: Path) -> None:
    owner = uuid4()
    inputs(tmp_path)
    rows = [risk_acknowledgement(owner, f"00.{900 - index:03}") for index in range(26)]
    write_risk_stream(tmp_path / "monitor.risk.jsonl", rows)

    result = sla_summary(tmp_path, [owner])

    assert result["samples"] == result["expected"] == 2
    assert result["stream_order_errors"] == 25
    errors = result["first_stream_order_errors"]
    assert isinstance(errors, list)
    assert len(errors) == 20
    assert errors[-1]["line"] == 21
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
