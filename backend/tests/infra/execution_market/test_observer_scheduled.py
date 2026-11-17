"""OBS-04 schedule, scope, supervision and real PostgreSQL capture."""

import asyncio
from pathlib import Path
from time import monotonic
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market import profile_observer_scheduled as scheduled
from tests.infra.execution_market import profile_publisher_lease_load as load
from tests.infra.execution_market.profile_owned_pools import parent_configuration
from tests.infra.execution_market.test_observer_short_load import approved


@pytest.mark.parametrize(
    "change",
    [
        {"phase": "W3"},
        {"phase": "W1"},
        {"publisher_fence_timing": False},
        {"publisher_lease_observer": False},
        {"publisher_fence_observer": False},
        {"publisher_fence_fail_fast": False},
        {"publisher_clock_recovery": True},
        {"worker_only": True},
        {"diagnostics": True},
        {"controlled_delay": True},
        {"failure_timeline": True},
        {"acceptance_profile": "other"},
    ],
)
def test_scope(change: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        load.validate_options(approved(observer_scheduled_samples=True, **change))


def test_inventory_and_options() -> None:
    load.validate_options(approved(observer_scheduled_samples=True))
    base = parent_configuration(publisher_lease_observer=True, publisher_fence_observer=True)
    assert parent_configuration(
        publisher_lease_observer=True,
        publisher_fence_observer=True,
        observer_scheduled_samples=True,
    ) == [*base, ("ADMIN_OBSERVER", 5, 10), ("MARKET_DATA", 1, 0)]
    with pytest.raises(ValueError):
        parent_configuration(observer_scheduled_samples=True)


@pytest.fixture
def subject(monkeypatch: pytest.MonkeyPatch) -> scheduled.ScheduledObservation:
    monkeypatch.setattr(internal, "guard_database", lambda _: None)
    monkeypatch.setattr(scheduled, "FenceObservation", lambda _: Mock(close=AsyncMock()))
    monkeypatch.setattr(scheduled, "create_engine_for", lambda *a, **kw: Mock(dispose=AsyncMock()))
    return scheduled.ScheduledObservation()


async def test_guard_before_engines(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(_: Any) -> None:
        raise ValueError("isolation")

    factory = Mock()
    monkeypatch.setattr(internal, "guard_database", reject)
    monkeypatch.setattr(scheduled, "FenceObservation", factory)
    monkeypatch.setattr(scheduled, "create_engine_for", factory)
    with pytest.raises(ValueError, match="isolation"):
        scheduled.ScheduledObservation()
    factory.assert_not_called()


@pytest.mark.parametrize("delay", [0, 30])
async def test_slots(
    subject: scheduled.ScheduledObservation, monkeypatch: pytest.MonkeyPatch, delay: int
) -> None:
    clock = [100.0]

    async def sleep(seconds: float) -> None:
        clock[0] += seconds + delay

    async def capture(record: dict[str, Any]) -> None:
        record["outcome"] = "RETURNED"

    monkeypatch.setattr(scheduled, "monotonic", lambda: clock[0])
    monkeypatch.setattr(asyncio, "sleep", sleep)
    operation = AsyncMock(side_effect=capture)
    monkeypatch.setattr(subject, "capture", operation)
    assert not subject.report()["task_joined"] and not subject.records
    subject.start(100)
    assert subject.task is not None
    if delay:
        with pytest.raises(ValueError):
            await subject.task
        operation.assert_not_awaited()
        assert len(subject.records) == 1
        assert subject.report()["status"] == "INCOMPLETE"
    else:
        await subject.task
        assert operation.await_count == 10
        assert [r["started"] for r in subject.records] == [100 + x for x in scheduled.OFFSETS]
        assert subject.report()["status"] == "RECORDED"
    with pytest.raises(ValueError):
        subject.start(100)
    await subject.close()


@pytest.mark.parametrize("error_type", [RuntimeError, TimeoutError, asyncio.CancelledError])
async def test_error_no_retry(
    subject: scheduled.ScheduledObservation,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[BaseException],
) -> None:
    monkeypatch.setattr(subject, "offsets", (0, 30))
    monkeypatch.setattr(scheduled, "monotonic", lambda: 0)
    error = error_type()
    operation = AsyncMock(side_effect=error)
    monkeypatch.setattr(subject, "capture", operation)
    subject.start(0)
    assert subject.task is not None
    with pytest.raises(error_type) as caught:
        await subject.task
    assert caught.value is error
    operation.assert_awaited_once()
    assert subject.records[0]["outcome"] == error_type.__name__
    assert subject.report()["status"] == "INCOMPLETE"
    await subject.close()


async def test_early_close(subject: scheduled.ScheduledObservation) -> None:
    subject.start(monotonic())
    await subject.close()
    assert subject.report()["task_joined"]
    assert not subject.report()["task_completed"]
    assert subject.report()["status"] == "INCOMPLETE"
    assert not subject.records


async def test_supervision(tmp_path: Path) -> None:
    owner = load.LoadLeaseObserver(
        tmp_path,
        {"write_failed": False},
        fence_observer=True,
        fence_fail_fast=True,
        fence_timing=True,
        scheduled_samples=True,
    )
    with pytest.raises(ValueError, match="missing"):
        owner.measurement_started(0)
    task = asyncio.create_task(asyncio.sleep(10))
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    owner.scheduled_finished(task)
    assert owner.failure_reason == "SCHEDULED_SAMPLER_EVIDENCE_LOST"


@pytest.mark.usefixtures("internal_database")
async def test_real_capture() -> None:
    subject = scheduled.ScheduledObservation()
    record: dict[str, Any] = {}
    try:
        await subject.capture(record)
        row = record["observation"]
        assert record["outcome"] == "RETURNED"
        assert row["stage"] == "scheduled_fixture_idle"
        assert row["publication_tick"] is None
        assert row["publisher_pid"] in [r["pid"] for r in row["activity"]]
        assert len(record["spans"]) == 7
        assert subject.fixture.pool.checkedout() == 0  # type: ignore[attr-defined]
        assert subject.observer.engine.pool.checkedout() == 0  # type: ignore[attr-defined]
    finally:
        await subject.close()


@pytest.mark.usefixtures("internal_database")
@pytest.mark.parametrize("error_type", [RuntimeError, asyncio.CancelledError])
async def test_real_capture_failure_returns_fixture(
    monkeypatch: pytest.MonkeyPatch, error_type: type[BaseException]
) -> None:
    from sqlalchemy import text

    subject = scheduled.ScheduledObservation()
    pids: list[int] = []
    primary = error_type("private")

    async def fail(statement: dict[str, Any]) -> dict[str, Any]:
        pids.append(statement["backend_pid"])
        raise primary

    monkeypatch.setattr(subject.observer, "sample", fail)
    record: dict[str, Any] = {}
    try:
        with pytest.raises(error_type) as caught:
            await subject.capture(record)
        assert caught.value is primary
        assert record["outcome"] == error_type.__name__
        assert subject.fixture.pool.checkedout() == 0  # type: ignore[attr-defined]
        async with subject.observer.engine.connect() as connection:
            assert (
                await connection.execute(
                    text(
                        "SELECT count(*) FROM pg_stat_activity WHERE pid=:pid "
                        "AND xact_start IS NOT NULL"
                    ),
                    {"pid": pids[0]},
                )
            ).scalar_one() == 0
            assert (
                await connection.execute(
                    text("SELECT count(*) FROM pg_locks WHERE pid=:pid AND locktype='advisory'"),
                    {"pid": pids[0]},
                )
            ).scalar_one() == 0
    finally:
        await subject.close()


@pytest.mark.parametrize("io_failure", [False, True])
async def test_incomplete_scheduled_receipt_cannot_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, io_failure: bool
) -> None:
    import json
    from types import SimpleNamespace

    from tests.infra.execution_market import profile_workload as workload

    parent = load.LoadLeaseObserver(
        tmp_path,
        {"write_failed": False},
        fence_observer=True,
        fence_fail_fast=True,
        fence_timing=True,
        scheduled_samples=True,
    )
    parent.outcomes["RETURNED"] = 1
    parent.fence = SimpleNamespace(
        errors={},
        total=0,
        report=lambda: {
            "task_joined": True,
            "timing": {
                "status": "NO_TRIGGER",
                "lag_task_joined": True,
                "lag_task_completed": True,
                "counts": {},
            },
        },
    )
    parent.scheduled = SimpleNamespace(report=lambda: {"status": "INCOMPLETE"})
    (tmp_path / "publisher-readiness.json").write_text(
        json.dumps(
            {
                "scope": "parent publish_market readiness guards only",
                "checks": [],
                "total_checks": 0,
                "discarded_earlier_checks": 0,
                "flush_reason": "test",
            }
        )
    )
    if io_failure:
        monkeypatch.setattr(workload, "save", Mock(side_effect=OSError()))
    with pytest.raises(OSError if io_failure else ValueError):
        parent.flush()
    if not io_failure:
        report = json.loads((tmp_path / "publisher-lease.json").read_text())
        assert report["scheduled_observation"]["status"] == "INCOMPLETE"


async def test_capture_crossing_next_slot_stops(
    subject: scheduled.ScheduledObservation, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = [0.0]

    async def sleep(seconds: float) -> None:
        clock[0] += seconds

    async def capture(record: dict[str, Any]) -> None:
        record["outcome"] = "RETURNED"
        clock[0] += 30

    monkeypatch.setattr(scheduled, "monotonic", lambda: clock[0])
    monkeypatch.setattr(asyncio, "sleep", sleep)
    monkeypatch.setattr(subject, "capture", capture)
    subject.start(0)
    assert subject.task is not None
    with pytest.raises(ValueError, match="crossed"):
        await subject.task
    assert len(subject.records) == 1
    assert subject.report()["status"] == "INCOMPLETE"
    await subject.close()


@pytest.mark.parametrize("offset", [0, 285])
async def test_hung_capture_cancelled_at_slot_deadline(
    subject: scheduled.ScheduledObservation,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    offset: int,
) -> None:
    monkeypatch.setattr(subject, "offsets", (offset,))
    entered = asyncio.Event()
    released = asyncio.Event()

    async def capture(record: dict[str, Any]) -> None:
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            released.set()

    operation = AsyncMock(side_effect=capture)
    monkeypatch.setattr(subject, "capture", operation)
    owner = load.LoadLeaseObserver(
        tmp_path,
        {"write_failed": False},
        fence_observer=True,
        fence_fail_fast=True,
        fence_timing=True,
        scheduled_samples=True,
    )
    owner.scheduled = subject
    # Reach the actual slot/measurement boundary without waiting 30/300 seconds.
    boundary = min(offset + 30, 300)
    owner.measurement_started(monotonic() - boundary + 0.05)
    assert subject.task is not None
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(asyncio.shield(subject.task), 1)
    assert subject.task.done() and entered.is_set() and released.is_set()
    operation.assert_awaited_once()
    assert subject.records[0]["outcome"] == "TimeoutError"
    assert subject.report()["status"] == "INCOMPLETE"
    assert owner.failure_reason == "SCHEDULED_SAMPLER_EVIDENCE_LOST"
    await subject.close()


@pytest.mark.parametrize(
    ("first_type", "second_fails"),
    [
        (RuntimeError, False),
        (RuntimeError, True),
        (asyncio.CancelledError, False),
        (asyncio.CancelledError, True),
        (None, True),
    ],
)
async def test_cleanup_preserves_first_error(
    subject: scheduled.ScheduledObservation,
    first_type: type[BaseException] | None,
    second_fails: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = first_type("PRIVATE FIRST") if first_type is not None else None
    second = ValueError("PRIVATE SECOND") if second_fails else None
    expected = first if first is not None else second
    assert expected is not None
    observer_close = AsyncMock(side_effect=first)
    fixture_dispose = AsyncMock(side_effect=second)
    monkeypatch.setattr(subject.observer, "close", observer_close)
    monkeypatch.setattr(subject.fixture, "dispose", fixture_dispose)
    with pytest.raises(type(expected)) as caught:
        await subject.close()
    assert caught.value is expected
    observer_close.assert_awaited_once()
    fixture_dispose.assert_awaited_once()
    notes = getattr(expected, "__notes__", [])
    assert notes == (
        ["scheduled cleanup failed: ValueError"] if first is not None and second_fails else []
    )
