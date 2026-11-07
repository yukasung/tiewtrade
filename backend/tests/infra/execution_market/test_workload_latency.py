"""Latency acceptance uses the declared load cohort without dropping slow tails."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from tests.infra.execution_market import profile_workload as f15


def test_shared_selector_keeps_boundaries_restarts_and_full_slow_durations(tmp_path: Path) -> None:
    first = tmp_path / "worker-0.json"
    restarted = tmp_path / "restart-0-worker-0.json"
    monitor = tmp_path / "risk-0.json"
    f15.save(
        first,
        {
            "transaction_samples": [
                {"started": 1, "seconds": 0.001},  # setup
                {"started": 10, "seconds": 0.1},  # inclusive load start
                {"started": 11, "seconds": 5},  # spans a fault: retain all five seconds
                {"started": 12, "seconds": 7},  # fault start
                {"started": 13.9, "seconds": 8},  # fault, even if it ends after restoration
            ]
        },
    )
    f15.save(
        restarted,
        {
            "transaction_samples": [
                {"started": 14, "seconds": 0.2},  # restoration is inclusive
                {"started": 19.9, "seconds": 2},  # slow tail finishes after load end
                {"started": 20, "seconds": 9},  # drain starts at the exclusive end
            ]
        },
    )
    monitor.write_text("not a Paper transaction metric")
    assert f15.measured_transaction_seconds(
        [first, restarted, monitor], started=10, ended=20, excluded=[(12, 14)]
    ) == [0.1, 5, 0.2, 2]


@pytest.mark.parametrize("phase", ["SMOKE", "W1", "W2", "W3_SMOKE", "W3"])
@pytest.mark.parametrize("slow", [False, True])
async def test_parent_uses_measured_population_for_result_and_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, phase: str, slow: bool
) -> None:
    args = mock_parent(monkeypatch, tmp_path, phase=phase, case="slow" if slow else "normal")
    code = await f15._run(args)
    result = json.loads((args.output / "result.json").read_text())
    metric = result["engine_transaction_seconds"]
    assert metric["applicable"] is True
    assert metric["samples"] == 4
    assert metric["p95"] == metric["p99"] == metric["max"] == (2 if slow else 0.2)
    assert metric["window"]["started"] == 10
    assert metric["window"]["ended"] == (10 + f15.W3_DURATION_SECONDS if phase == "W3" else 20)
    assert metric["window"]["excluded_fault_intervals"] == (
        [[12, 14]] if phase.startswith("W3") else []
    )
    assert metric["window"] == json.loads((args.output / "processing-window.json").read_text())
    # The tiny fake W3 fixture cannot certify the real four-hour throughput/resource criteria.
    failed = slow or phase == "W3"
    assert code == int(failed)
    assert result["status"] == ("FAILED" if failed else "PASSED")


@pytest.mark.parametrize(
    "case,error,message",
    [
        ("legacy", KeyError, "transaction_samples"),
        ("empty", AssertionError, "latency sample is empty"),
        ("cycle_failure", RuntimeError, "controlled cycle failure"),
    ],
)
async def test_missing_or_incomplete_measurement_cannot_produce_acceptance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    case: str,
    error: type[Exception],
    message: str,
) -> None:
    args = mock_parent(monkeypatch, tmp_path, phase="SMOKE", case=case)
    with pytest.raises(error, match=message):
        await f15._run(args)
    assert not (args.output / "result.json").exists()
    window = json.loads((args.output / "processing-window.json").read_text())
    assert window["status"] == "INCOMPLETE"
    assert window["started"] == 10
    assert window["ended"] == (None if case == "cycle_failure" else 20)
    assert window["failure_observed"] >= 20
    failure = json.loads((args.output / "failure.json").read_text())
    assert failure["error_type"] == error.__name__


@pytest.mark.parametrize("phase", ["BASELINE", "W2_OVERFLOW"])
async def test_non_load_phases_do_not_certify_latency_from_setup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, phase: str
) -> None:
    args = mock_parent(monkeypatch, tmp_path, phase=phase, case="legacy")
    assert await f15._run(args) == 0
    result = json.loads((args.output / "result.json").read_text())
    assert not (args.output / "processing-window.json").exists()
    if phase == "BASELINE":
        assert result == {"status": "PREPARED", "acceptance_result": False}
    else:
        assert result["engine_transaction_seconds"] == {
            "applicable": False,
            "p95": None,
            "p99": None,
            "max": None,
            "samples": 0,
            "window": None,
        }
        assert result["fault"]["no_economic_change"] is True


def mock_parent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, phase: str, case: str
) -> argparse.Namespace:
    """Run the real parent/reporting path with fake I/O and a deterministic clock."""
    clock = SimpleNamespace(now=0.0)
    database = SimpleNamespace(dispose=AsyncMock())
    worker = SimpleNamespace(returncode=0)
    paths = [tmp_path / "worker-0.json", tmp_path / "restart-0-worker-0.json"]
    load_end = 10 + f15.W3_DURATION_SECONDS if phase == "W3" else 20
    samples = [
        *([{"started": 1, "seconds": 0.001}] * 1000),
        {"started": 10, "seconds": 0.1},
        {"started": 11.9, "seconds": 0.2},
        {"started": 14, "seconds": 0.2},
        {"started": load_end - 0.1, "seconds": 2 if case == "slow" else 0.1},
        {"started": load_end, "seconds": 5},
    ]
    if phase.startswith("W3"):
        samples.append({"started": 12, "seconds": 7})
    for path, records in zip(paths, [samples[:1002], samples[1002:]], strict=True):
        f15.save(
            path,
            {"transaction_seconds": [0.001]}
            if case == "legacy"
            else {"transaction_samples": [] if case == "empty" else records},
        )
    stats: dict[str, Any] = {}

    async def publisher(
        source: Any, stop: asyncio.Event, values: dict[str, Any], **kwargs: Any
    ) -> None:
        nonlocal stats
        stats = values
        stats["published"] = 2
        await stop.wait()

    async def baseline(*args: Any, **kwargs: Any) -> None:
        clock.now = 10

    async def cycles(
        engine: Any,
        owners: Any,
        run_id: Any,
        cycles_per_owner: int,
        rate: int,
        counters: f15.Counters,
        *args: Any,
        **kwargs: Any,
    ) -> float:
        clock.now = 20
        if case == "cycle_failure":
            raise RuntimeError("controlled cycle failure")
        counters.offered = counters.admitted = counters.completed = 5
        counters.cycles = counters.cancels = counters.replays = 1
        counters.fills = 2
        stats["published"] = 202
        return 10

    async def faults(*args: Any, **kwargs: Any) -> None:
        kwargs["observations"].append({"started": 12, "restored": 14, "status": "RECOVERED"})

    async def recovery(*args: Any, **kwargs: Any) -> None:
        clock.now += 10  # Final drain must not extend the recorded load window.

    original_sleep = asyncio.sleep

    async def sleep(seconds: float) -> None:
        if seconds > 1:  # W3's four-hour hold is simulated, never actually run.
            clock.now += seconds
        await original_sleep(0)

    monkeypatch.setattr(f15, "monotonic", lambda: clock.now)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    monkeypatch.setattr(f15, "create_engine_for", lambda role: database)
    monkeypatch.setattr(f15, "database_manifest", AsyncMock(return_value={}))
    monkeypatch.setattr(f15, "seed_owners", AsyncMock(return_value=[]))
    monkeypatch.setattr(f15, "seed_baseline", baseline)
    monkeypatch.setattr(f15, "market_publisher", publisher)
    monkeypatch.setattr(
        f15, "start_worker_processes", AsyncMock(return_value=([worker], tmp_path / "stop", paths))
    )
    monkeypatch.setattr(f15, "stop_worker_processes", AsyncMock())
    monkeypatch.setattr(f15, "resource_sampler", AsyncMock())
    monkeypatch.setattr(f15, "run_scheduled_cycles", cycles)
    monkeypatch.setattr(f15, "run_fault_schedule", faults)
    monkeypatch.setattr(f15, "load_fault_schedule", lambda path: ([], 1, "digest"))
    monkeypatch.setattr(f15, "wait_for_input_recovery", recovery)
    monkeypatch.setattr(f15, "verify", AsyncMock(return_value=[{"passed": True}]))
    monkeypatch.setattr(
        f15, "verify_global_invariants", AsyncMock(return_value={"passed": True, "input_lag": 0})
    )
    monkeypatch.setattr(f15, "economic_snapshot", AsyncMock(return_value={"unchanged": True}))
    monkeypatch.setattr(f15, "publish_overflow", AsyncMock(return_value=4097))
    monkeypatch.setattr(
        f15,
        "summarize_resources",
        lambda samples: {
            "peak_process_rss_bytes": 0,
            "lock_waits_end": 0,
            "connections_start": 0,
            "connections_end": 0,
        },
    )
    return argparse.Namespace(
        output=tmp_path / "run",
        phase=phase,
        owners=1,
        baseline_orders=20,
        cycles_per_owner=0 if phase in {"BASELINE", "W2_OVERFLOW"} else 1,
        rate=1,
        workers=1,
        baseline_manifest=None,
        fault_schedule=tmp_path / "schedule.json",
        redis_container="unused",
    )


@pytest.mark.parametrize("pilot", [False, True])
@pytest.mark.parametrize(
    "p95,p99,pilot_ok,target_ok",
    [
        (0.25, 1.0, True, True),
        (0.5, 2.0, True, False),
        (0.500001, 1.0, False, False),
        (0.25, 2.000001, False, False),
        (None, 1.0, False, False),
        (0.25, None, False, False),
        (float("nan"), 1.0, False, False),
        (0.25, float("inf"), False, False),
        (-0.1, 1.0, False, False),
    ],
)
def test_pilot_processing_limits_keep_default_targets_and_fail_closed(
    pilot: bool, p95: float | None, p99: float | None, pilot_ok: bool, target_ok: bool
) -> None:
    from tests.infra.execution_market import profile_internal as internal

    report = internal.processing_acceptance(
        argparse.Namespace(phase="W1", acceptance_profile=internal.NAME if pilot else None),
        p95,
        p99,
    )
    assert report["passed"] == (pilot_ok if pilot else target_ok)
    assert report["target_passed"] == target_ok
    assert report["performance_warning"] == (pilot and pilot_ok and not target_ok)
    assert report["p95_limit_seconds"] == (0.5 if pilot else 0.25)
    assert report["p99_limit_seconds"] == (2.0 if pilot else 1.0)


@pytest.mark.parametrize(
    "p95,p99,passed,warning",
    [
        (0.25, 1.0, True, False),
        (0.5, 2.0, True, True),
        (0.500001, 1.0, False, False),
        (0.25, 2.000001, False, False),
    ],
)
def test_v2_retains_approved_pilot_timing_and_separate_original_target(
    p95: float, p99: float, passed: bool, warning: bool
) -> None:
    from tests.infra.execution_market import profile_internal as internal

    report = internal.processing_acceptance(
        argparse.Namespace(phase="W2", acceptance_profile=internal.NAME_V2), p95, p99
    )
    assert report["revision"] == "NC12_SECTION18_PILOT"
    assert report["passed"] == passed and report["performance_warning"] == warning


async def test_v3_parent_uses_short_hold_rss_and_snapshot_count(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    from tests.infra.execution_market import profile_http, profile_positions
    from tests.infra.execution_market import profile_internal as internal
    from tests.infra.execution_market.profile_parent_poll import ParentPollGate

    args = mock_parent(monkeypatch, tmp_path, phase="W3", case="normal")
    # All database I/O is fake here; provide its own valid config instead of
    # depending on the ambient CI database name. Keep the real guard enabled.
    for role in ("API", "AUTH", "ENGINE", "ENGINE_SCAN", "MIGRATOR", "MARKET_DATA"):
        monkeypatch.setenv(
            f"TIEWTRADE_DATABASE_URL_{role}", "postgresql://localhost/tiewtrade_internal20_mock"
        )
    args.acceptance_profile = internal.NAME_V3
    args.owners = args.workers = 20
    args.rate = 2
    args.cycles_per_owner = 30
    args.parent_poll_limit = 4
    args.r8_claim_budget = args.coordinate_claims = True
    args.publisher_heartbeat_per_book = args.final_tail_drain = True
    args.fault_schedule = internal.fault_schedule_for(internal.NAME_V3)
    monkeypatch.setattr(ParentPollGate, "verify_pool", lambda *a: None)
    monkeypatch.setattr(internal, "require_empty_database", AsyncMock())
    # mock_parent replaced the loader; use the pinned actual fixture data explicitly.
    import hashlib

    data = json.loads(args.fault_schedule.read_text())
    monkeypatch.setattr(
        f15,
        "load_fault_schedule",
        lambda path: (
            [
                f15.FaultEvent(e["offset_seconds"], e["duration_seconds"], e["kind"])
                for e in data["events"]
            ],
            30,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        ),
    )
    marks: dict[str, Any] = {}
    stats: dict[str, Any] = {}

    @asynccontextmanager
    async def intake(*a: Any, **kw: Any) -> AsyncIterator[object]:
        yield object()

    monkeypatch.setattr(profile_http, "internal_intake", intake)

    async def publisher(
        source: Any, stop: asyncio.Event, values: dict[str, Any], **kw: Any
    ) -> None:
        nonlocal stats
        stats = values
        stats["published"] = 2
        await stop.wait()

    monkeypatch.setattr(f15, "market_publisher", publisher)
    original_cycles = f15.run_scheduled_cycles

    async def cycles(*a: Any, **kw: Any) -> float:
        elapsed = await original_cycles(*a, **kw)
        counter = a[5]  # counters follows rate in the existing scheduler signature.
        counter.offered = counter.admitted = counter.completed = 3000
        counter.cycles = counter.cancels = counter.replays = 600
        counter.fills = 1200
        stats["published"] = 15002
        return elapsed

    monkeypatch.setattr(f15, "run_scheduled_cycles", cycles)

    class Checks:
        def __init__(self, *a: Any) -> None:
            pass

        async def observe_endurance(self, started: float, seconds: int) -> None:
            marks["observed_duration"] = seconds

        async def final(self, *, expected_periodic: int) -> dict[str, Any]:
            marks["periodic_count"] = expected_periodic
            return {"passed": True}

    monkeypatch.setattr(profile_positions, "PositionChecks", Checks)

    def rss(samples: Any, *, duration_seconds: int) -> dict[str, bool]:
        marks["rss_duration"] = duration_seconds
        return {"passed": True}

    monkeypatch.setattr(f15, "endurance_rss", rss)

    async def drain(*a: Any, **kw: Any) -> float:
        a[4].set()
        await a[3]
        return 0

    monkeypatch.setattr(f15, "drain_final_tail", drain)
    assert await f15._run(args) == 0
    result = json.loads((args.output / "result.json").read_text())
    assert result["status"] == "PENDING_POOL_VALIDATION"
    assert result["elapsed_seconds"] == 1800 and result["target_seconds"] == 1500
    assert result["required_book_inputs"] == 15000
    assert marks == {"observed_duration": 1800, "periodic_count": 30, "rss_duration": 1800}
    assert result["counters"]["completed"] == 3000
    assert result["processing_acceptance"]["revision"] == "NC12_SECTION21_PILOT"
