"""Failure-only observations are bounded, sanitized and do not replace workload results."""

import argparse
import asyncio
import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from tests.infra.execution_market import profile_diagnostics as diagnostic
from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market import profile_workload as workload
from tiewtrade.infra.db import session as db


@pytest.mark.parametrize("fail_query", [False, True])
async def test_query_observer_bounds_redacts_and_restores(
    monkeypatch: pytest.MonkeyPatch, fail_query: bool
) -> None:
    private = "PRIVATE_PARAMETER_OR_ERROR"
    value = object()
    execute = AsyncMock(return_value=value)
    monkeypatch.setattr(db, "_execute", execute)
    record: dict[str, Any] = {}
    with diagnostic.query_observations():
        # Queries outside a scheduled owner cycle are not observed.
        assert await db._execute(None, "outside", {"secret": private}) is value  # type: ignore[arg-type]
        token = diagnostic._CYCLE.set(record)
        try:
            for number in range(40):
                assert await db._execute(None, f"SELECT {number}", {"secret": private}) is value  # type: ignore[arg-type]
            if fail_query:
                execute.side_effect = RuntimeError(private)
                with pytest.raises(RuntimeError, match=private):
                    await db._execute(None, "SELECT private", None)  # type: ignore[arg-type]
        finally:
            diagnostic._CYCLE.reset(token)
    assert db._execute is execute
    assert diagnostic.query_fingerprint.cache_info().currsize == 0
    assert record["query_count"] == 40 + int(fail_query)
    assert len(record["queries"]) == 32 and record["queries_truncated"]
    assert len(record["recent_queries"]) == 16
    assert private not in json.dumps(record) and "SELECT" not in json.dumps(record)
    assert record["recent_queries"][-1]["outcome"] == ("RuntimeError" if fail_query else "RETURNED")
    assert all(len(fingerprint) == 64 for fingerprint in record["queries"])


@pytest.mark.parametrize("failure", ["none", "expiry", "inner", "cancel"])
async def test_failure_only_late_cycle_preserves_semantics_and_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    output = tmp_path / "run"
    owner = cast(workload.OwnerState, SimpleNamespace(user_id=uuid4()))
    original_timeout = asyncio.timeout
    requested: list[float | None] = []
    stopped = False
    snapshots: list[object] = []
    execute = AsyncMock(return_value=object())
    monkeypatch.setattr(db, "_execute", execute)
    sampler = workload.resource_sampler

    def budget(seconds: float | None) -> asyncio.Timeout:
        requested.append(seconds)
        return original_timeout(0.02)

    async def cycle(engine: Any, owner: Any, run: Any, number: int, *args: Any, **kw: Any) -> None:
        await db._execute(cast(AsyncConnection, None), "SELECT safe", {"private": "PRIVATE_VALUE"})
        if number == 1:
            if failure == "expiry":
                await asyncio.Event().wait()
            elif failure == "inner":
                raise TimeoutError("inner transport")
            elif failure == "cancel":
                raise asyncio.CancelledError

    async def run(args: argparse.Namespace, **kwargs: Any) -> int:
        nonlocal stopped
        output.mkdir()
        assert workload.resource_sampler is sampler
        assert not kwargs  # No extra runtime sampler or parent transaction observer.
        try:
            await workload.run_scheduled_cycles(
                cast(AsyncEngine, None), [owner], uuid4(), 2, 1000, workload.Counters(), []
            )
            return 7
        finally:
            stopped = True

    async def snapshot(path: Path, records: list[dict[str, Any]]) -> None:
        assert stopped
        snapshots.extend(records)

    monkeypatch.setattr(asyncio, "timeout", budget)
    monkeypatch.setattr(workload, "cycle", cycle)
    monkeypatch.setattr(workload, "_run", run)
    monkeypatch.setattr(diagnostic, "write_timeout_queue_snapshot", snapshot)
    # Any accidental full instrumentation must fail this test.
    monkeypatch.setattr(diagnostic, "TransactionTrace", lambda *a, **k: pytest.fail("full trace"))
    original_cycles = workload.run_scheduled_cycles
    args = argparse.Namespace(phase="SMOKE", output=output, parent_poll_limit=4)
    if failure == "none":
        assert await diagnostic.observe_workload(args, failure_only=True) == 7
    else:
        error = asyncio.CancelledError if failure == "cancel" else TimeoutError
        with pytest.raises(error) as caught:
            await diagnostic.observe_workload(args, failure_only=True)
        assert isinstance(caught.value, workload.CycleBudgetExceededError) is (failure == "expiry")
    assert requested == [60, 60]
    assert workload.run_scheduled_cycles is original_cycles
    assert workload.resource_sampler is sampler and db._execute is execute
    assert diagnostic._CYCLE.get() is None
    receipt = json.loads((output / "diagnostic-only.json").read_text())
    assert receipt["acceptance_result"] is False and receipt["failure_timeline_only"]
    assert receipt["trace_seconds"] == 0
    assert receipt["baseline_publisher_timing"] is False
    assert not (output / "parent.transactions.jsonl").exists()
    if failure == "expiry":
        record = snapshots[0]
        assert isinstance(record, dict)
        assert record["cycle"] == 1 and record["owner"] == str(owner.user_id)
        assert record["query_count"] == 1
        assert record["phases"][-1]["phase"] == "cycle"
        assert json.loads((output / "timeout-worker-progress.json").read_text())[
            "after_workers_stopped"
        ]
    else:
        assert not snapshots and not (output / "cycle-timeouts.json").exists()
    assert "PRIVATE_VALUE" not in "".join(p.read_text() for p in output.glob("*.json"))


