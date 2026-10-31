import asyncio
from uuid import UUID

import pytest

from tests.infra.execution_market.profile_workload import FaultGate
from tests.infra.risk_limits.profile_stop_schedule import (
    build_stop_schedule,
    conservation_summary,
)


def _owners(count: int) -> list[UUID]:
    return [UUID(int=index + 1) for index in range(count)]


@pytest.mark.parametrize(
    ("phase", "owner_count", "offsets"),
    [
        ("W1", 2, [50, 60, 90, 110, 120, 120, 150]),
        ("W2", 10, [30, 30, 30, 60, 90]),
        ("W3", 2, [210, 285, 600, 660, 660, 750]),
    ],
)
def test_stop_schedule_is_owner_bound_ordered_and_digest_stable(
    phase: str, owner_count: int, offsets: list[int]
) -> None:
    schedule = build_stop_schedule(phase, _owners(owner_count))

    assert [event.offset_seconds for event in schedule.events] == offsets
    assert schedule.digest() == build_stop_schedule(phase, _owners(owner_count)).digest()
    assert len(schedule.digest()) == 64
    assert schedule.document()["owners"] == [str(owner) for owner in _owners(owner_count)]


def test_w3_schedule_binds_platform_windows_to_existing_faults() -> None:
    schedule = build_stop_schedule("W3", _owners(2))

    assert [event.overlap for event in schedule.events if event.overlap] == [
        "WORKER_RESTART@225",
        "REDIS_OUTAGE@675",
    ]
    assert any(
        event.action == "HOLD_ONE_TARGET_FAILED" and event.expected == "ALERT_AFTER_60_SECONDS"
        for event in schedule.events
    )


@pytest.mark.parametrize(("phase", "owners"), [("CHECK", 2), ("W2", 9), ("W3", 1)])
def test_stop_schedule_rejects_missing_phase_or_dedicated_owners(phase: str, owners: int) -> None:
    with pytest.raises(ValueError):
        build_stop_schedule(phase, _owners(owners))


def test_conservation_accepts_only_marked_platform_blocks() -> None:
    summary = conservation_summary(
        expected=100,
        offered=100,
        admitted=96,
        completed=96,
        blocked_by_scheduled_platform_stop=4,
        other_rejected=0,
        blocked_outside_schedule=0,
    )

    assert summary["passed"] is True
    for field in (
        "offered",
        "admitted",
        "completed",
        "blocked_by_scheduled_platform_stop",
        "other_rejected",
        "blocked_outside_schedule",
    ):
        broken = dict(summary)
        broken[field] = int(broken[field]) + 1
        assert (
            conservation_summary(
                expected=int(broken["expected"]),
                offered=int(broken["offered"]),
                admitted=int(broken["admitted"]),
                completed=int(broken["completed"]),
                blocked_by_scheduled_platform_stop=int(
                    broken["blocked_by_scheduled_platform_stop"]
                ),
                other_rejected=int(broken["other_rejected"]),
                blocked_outside_schedule=int(broken["blocked_outside_schedule"]),
            )["passed"]
            is False
        )


@pytest.mark.asyncio
async def test_overlapping_stop_and_fault_holds_do_not_reopen_workload_early() -> None:
    gate = FaultGate()

    await gate.pause()
    await gate.pause()
    gate.resume(1)
    assert not gate.open.is_set()
    gate.resume(1)
    assert gate.open.is_set()
    assert gate.pause_seconds >= 0

    with pytest.raises(RuntimeError, match="without a matching pause"):
        gate.resume(0)
    await asyncio.sleep(0)