@pytest.mark.parametrize("error", [False, True])
def test_worker_progress_tails_are_bounded_and_type_only(tmp_path: Path, error: bool) -> None:
    for number in range(25):
        (tmp_path / f"worker-{number}.latencies").write_text(
            "PRIVATE_INVALID_JSON"
            if error
            else (
                json.dumps({"started": 1, "finished": 2, "seconds": 1, "extra": "PRIVATE"}) + "\n"
            )
            * 2000
        )
    diagnostic.write_worker_progress(tmp_path)
    raw = (tmp_path / "timeout-worker-progress.json").read_text()
    data = json.loads(raw)
    assert len(data["workers"]) == 20 and "PRIVATE" not in raw
    assert all(row["tail_limit_bytes"] == 65536 for row in data["workers"])
    if error:
        assert all(row["error_type"] == "JSONDecodeError" for row in data["workers"])
    else:
        assert all(row["truncated"] for row in data["workers"])
        assert all(row["last_transaction"]["finished"] == 2 for row in data["workers"])


@pytest.mark.parametrize(
    "profile,phase,full,worker",
    [
        (internal.NAME, "SMOKE", False, False),
        (internal.RELEASE_NAME, "W1", False, False),
        (internal.RELEASE_NAME, "SMOKE", True, False),
        (internal.RELEASE_NAME, "SMOKE", False, True),
    ],
)
async def test_failure_timeline_rejects_unapproved_combinations(
    profile: str, phase: str, full: bool, worker: bool
) -> None:
    with pytest.raises(ValueError, match="failure timeline requires"):
        await workload.run(
            argparse.Namespace(
                acceptance_profile=profile,
                phase=phase,
                diagnostics=full,
                failure_timeline=True,
                worker_only=worker,
            )
        )


@pytest.mark.parametrize("value", ["PRIVATE", float("nan"), True])
def test_worker_timing_values_are_validated_before_publication(tmp_path: Path, value: Any) -> None:
    (tmp_path / "worker-0.latencies").write_text(
        json.dumps({"started": value, "finished": 2, "seconds": 1}) + "\n"
    )
    diagnostic.write_worker_progress(tmp_path)
    raw = (tmp_path / "timeout-worker-progress.json").read_text()
    assert "PRIVATE" not in raw and "NaN" not in raw
    assert json.loads(raw)["workers"][0]["error_type"] == "ValueError"


async def test_receipt_write_error_does_not_replace_primary_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "run"
    primary = workload.CycleBudgetExceededError("original criterion")

    async def run(*args: Any, **kwargs: Any) -> int:
        output.mkdir()
        raise primary

    def fail_save(*args: Any) -> None:
        raise OSError("PRIVATE_FILE_ERROR")

    monkeypatch.setattr(workload, "_run", run)
    monkeypatch.setattr(workload, "save", fail_save)
    with pytest.raises(workload.CycleBudgetExceededError) as caught:
        await diagnostic.observe_workload(
            argparse.Namespace(phase="SMOKE", output=output), failure_only=True
        )
    assert caught.value is primary
    assert "PRIVATE" not in str(primary.__notes__)


@pytest.mark.parametrize("cancel", [False, True])
async def test_observer_teardown_preserves_original_failure_and_cancellation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel: bool
) -> None:
    primary = asyncio.CancelledError() if cancel else ValueError("primary")
    output = tmp_path / "run"

    @contextmanager
    def observations(*args: Any, **kwargs: Any) -> Any:
        try:
            yield []
        finally:
            raise RuntimeError("PRIVATE_CLEANUP_ERROR")

    async def run(*args: Any, **kwargs: Any) -> int:
        output.mkdir()
        raise primary

    monkeypatch.setattr(diagnostic, "parent_observations", observations)
    monkeypatch.setattr(workload, "_run", run)
    with pytest.raises(type(primary)) as caught:
        await diagnostic.observe_workload(
            argparse.Namespace(phase="SMOKE", output=output), failure_only=True
        )
    assert caught.value is primary
    assert primary.__notes__ == ["observer cleanup also failed: RuntimeError"]
    assert "PRIVATE" not in "".join(path.read_text() for path in output.glob("*.json"))
